"""evidence.py — normalize a trial's trajectory into ``evidence.jsonl`` (one line per MIMIC call).

Runs IN the trial container, while the harness's native trajectory is still at hand, and emits one
stable schema. Every downstream consumer reads that rather than re-deriving "what did the agent
actually see" from four harness dialects, which is what ``eval/core/trajectory.py`` has to do when
this file's output is absent. That reverse-engineering is the fragile path: a dialect it does not
recognize yields an empty evidence pool, and an empty pool produces a grounding number rather than
an error.

It also records tool-call HEALTH per trial. A run whose MIMIC calls all returned
``401 Unauthorized`` otherwise looks like one that queried successfully and found little data:
both end with an empty evidence pool and a hedged report. ``status`` plus the summary counts
separate the two, and they are captured here because this is where the distinction still exists —
the trajectory has it, the scored reward does not.

Emits raw facts, NOT canonicalized ones. Table names come straight from the tool registry (or the
SQL text for ``run_sql``); the ``canon``/``_DROP`` folding in
``eval/metrics/grounding/evidence_retrieval_recall.py`` is tied to the GOLD vocabulary and stays
with the consumer, so the gold set can evolve without re-running trials.

Stdlib only. The tool→table map is read from the installed ``mimic_tools`` registry when present
(no vendored copy to drift), with a minimal fallback for offline use outside the container.

  python evidence.py --trajectory /logs/agent/trajectory.json --output /logs/verifier/evidence.jsonl

Schema (one JSON object per line):
  {"step": 12, "call_id": "toolu_…", "tool": "get_lab_timeline",
   "kind": "mimic"|"policy"|"exec_output"|"subagent",
   "args": {...},                       # run_sql keeps its query so consumers can parse tables
   "status": "ok"|"error"|"empty"|"unattributed", "n_rows": 37, "chars": 4821,
   "record_ids": ["10001217", "20449658"], "text": "<unwrapped tool output>"}

There is deliberately NO `tables` field — see the tool-recognition note below.

A trailing summary is NOT written into the jsonl (it must stay one-record-per-line); callers get it
from ``summarize()`` or the ``--summary`` file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── tool RECOGNITION surface ─────────────────────────────────────────────────────────────
# This module records WHICH tool was called; it deliberately does NOT record which tables that
# tool reads. The tool→table map is a SCORING POLICY, not a raw fact: the offline map overrides
# the registry for `get_data_availability` (it returns row COUNTS, never clinical content, so
# crediting its 16 tables would let one call score full retrieval recall), and that override is
# revisable. Freezing it into a per-trial artifact would make a later correction unrecomputable —
# the same input-stability rule that keeps `canon` out of here
# . Consumers map `tool` + `args` → tables at scoring time.
#
# The registry is used only to RECOGNIZE MIMIC tool names. A vendored fallback covers an import
# failure / use outside the container: without it an empty map would make `is_mimic_tool` reject
# every typed call and silently degrade a whole sweep to an empty evidence pool.
_FALLBACK_TOOLS = frozenset(
    {
        "get_patient_demographics",
        "get_data_availability",
        "list_admissions",
        "get_admission_details",
        "list_ed_visits",
        "get_ed_visit_details",
        "list_icu_stays",
        "get_icu_stay_details",
        "get_lab_timeline",
        "get_vitals_timeline",
        "get_chart_timeline",
        "get_icu_administrations",
        "get_medication_administered",
        "get_medication_prescribed",
        "get_medication_reconciliation",
        "get_diagnosis_history",
        "get_procedures",
        "get_imaging_studies",
        "get_microbiology_results",
        "get_fluid_balance",
        "list_notes",
        "get_note",
        "search_notes",
        "list_orders",
        "run_sql",
    }
)


def _registry_tools() -> tuple[frozenset, bool]:
    """(recognized tool names, registry_loaded). Falls back to the vendored set."""
    try:
        from mimic_tools.tool_registry import TOOLS  # type: ignore

        return frozenset(TOOLS), True
    except (
        Exception
    ):  # noqa: BLE001 — offline use; recognition falls back, nothing silently empties
        return _FALLBACK_TOOLS, False


KNOWN_TOOLS, REGISTRY_LOADED = _registry_tools()

# The policy tools read no MIMIC table but ARE data access; keep them in the surface so a
# policy-grounding consumer can count them, with an empty table list. They are tagged
# kind="policy" and contribute NO record_ids: guideline text is full of 6-digit reference and
# line numbers that the ID regex cannot distinguish from a subject_id, so pooling them would let
# a report cite a FABRICATED id and be scored grounded because some PDF contains that number.
# That would silently weaken T1's fabrication floor. Verified against the offline extractor,
# which excludes these tools from its pool for the same reason.
_POLICY_TOOLS = {"list_policy_docs", "search_policy", "read_policy"}

# ── codex exec-scaffold ("code mode") ────────────────────────────────────────────────────
# Some codex runs (gpt-5.6-sol / -luna) call ONE tool named `exec` per step and drive MIMIC from
# inside a JS script, so there are no per-tool tool_calls to read. Ported from
# eval/core/trajectory.py::parse_exec_script — without it those runs extract zero calls, which
# reads as "the agent touched no data" rather than "the extractor didn't understand this harness".
# The script text contains the CALLS (so tables are attributable); the returned ROWS come back in
# the exec step's own observation, which is captured separately as a kind="exec_output" record.
# Must be an actual CALL — the name followed by "(" — and found in LIVE code, not in a comment or
# a string. Agents routinely build introspection arrays like
#   const names = ["mcp__mimic__list_policy_docs", "mcp__mimic__get_admission_details", ...]
# and a bare-name match credited every tool listed. Measured on 1,261 real exec scripts: 42 of
# 2,438 references (2%) were non-calls, but retrieval coverage is a SET UNION over tables, so one
# such line can add several tables and a single one can flip a case's recall.
_EXEC_MIMIC_REF = re.compile(r"mcp__mimic__(\w+)\s*\(")


def _live_code(script: str) -> str:
    """`script` with block/line comments and string literals blanked out.

    Applied only for CALL detection. ``_sql_literals`` still reads the ORIGINAL text, because a
    run_sql query lives inside exactly the string literals blanked here.
    """
    s = re.sub(r"/\*.*?\*/", " ", script or "", flags=re.S)
    s = re.sub(r"//[^\n]*", " ", s)
    return re.sub(r"`(?:[^`\\]|\\.)*`|\"(?:[^\"\\]|\\.)*\"|\'(?:[^\'\\]|\\.)*\'", '""', s)


_EXEC_STR_LITERAL = re.compile(
    r"`((?:[^`\\]|\\.)*)`" r'|"((?:[^"\\]|\\.)*)"' r"|'((?:[^'\\]|\\.)*)'",
    re.S,
)
_SQL_FROM = re.compile(r"\bfrom\s+[a-z_]", re.I)
_SQL_SELECT = re.compile(r"\bselect\b", re.I)


def _sql_literals(script: str) -> list[str]:
    """String/template literals in an exec script that look like a query (SELECT and FROM)."""
    out = []
    for m in _EXEC_STR_LITERAL.finditer(script or ""):
        lit = m.group(1) or m.group(2) or m.group(3) or ""
        if _SQL_SELECT.search(lit) and _SQL_FROM.search(lit):
            out.append(lit)
    return out


def exec_script_calls(script: str) -> list[tuple[str, dict]]:
    """[(tool, args)] recovered from one exec script. run_sql carries its query so the consumer can
    still attribute tables; other tools carry {}.

    Counts OCCURRENCES, not distinct names: a script calling get_lab_timeline 30 times is 30 data
    calls, and de-duplicating made the `data` column per-call for typed harnesses but
    per-distinct-name-per-step for code mode — while the table footer advertises it as the fair
    cross-harness metric.
    """
    refs = _EXEC_MIMIC_REF.findall(_live_code(script))
    out: list[tuple[str, dict]] = []
    for name in refs:
        if name == "run_sql":
            continue  # handled below, paired with its query
        if name in KNOWN_TOOLS or name in _FALLBACK_TOOLS or name in _POLICY_TOOLS:
            out.append((name, {}))
    n_sql = sum(1 for n in refs if n == "run_sql")
    if n_sql:
        qs = _sql_literals(script)
        # Pair each recovered query with a call; if the script builds queries dynamically (or calls
        # run_sql more times than there are literals) still record every call, argument-less.
        for i in range(max(n_sql, len(qs))):
            out.append(("run_sql", {"query": qs[i]} if i < len(qs) else {}))
    return out


# ── record-ID atoms — MUST match eval/metrics/grounding/insight_grounding.py::_extract_ids ──
# Kept in sync deliberately: if the two disagree, in-trial T1 and the offline T1 disagree about
# what counts as an ID, which is exactly the drift this file exists to remove.
_TS = re.compile(r"\b\d{4}-\d{2}(?:-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?)?\b")
_ID_HYPHEN = re.compile(r"\b\d{6,}-(?:[A-Z]{1,4}-)?\d+\b")
_ID_INT = re.compile(r"\b\d{6,}\b")

# Only applied to a short, NON-JSON payload (see _status). Codes must sit next to an auth/error
# word so a lab value of 500 or a dilution of 403 can never match; "error"/"exception" must lead.
# claude-code truncates an oversized tool result and writes the full payload to a file:
#   "Error: result (71,480 characters ...) exceeds maximum allowed tokens. Output has been saved
#    to /logs/agent/sessions/.../tool-results/mcp-mimic-search_policy-...txt"
# The CALL SUCCEEDED — only the inline copy was elided. Classifying that as `error` cost 71k chars
# of real evidence on the very first smoke trial: consumers that keep only successful records
# dropped both its ids and its table attribution.
_SPILL_RX = re.compile(r"exceeds maximum allowed tokens.*?saved to\s+(\S+)", re.S | re.IGNORECASE)
# Auth/permission failures are the INFRASTRUCTURE signal (a whole sweep losing data access, like the
# 401 job). Kept distinct from an agent-caused failure such as calling a tool that does not exist.
_AUTH_ERR_RX = re.compile(r"\b(?:401|403)\b|\b(?:unauthorized|forbidden)\b", re.IGNORECASE)

_ERR_RX = re.compile(
    r"^\s*(?:error|exception|traceback)\b"
    r"|\b(?:unauthorized|forbidden|permission denied|access denied)\b"
    r"|\b(?:40[13]|50[023])\s*[:\-]?\s*(?:unauthorized|forbidden|error|internal|bad gateway|"
    r"service unavailable)\b"
    r"|\b(?:timed?\s*out|timeout)\b",
    re.IGNORECASE,
)


# Longest first — "mcp__mimic__" must win over "mcp_mimic_". Kept identical to
# eval/core/trajectory.py::MCP_PREFIXES. A prefix missing here does not error: every call from
# that harness extracts as ZERO, and the run reads as "the agent touched no data".
_MCP_PREFIXES = ("mcp__mimic__", "mcp_mimic_", "mimic_")


def normalize_tool(name: str | None) -> str:
    """Strip the MCP prefix: claude-code ``mcp__mimic__x``, gemini-cli ``mcp_mimic_x``,
    opencode ``mimic_x``; codex names are already bare."""
    n = (name or "").strip()
    for pref in _MCP_PREFIXES:
        if n.startswith(pref):
            return n[len(pref) :]
    return n


def is_mimic_tool(name: str | None) -> bool:
    t = normalize_tool(name)
    return bool(t) and (t in KNOWN_TOOLS or t in _FALLBACK_TOOLS or t in _POLICY_TOOLS)


def extract_record_ids(text: str) -> list[str]:
    """Record-ID atoms present in tool output — the EVIDENCE side, so compound prefixes are KEPT
    (a subject_id may appear only inside ``10001217-RR-14``, yet a report may cite it bare).
    Timestamps are stripped first so a date can't be misread as an ID."""
    text = _TS.sub(" ", text or "")
    ids = {m.group() for m in _ID_HYPHEN.finditer(text)}
    ids |= {m.group() for m in _ID_INT.finditer(text)}
    return sorted(ids)


def unwrap_text(content) -> str:
    """Recover the tool's returned payload from a harness-wrapped observation.

    Handles, in one pass: claude-code's ``{"type":"text","text":"<rows-json>"}`` envelope (often
    itself a JSON string), gemini-cli's ``<untrusted_context>…</untrusted_context>`` wrapper, and
    codex's ``"Wall time: …\\nOutput:\\n[…]"`` prefix. Falls back to the raw string.
    """
    if content is None:
        return ""
    if isinstance(content, (dict, list)):
        return "\n".join(_walk_text(content))
    s = str(content)
    s = re.sub(r"</?untrusted_context>", "", s).strip()
    m = re.search(r"Output:\s*(\[.*|\{.*)", s, re.S)
    if m:
        s = m.group(1)
    if s[:1] in "[{":
        try:
            return "\n".join(_walk_text(json.loads(s)))
        except ValueError:
            return s
    return s


def _walk_text(obj) -> list[str]:
    """Collect payload text from a nested envelope: prefer ``text`` fields, else serialize."""
    out: list[str] = []
    if isinstance(obj, dict):
        if "text" in obj and isinstance(obj["text"], str):
            inner = obj["text"].strip()
            if inner[:1] in "[{":
                try:
                    out.extend(_walk_text(json.loads(inner)))
                    return out
                except ValueError:
                    pass
            out.append(obj["text"])
            return out
        for v in obj.values():
            out.extend(_walk_text(v))
        if not out:
            out.append(json.dumps(obj, ensure_ascii=False))
    elif isinstance(obj, list):
        # A list of row dicts IS the payload — serialize it once rather than per-field.
        if obj and all(isinstance(x, dict) and "text" not in x for x in obj):
            out.append(json.dumps(obj, ensure_ascii=False))
        else:
            for v in obj:
                out.extend(_walk_text(v))
    elif obj is not None:
        out.append(str(obj))
    return out


def _resolve_spill(path: str, traj_file: str | None) -> str | None:
    """Read a spilled tool-result file. The notice carries the in-CONTAINER absolute path
    (/logs/agent/sessions/...); post-hoc the same file sits under the trial's own agent/ dir, so
    fall back to remapping everything from "agent/" onward relative to the trajectory."""
    # The notice ends the sentence right after the filename ("...-1785538066561.txt.\nFormat:"),
    # and a greedy \S+ capture swallows that period — which silently defeated the recovery on the
    # first real trial. Strip trailing sentence punctuation before resolving.
    path = (path or "").rstrip(".,;:)]}\"'")
    try:
        p = Path(path)
        if p.is_file():
            return p.read_text(errors="replace")
        if traj_file and "agent/" in path:
            cand = Path(traj_file).parent.parent / path[path.index("agent/") :]
            if cand.is_file():
                return cand.read_text(errors="replace")
    except OSError:
        return None
    return None


def _row_count(text: str) -> int | None:
    t = (text or "").lstrip()
    if not t.startswith("["):
        return None
    try:
        v = json.loads(t)
    except ValueError:
        return None
    return len(v) if isinstance(v, list) else None


def _status(text: str, n_rows: int | None) -> str:
    """ok | error | empty for one tool result.

    Deliberately conservative about `error`, because clinical payloads collide with every naive
    error pattern: a glucose of 500, a microbiology dilution of 403, and the note phrase
    "patient denied chest pain" all look like HTTP status codes or failure text. Matching those
    inflates `evidence_calls_error` (the signal this file exists to provide) and makes a consumer
    that keeps only `ok` records silently drop real data. So:
      * a payload that PARSES as a row array is a successful call by construction — never an error;
      * HTTP-ish codes count only next to an actual auth/error word;
      * bare "error"/"exception" counts only at the START of a non-JSON payload.
    """
    t = (text or "").strip()
    if not t:
        return "empty"
    if n_rows is not None:  # parsed as a JSON array -> the call returned
        return "empty" if n_rows == 0 else "ok"
    if _SPILL_RX.search(t):
        return "spilled"  # succeeded; payload elided by the harness (see _SPILL_RX)
    if t[:1] not in "[{" and len(t) <= 2000 and _ERR_RX.search(t):
        return "auth_error" if _AUTH_ERR_RX.search(t) else "error"
    return "ok"


def iter_evidence(traj: dict, traj_file: str | None = None):
    """Yield one evidence record per MIMIC tool call in an ATIF trajectory.

    `traj_file` lets a spilled payload (see _SPILL_RX) be read back off disk, recovering evidence
    the harness elided from the inline result.
    """
    for step in traj.get("steps") or []:
        if not isinstance(step, dict):
            continue
        calls = [c for c in (step.get("tool_calls") or []) if isinstance(c, dict)]
        results = [
            r for r in ((step.get("observation") or {}).get("results") or []) if isinstance(r, dict)
        ]
        by_id = {r.get("source_call_id"): r for r in results if r.get("source_call_id")}
        for i, call in enumerate(calls):
            raw_name = (
                call.get("function_name")
                or (call.get("function") or {}).get("name")
                or call.get("name")
            )
            # exec-scaffold step: the MIMIC calls are inside the script, and the rows come back in
            # this step's observation. Emit one record per recovered call (tables attributable,
            # no text) plus one exec_output record carrying the returned text (where the IDs are).
            # `wait` carries the output of an ASYNC exec cell — the rows (and therefore the record
            # ids) arrive there, not in the exec step. Handling only `exec` dropped them entirely.
            if normalize_tool(raw_name) == "wait":
                cid_w = call.get("tool_call_id") or call.get("id")
                res_w = by_id.get(cid_w) or (results[i] if i < len(results) and not by_id else None)
                text_w = unwrap_text((res_w or {}).get("content"))
                if text_w:
                    yield {
                        "step": step.get("step_id"),
                        "call_id": cid_w,
                        "tool": "wait",
                        "kind": "exec_output",
                        "args": {},
                        "status": _status(text_w, _row_count(text_w)),
                        "n_rows": _row_count(text_w),
                        "chars": len(text_w),
                        "record_ids": extract_record_ids(text_w),
                        "text": text_w,
                    }
                continue
            if normalize_tool(raw_name) == "exec":
                args_e = call.get("arguments")
                if isinstance(args_e, str):
                    try:
                        args_e = json.loads(args_e)
                    except ValueError:
                        args_e = {}
                script = (args_e or {}).get("input", "") if isinstance(args_e, dict) else ""
                for tool_e, targs in exec_script_calls(script):
                    yield {
                        "step": step.get("step_id"),
                        "call_id": call.get("tool_call_id") or call.get("id"),
                        "tool": tool_e,
                        "kind": "policy" if tool_e in _POLICY_TOOLS else "mimic",
                        "args": targs,
                        # The script proves the CALL, not its result — so status is explicitly
                        # unattributed rather than "empty", which would wrongly read as "returned
                        # nothing". Row text lives in the exec_output record below.
                        "status": "unattributed",
                        "n_rows": None,
                        "chars": 0,
                        "record_ids": [],
                        "text": "",
                        "from_exec_script": True,
                    }
                cid_e = call.get("tool_call_id") or call.get("id")
                res_e = by_id.get(cid_e) or (results[i] if i < len(results) and not by_id else None)
                text_e = unwrap_text((res_e or {}).get("content"))
                if text_e:
                    yield {
                        "step": step.get("step_id"),
                        "call_id": cid_e,
                        "tool": "exec",
                        "kind": "exec_output",
                        "args": {},
                        "status": _status(text_e, _row_count(text_e)),
                        "n_rows": _row_count(text_e),
                        "chars": len(text_e),
                        "record_ids": extract_record_ids(text_e),
                        "text": text_e,
                    }
                continue
            # A sub-agent (claude-code's `Agent` tool) makes its MIMIC calls inside a nested
            # session, so they never appear as tool_calls here — but the summary it returns to the
            # parent IS in this trajectory and legitimately carries record ids the report may cite.
            # Without pooling it, the fabrication floor flags real citations. (The sub-agent's own
            # tool-call args, recoverable only from agent/sessions/**.jsonl, are still out of reach
            # from inside the container — see eval/core/trajectory.py::subagent_observations.)
            if normalize_tool(raw_name) in ("Agent", "Task"):
                cid_s = call.get("tool_call_id") or call.get("id")
                res_s = by_id.get(cid_s) or (results[i] if i < len(results) and not by_id else None)
                text_s = unwrap_text((res_s or {}).get("content"))
                if text_s:
                    yield {
                        "step": step.get("step_id"),
                        "call_id": cid_s,
                        "tool": normalize_tool(raw_name),
                        "kind": "subagent",
                        "args": {},
                        "status": _status(text_s, _row_count(text_s)),
                        "n_rows": None,
                        "chars": len(text_s),
                        "record_ids": extract_record_ids(text_s),
                        "text": text_s,
                        "subagent_summary": True,
                    }
                continue
            if not is_mimic_tool(raw_name):
                continue
            tool = normalize_tool(raw_name)
            args = call.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {"_raw": args}
            if not isinstance(args, dict):
                args = {}
            cid = call.get("tool_call_id") or call.get("id")
            # Pair by source_call_id; fall back to positional for harnesses that omit it.
            res = by_id.get(cid) or (results[i] if i < len(results) and not by_id else None)
            text = unwrap_text((res or {}).get("content"))
            spill = _SPILL_RX.search(text or "")
            recovered = _resolve_spill(spill.group(1), traj_file) if spill else None
            if recovered:
                text = recovered  # full payload restored; status recomputed from real content below
            n_rows = _row_count(text)
            kind = "policy" if tool in _POLICY_TOOLS else "mimic"
            yield {
                "step": step.get("step_id"),
                "call_id": cid,
                "tool": tool,
                "kind": kind,
                "args": args,
                "status": _status(text, n_rows),
                "n_rows": n_rows,
                "chars": len(text),
                "record_ids": extract_record_ids(text) if kind == "mimic" else [],
                "text": text,
                **({"spill_recovered": True} if recovered else {}),
            }


def summarize(records: list[dict]) -> dict:
    """Trial-level health + coverage counts. `*_calls_error` is the signal that a whole sweep lost
    its data access: a sweep-wide nonzero count means the system's scores measure a broken sidecar,
    not the model."""
    ids: set[str] = set()
    by_status: dict[str, int] = {
        "ok": 0,
        "error": 0,
        "auth_error": 0,
        "empty": 0,
        "unattributed": 0,
        "spilled": 0,
    }
    n_policy = 0
    n_exec = 0
    n_sub = 0
    for r in records:
        ids |= set(r["record_ids"])  # empty for kind="policy" by construction
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        n_policy += 1 if r.get("kind") == "policy" else 0
        n_exec += 1 if r.get("from_exec_script") else 0
        n_sub += 1 if r.get("kind") == "subagent" else 0
    return {
        "evidence_calls": len(records),
        "evidence_calls_policy": n_policy,
        "evidence_calls_from_exec_script": n_exec,
        # >0 means the id pool is INCOMPLETE: a sub-agent's own tool results are not in
        # this trajectory, only its summary. Consumers should treat grounding as a lower bound.
        "evidence_subagent_summaries": n_sub,
        "evidence_calls_ok": by_status["ok"],
        "evidence_calls_error": by_status["error"],
        # The INFRASTRUCTURE signal: a sweep that lost data access (the 401 job). An ordinary
        # agent-caused failure — e.g. calling a tool the sidecar does not serve — stays in
        # evidence_calls_error, so the two are never conflated.
        "evidence_calls_auth_error": by_status["auth_error"],
        "evidence_calls_spilled": by_status["spilled"],
        "evidence_calls_empty": by_status["empty"],
        "evidence_calls_unattributed": by_status["unattributed"],
        "evidence_record_ids": len(ids),
        "evidence_chars": sum(r["chars"] for r in records),
        "evidence_registry_loaded": 1 if REGISTRY_LOADED else 0,
    }


def build(trajectory_file: str) -> tuple[list[dict], dict]:
    p = Path(trajectory_file)
    if not p.is_file():
        return [], summarize([])
    try:
        traj = json.loads(p.read_text(errors="replace"))
    except ValueError:
        return [], summarize([])
    if not isinstance(traj, dict):
        return [], summarize([])
    records = list(iter_evidence(traj, trajectory_file))
    return records, summarize(records)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--trajectory", required=True)
    ap.add_argument("--output", required=True, help="evidence.jsonl path")
    ap.add_argument("--summary", default="", help="optional path for the summary JSON")
    ap.add_argument(
        "--max-text-chars",
        type=int,
        default=0,
        help="truncate each record's `text` (0 = keep whole; T2 grounding needs the rows)",
    )
    args = ap.parse_args()

    records, summary = build(args.trajectory)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        for r in records:
            if args.max_text_chars and len(r["text"]) > args.max_text_chars:
                r = {**r, "text": r["text"][: args.max_text_chars], "text_truncated": True}
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    if args.summary:
        Path(args.summary).write_text(json.dumps(summary, indent=2))
    print(
        f"evidence: {summary['evidence_calls']} MIMIC calls "
        f"({summary['evidence_calls_ok']} ok / {summary['evidence_calls_error']} error / "
        f"{summary['evidence_calls_empty']} empty, "
        f"{summary['evidence_calls_unattributed']} unattributed), "
        f"{summary['evidence_record_ids']} record ids -> {out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
