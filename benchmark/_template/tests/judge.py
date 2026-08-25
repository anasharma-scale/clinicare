#!/usr/bin/env python3
"""Deterministic verifier for MIMIC healthcare Harbor trials.

Writes ``reward.json`` for Harbor. This makes **no LLM
call**: everything it computes is deterministic, needs no credentials, and cannot silently skip.

  * **Outcome (the primary `score`)** — regex-extract the agent's 4-class verdict from
    ``report.md``'s ``## Answer:`` line and compare it to the task's ``expected_label``. Regex, not
    an LLM, so it can't fail or be talked into a grade; only the first verdict line counts and a
    line naming several labels resolves to none (anti-gaming).
  * **Patient-evidence grounding** — cited record IDs in the report vs the IDs present in retrieved
    evidence (``evidence.jsonl``, produced by ``evidence.py`` earlier in ``test.sh``), plus
    tool-call health counts. A fabrication floor: an ID can't be computed, so one absent from every
    tool result was invented.
  * **Policy grounding, deterministic half** — citation existence, line-span validity, file-level
    P/R/F1 vs the gold governing docs, and the 3-class relevance item (gold-doc set membership).

This file is hardlinked into every generated task dir and must run in a container with no repo
checkout, so it may import nothing from ``eval/``, while ``eval/`` imports the deterministic
helpers below freely.

On any unrecoverable failure ``reward.json`` is still written (``score=0.0``) so Harbor sees a
reward rather than treating the verifier as missing; the reason lands in ``grades_detail.json``.
"""

import argparse
import json
import os
import re
import sys
import traceback
from pathlib import Path


def _read_text(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.is_file():
        return ""
    return p.read_text(errors="replace").strip()


# The four canonical verdict labels (the outcome classes the agent must choose from).
_LABELS = ("YES", "NO", "INDETERMINATE_LACK_OF_DATA", "INDETERMINATE_MEDICAL_AMBIGUITY")

# The verdict line: a heading/bold "Answer"/"Verdict"/… label at the START of a line
# (only markdown punctuation allowed before it, so an in-prose "...is a clear Yes" never
# matches), then whatever the agent put after it. Case-insensitive.
_VERDICT_MARKER = re.compile(
    r"^[\s#>*_`\-]*(?:final\s+answer|answer|verdict|determination)\b\s*[:\-–—.)]?\s*(.*)$",
    re.IGNORECASE,
)

# The agent self-reports an environment failure (MIMIC tools timing out / disconnecting) with a
# "## Environment: degraded" line — see the Final answer section of _template/instruction_appendix.md.
# Purpose: keep the two causes of an INDETERMINATE_LACK_OF_DATA verdict distinguishable. Without
# this, a trial whose tools died is indistinguishable in reward.json from one where the patient's
# record genuinely lacks the data — the first is infrastructure, the second is a clinical finding —
# and any downstream label-rate tabulation (e.g. construction/scripts/analyze_labels.py) merges
# them silently.
# Deliberately NOT part of `score`: it is a diagnostic flag, not a grading input. "Environment" is
# not one of _VERDICT_MARKER's keywords, so this line can never be mistaken for the verdict line.
# Tolerant of markdown drift around the keyword the same way _VERDICT_MARKER is (`## Environment:
# degraded`, `**Environment:** degraded`, `- environment - degraded`), but still anchored at line
# start, so "the environment was degraded" in prose cannot trip it.
_ENV_DEGRADED_MARKER = re.compile(
    r"^[\s#>*_`\-]*environment[\s*_`]*[:\-–—.)]?[\s*_`]*degraded\b",
    re.IGNORECASE | re.MULTILINE,
)


def _labels_in_slot(slot: str) -> set[str]:
    """The distinct 4-class labels named in a verdict slot. A slot that names more than one is
    ambiguous (the caller returns None). A bare 'Indeterminate' with no subtype names no
    resolvable label — the instruction requires the specific subtype."""
    s = slot.lower()
    found: set[str] = set()
    if "indetermin" in s:
        if "lack" in s or "insufficient data" in s:
            found.add("INDETERMINATE_LACK_OF_DATA")
        if "ambig" in s or "medical" in s:
            found.add("INDETERMINATE_MEDICAL_AMBIGUITY")
    if re.search(r"\byes\b", s):
        found.add("YES")
    if re.search(r"\bno\b", s):
        found.add("NO")
    return found


def _collapse(label: str) -> str:
    """Fold to the shared 3-class vocabulary (YES/NO/ESCALATE); the whole indeterminate family
    → ESCALATE. Used only for the one ground-truth case that has no subtype (see _label_match).
    """
    u = (label or "").upper()
    if u in ("YES", "NO"):
        return u
    if "INDETERM" in u or "ESCALATE" in u:
        return "ESCALATE"
    return u


def _label_match(agent: str, gt: str) -> bool:
    """True 4-way match between the agent's verdict and the ground-truth label — the two
    indeterminate SUBTYPES are distinct and must match exactly. The ONE concession: a ground
    truth of the merged 3-class `ESCALATE` (silver_patients.csv folds both subtypes into it, so
    the subtype isn't recoverable) accepts either indeterminate. A 4-class ground truth
    (patients.csv) is matched exactly, subtype and all."""
    a = (agent or "").upper()
    g = (gt or "").upper()
    if not a or not g:
        return False
    if a == g:
        return True
    return g == "ESCALATE" and _collapse(a) == "ESCALATE"


def _extract_outcome_label(report: str) -> str | None:
    """Deterministically pull the agent's 4-class verdict from report.md.

    The 4 classes: Yes / No / Indeterminate – lack of data / Indeterminate – medical ambiguity.

    Anti-gaming contract (matches the instruction the agent is given):
      * Only the FIRST verdict-marker line is authoritative — an agent can't bury a
        clean line after a hedged one.
      * That line's answer slot must resolve to EXACTLY ONE distinct label. A slot that
        lists several ("Yes / No / Indeterminate – lack of data", "Yes, not No") is ambiguous
        and returns None (scored incorrect) — so dumping all labels can't match the key.
      * Case-insensitive; a bare "Indeterminate" with no subtype resolves to no label.
    If the marker line has no text after it, the next non-empty line is used as the slot
    (covers a "## Answer\\nYes" split). Returns the canonical label, or None if no
    unambiguous verdict is present.

    Keep in sync with construction/scripts/analyze_labels.py::extract_verdict.
    """
    lines = report.splitlines()

    def _slot_label(i, m):
        slot = m.group(1)
        if not slot.strip():  # "## Answer\nYes" split — use the next non-empty line
            for nxt in lines[i + 1 :]:
                if nxt.strip():
                    slot = nxt
                    break
        found = _labels_in_slot(slot)
        return found.pop() if len(found) == 1 else None

    # Prefer the first verdict marker that is a markdown HEADING (## Answer / ### Answer): that is the
    # designated verdict location, and preferring it makes extraction robust to reasoning-first formats
    # (e.g. the md answer-format, where a stray "Answer:"-prose line inside an Explanation section could
    # otherwise preempt the real verdict). Fall back to the first marker of any kind (bold/plain), which
    # preserves the original behavior when no heading marker exists.
    for headings_only in (True, False):
        for i, line in enumerate(lines):
            if headings_only and not line.lstrip().startswith("#"):
                continue
            if _VERDICT_MARKER.match(line):
                return _slot_label(i, _VERDICT_MARKER.match(line))
    return None


# Per tool-result cap when feeding a trajectory to the judge. The claude-code trajectory format
# stores each tool result several times over (observation.content + the extra.tool_result_metadata
# duplicates), and a single run_sql/notes call can dump ~1 MB — bloating a trajectory past 2 MB of
# mostly-redundant raw data the PROCESS judge doesn't need (it grades from the report + which tools
# ran + the agent's reasoning, not the raw rows). We keep every step, cap each tool-result `content`
# to this many chars, and drop the duplicate `extra` blobs. ~12k chars ≈ 3k tokens/result keeps
# trajectories well under _CHUNK_THRESHOLD_CHARS (one call, no chunking). Set 0 to disable.
_MAX_TOOL_RESULT_CHARS = int(os.environ.get("JUDGE_MAX_TOOL_RESULT_CHARS", "12000"))


def _slim_trajectory(text: str) -> str:
    """Shrink a trajectory JSON for judging: cap each tool-result `content` and drop the redundant
    duplicate copies. Preserves step structure + reasoning. No-op if disabled or not a steps JSON.
    """
    if _MAX_TOOL_RESULT_CHARS <= 0 or not text:
        return text
    try:
        d = json.loads(text)
    except Exception:
        return text
    if not isinstance(d, dict) or "steps" not in d:
        return text
    cap = _MAX_TOOL_RESULT_CHARS
    for step in d.get("steps") or []:
        if not isinstance(step, dict):
            continue
        obs = step.get("observation") or {}
        for r in obs.get("results") or []:
            if not isinstance(r, dict):
                continue
            c = r.get("content")
            if isinstance(c, str) and len(c) > cap:
                r["content"] = c[:cap] + f"\n…[truncated {len(c) - cap:,} chars of tool output]…"
            r.pop("extra", None)  # drops the 3-4x redundant tool_result_metadata duplicates
    return json.dumps(d, ensure_ascii=False)


def _read_trajectory(path: str | None) -> str:
    """Read a trajectory file and slim it for judging (see _slim_trajectory)."""
    return _slim_trajectory(_read_text(path))


# ── policy corpus resolution ───────────────────────────────────────────────────────────────
# The corpus is mounted into the SIDECAR, not into this container (sidecar.compose.yml:
# "Stage the (non-sensitive) policy corpus into the sidecar instead of the agent container").
# So a local filesystem probe is absent on every policy-ON docker trial and must NOT be used to
# infer the run's condition — doing so silently graded a whole sweep on the policy-OFF branch and
# marked every real citation "fabricated". The condition comes from the bundle (`policy_expected`,
# set at build time); the corpus is resolved here, materializing it from the sidecar when needed.


def _sidecar_call(tool: str, params: dict) -> dict | None:
    """One `POST {MIMIC_TOOLS_URL}/call-tool` (the same API the agent's MCP shim uses).
    Returns the tool result, or None if the sidecar is unreachable / the call fails."""
    import urllib.request

    base = (os.environ.get("MIMIC_TOOLS_URL") or "").rstrip("/")
    if not base:
        return None
    body = json.dumps({"tool": tool, "params": params}).encode()
    headers = {"Content-Type": "application/json"}
    if key := os.environ.get("MIMIC_TOOLS_API_KEY"):
        headers["x-api-key"] = key
    req = urllib.request.Request(base + "/call-tool", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(
            req, timeout=float(os.environ.get("POLICY_FETCH_TIMEOUT", "120"))
        ) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 — unreachable sidecar is a normal degraded case, not a crash
        return None
    return payload.get("result") if payload.get("ok") else None


def _strip_line_prefixes(text: str, start: int) -> str:
    """Undo read_policy's ``"{n}: "`` line-number prefixes to recover the original lines.
    Only strips a prefix whose number matches the expected physical line, so an original line
    that merely looks like ``12: foo`` survives intact.

    Line-exact, not byte-exact: a trailing newline on the source document is NOT reproduced —
    read_policy builds its body by joining ``splitlines()``, so the newline is gone before this
    function sees it and cannot be recovered. Harmless, because the citation contract is
    line-span based (``L<start>-L<end>``) and every check in policy_scoring reads the doc through
    ``splitlines()``, which yields the same list either way: span validity and the extracted
    ``cited_text`` are identical, including for a citation to the final line."""
    out = []
    for i, line in enumerate(text.splitlines(), start):
        pref = f"{i}: "
        out.append(line[len(pref) :] if line.startswith(pref) else line)
    return "\n".join(out)


def _materialize_policy_corpus() -> str | None:
    """Rebuild the corpus locally from the sidecar (list_policy_docs + read_policy) so the
    deterministic citation evals (existence, line-span validity, file-level P/R/F1) can run.
    Returns the temp dir, or None if the sidecar can't serve the corpus."""
    docs = _sidecar_call("list_policy_docs", {})
    if not isinstance(docs, list) or not docs:
        return None
    import atexit
    import shutil
    import tempfile

    dest = Path(tempfile.mkdtemp(prefix="policy_corpus_"))
    # The corpus has to outlive this function (score_policy_grounding reads it afterwards), so the
    # cleanup is deferred to interpreter exit rather than a context manager. ~12 MB / 67 files —
    # irrelevant in a per-trial container, but this keeps the helper safe to call from a
    # longer-lived process (e.g. an offline batch re-grade over many trials).
    atexit.register(shutil.rmtree, dest, ignore_errors=True)
    n = 0
    for d in docs:
        name = (d or {}).get("doc") if isinstance(d, dict) else None
        if not name:
            continue
        res = _sidecar_call("read_policy", {"doc": name})
        if not isinstance(res, dict) or "text" not in res:
            continue
        try:
            (dest / Path(name).name).write_text(
                _strip_line_prefixes(res["text"], int(res.get("line_start") or 1))
            )
            n += 1
        except OSError:
            continue
    return str(dest) if n else None


def _resolve_policy_corpus() -> tuple[str | None, str]:
    """(corpus_dir, source). Prefers a real local mount; falls back to the sidecar."""
    local = os.environ.get("POLICY_CORPUS_DIR", "/workspace/policy_corpus")
    p = Path(local)
    if p.is_dir() and any(p.glob("*.md")):
        return local, "local"
    fetched = _materialize_policy_corpus()
    if fetched:
        return fetched, "sidecar"
    return None, "unavailable"


# ── deterministic patient-evidence grounding (no LLM, no creds) ────────────────────────────
# In-trial (deterministic, stable inputs): pure set/string work over
# evidence.jsonl, which test.sh has already produced from the trajectory. Running them here means
# they cover EVERY trial instead of the hand-picked subset the offline CLIs reach, and they cannot
# skip on missing creds because they need none.
#
# Report-side ID extraction drops compound prefixes; the evidence side (evidence.py) keeps them.
# That asymmetry is deliberate and must match eval/metrics/grounding/insight_grounding.py:
# a poe_id like 10001217-107 in the report counts once, not also as a bare subject_id the report
# never cited; but in the evidence a subject_id may only ever appear inside a compound, and a
# report citing it bare is still legitimately grounded.
_TS_RX = re.compile(r"\b\d{4}-\d{2}(?:-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?)?\b")
_ID_HYPHEN_RX = re.compile(r"\b\d{6,}-(?:[A-Z]{1,4}-)?\d+\b")
_ID_INT_RX = re.compile(r"\b\d{6,}\b")


def _cited_ids(report: str) -> set[str]:
    """Record-ID atoms the REPORT cites (compound prefixes dropped — see above)."""
    text = _TS_RX.sub(" ", report or "")
    ids = {m.group() for m in _ID_HYPHEN_RX.finditer(text)}
    text = _ID_HYPHEN_RX.sub(" ", text)
    ids |= {m.group() for m in _ID_INT_RX.finditer(text)}
    return ids


def _load_evidence(path: str | None) -> list[dict] | None:
    """Parse evidence.jsonl. None when absent/unusable (metrics then omitted, not zeroed — a
    missing artifact is 'not measured', and scoring it 0 would look like total fabrication)."""
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    recs: list[dict] = []
    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            recs.append(json.loads(line))
        except ValueError:
            continue
    # [] is NOT None: an existing file with zero records means the agent made no MIMIC call at all,
    # which is the single most important thing to surface. Collapsing it to None routed it to
    # "grounding_skipped" and omitted every evidence_* key, so a run that touched no data looked
    # like a run that was never measured — and the surviving means were biased upward.
    return recs


def score_grounding(report: str, evidence: list[dict]) -> tuple[dict, dict]:
    """(reward, detail) for the deterministic grounding axis.

    id_grounding = |cited IDs seen in retrieved evidence| / |cited IDs| — a fabrication floor: an
    ID cannot be computed, so one absent from every tool result was invented. Undefined (omitted)
    when the report cites no IDs at all.
    """
    # TRUST BOUNDARY. T1 is only a fabrication floor because an id cannot be COMPUTED — it either
    # came back from a tool or was invented. That holds for `mimic` records (the payload is the
    # sidecar's response; the agent cannot inject text into it) but NOT for:
    #   * `exec_output` — codex code mode, where the observation is the agent's own script stdout.
    #     A script that merely prints "subject_id 99999999" would otherwise mint grounding credit.
    #   * `subagent`   — a model-written summary, which can hallucinate an id the parent then cites.
    # So ids from those records are pooled SEPARATELY and never counted as grounding evidence.
    trusted: set[str] = set()
    agent_authored: set[str] = set()
    status = {"ok": 0, "error": 0, "auth_error": 0, "empty": 0, "unattributed": 0, "spilled": 0}
    n_subagent = 0
    for r in evidence:
        # Only records that actually returned data. An ERROR payload can echo the subject_id back
        # ("no rows for subject 10001217"), which would ground a citation on a failed call.
        if r.get("status") in ("ok", "unattributed", "spilled"):
            ids = set(r.get("record_ids") or [])
            if r.get("kind") in ("exec_output", "subagent"):
                agent_authored |= ids
            else:
                trusted |= ids
        st = r.get("status")
        if st in status:
            status[st] += 1
        n_subagent += 1 if r.get("kind") == "subagent" else 0
    pool = trusted
    cited = _cited_ids(report)
    grounded = cited & trusted
    # Cited ids that appear ONLY in agent-authored text. Not evidence — but not fabrication proof
    # either, since in code mode the real rows also arrive via stdout. Reported, never credited.
    unverifiable = sorted((cited & agent_authored) - trusted)
    ungrounded = sorted(cited - trusted - agent_authored)

    reward: dict[str, float | int] = {
        "evidence_calls": len(evidence),
        "evidence_calls_ok": status["ok"],
        "evidence_calls_error": status["error"],
        "evidence_calls_auth_error": status["auth_error"],
        "evidence_calls_spilled": status["spilled"],
        "evidence_calls_empty": status["empty"],
        "evidence_calls_unattributed": status["unattributed"],
        "evidence_record_ids": len(pool),
        # >0 ⇒ the id pool is a LOWER BOUND: a sub-agent's own tool results live outside this
        # trajectory, so grounding_id_precision may under-report. Read it with this in mind.
        "evidence_subagent_summaries": n_subagent,
        "grounding_ids_cited": len(cited),
        "grounding_ids_grounded": len(grounded),
        "grounding_ids_agent_authored_only": len(unverifiable),
        "grounding_pool_trusted_ids": len(trusted),
    }
    # Report the precision only when there IS a trusted pool to measure against. A code-mode trial
    # has no tool-authored observations at all, so a 0.0 would read as mass fabrication and a 1.0
    # (crediting stdout) would be meaningless — omit it and say why instead.
    if cited and trusted:
        reward["grounding_id_precision"] = round(len(grounded) / len(cited), 3)
    elif cited:
        reward["grounding_id_untrustworthy_pool"] = 1
    detail = {
        "n_evidence_record_ids": len(pool),
        "cited_ids": sorted(cited),
        # The actionable part: which cited IDs appear in NO tool result.
        "ungrounded_cited_ids": ungrounded[:50],
        "agent_authored_only_cited_ids": unverifiable[:50],
        "call_status": status,
    }
    return reward, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-file", required=True, help="Path to agent's report.md")
    ap.add_argument("--rubrics-file", required=True, help="Bundled rubrics.json")
    ap.add_argument("--trajectory-file", default="", help="Optional agent tool-call trajectory")
    ap.add_argument(
        "--evidence-file",
        default="",
        help="Optional evidence.jsonl from evidence.py (deterministic grounding + call health)",
    )
    ap.add_argument("--output", required=True, help="Where to write reward.json")
    ap.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "openai/gpt-5.5"))
    ap.add_argument("--judge-api-key", default=os.environ.get("JUDGE_API_KEY", ""))
    args = ap.parse_args()

    # This verifier is DETERMINISTIC-ONLY: verdict match,
    # cited-ID grounding, and the deterministic policy items. No LLM call, so no creds, no
    # network, no per-trial judge cost, and nothing that can silently skip. The LLM-judged
    # metrics (process rubric, policy citation support) are scored afterwards from the persisted
    # artifacts by eval/metrics/{process,policy_support}.py.

    # Load the rubric bundle under the same always-write-reward.json contract as the grading
    # passes below: a missing/corrupt rubrics.json (older task, copy error) must still leave a
    # reward Harbor can read, not an uncaught crash with no reward file.
    try:
        with open(args.rubrics_file) as f:
            bundle = json.load(f)
    except (OSError, ValueError) as exc:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump({"score": 0.0, "judge_failed": 1, "rubrics_load_failed": 1}, f, indent=2)
        try:
            with open(Path(args.output).with_name("grades_detail.json"), "w") as f:
                json.dump(
                    {"error": f"could not load {args.rubrics_file!r}: {type(exc).__name__}: {exc}"},
                    f,
                    indent=2,
                )
        except OSError:
            pass
        print(f"ERROR: could not load rubrics file {args.rubrics_file!r}: {exc}", file=sys.stderr)
        return
    task_id = bundle.get("task_id", "unknown")
    # `case_id` is the pre-rename spelling of `scenario_id`. Accepted so the judge can still
    # re-grade a trial whose captured verifier/rubrics.json predates the rename (jobs/ holds
    # bundles that are not regenerated); build_tasks.py only ever writes `scenario_id`.
    scenario_id = bundle.get("scenario_id") or bundle.get("case_id", "unknown")
    task_prompt = bundle.get("prompt", "")
    ground_truth_label = bundle.get("ground_truth_label", "")
    process_rubrics = bundle.get("process_rubrics", [])
    policy_gold_docs = bundle.get("policy_gold_docs", [])
    policy_expected = bool(bundle.get("policy_expected", False))
    policy_rubrics = bundle.get("policy_rubrics", [])
    # NB _build_reference() is exported for the post-hoc process scorer
    # (eval/metrics/process.py calls it); nothing on this deterministic path uses it.

    report = _read_text(args.report_file)
    trajectory = _read_trajectory(args.trajectory_file)

    # reward.json is a flat dict of numbers (Harbor parses dict[str, float|int]);
    # verbose per-criterion grades go to the sidecar grades_detail.json.
    reward: dict[str, float | int] = {
        "report_present": 1 if report else 0,
        "report_chars": len(report),
        "trajectory_present": 1 if trajectory else 0,
        "trajectory_chars": len(trajectory),
        # Initialised so they are ALWAYS present, including on the early-exit path a no-report
        # trial takes. Setting them only when a judge actually runs makes a slim reward.json omit
        # them, and then `judge_failed == 1` matches nothing however many trials never reached a
        # judge -- a health check that cannot detect its own blind spot.
        "judge_failed": 0,
        "process_judge_failed": 0,
        "policy_judge_failed": 0,
    }
    detail: dict = {
        "task_id": task_id,
        "scenario_id": scenario_id,
        "judge_model": args.judge_model,
        "ground_truth_label": ground_truth_label,
        "report_chars": len(report),
        "trajectory_chars": len(trajectory),
    }

    # --- Outcome (PRIMARY reward): deterministic Yes/No/Escalate label match ---
    # This is the headline `score`, not the LLM process grade. It is a cheap, reproducible,
    # non-gameable regex extraction from the report's verdict line compared to the silver
    # label (case-insensitive). No LLM, so it never "fails" and can't be talked into a grade.
    # The label is scored ONLY here: no scenario rubric grades label correctness as an item, so
    # process_pct measures methodology and this measures the answer, with no double-count.
    # True 4-way match (the two indeterminate subtypes are distinct), with the sole concession
    # that a subtype-less 3-class ESCALATE ground truth (silver_patients.csv) accepts either
    # indeterminate. See _label_match.
    agent_label = _extract_outcome_label(report)
    gt_label = (ground_truth_label or "").strip().upper()
    outcome_correct = 1 if (agent_label is not None and _label_match(agent_label, gt_label)) else 0
    reward["outcome_label_parsed"] = 1 if agent_label is not None else 0
    reward["outcome_correct"] = outcome_correct
    reward["outcome_score"] = float(outcome_correct)
    reward["score"] = float(outcome_correct)  # PRIMARY reward
    # Diagnostic only — never folded into `score`. Lets an INDETERMINATE_LACK_OF_DATA verdict caused
    # by dead MIMIC tools be separated from one that reflects the patient's record (see
    # _ENV_DEGRADED_MARKER). Self-reported, so treat it as a lower bound on tool failure: an agent
    # that hangs or never writes a report emits no marker at all.
    reward["environment_degraded"] = 1 if _ENV_DEGRADED_MARKER.search(report) else 0
    detail["agent_label"] = agent_label or ""
    if agent_label is None:
        detail["outcome_note"] = (
            "no single unambiguous 4-class verdict parsed from the report's "
            "verdict line — scored incorrect"
        )
    elif not gt_label:
        detail["outcome_note"] = "no ground_truth_label bundled — outcome cannot be scored"

    # --- Patient-evidence grounding (deterministic, no LLM): cited-ID grounding + call health ---
    # Emitted as its own reward keys; NOT folded into `score`, same as policy grounding. Absent
    # evidence.jsonl -> keys omitted (not zeroed), so "not measured" stays distinguishable from
    # "measured as zero".
    evidence = _load_evidence(args.evidence_file)
    if evidence is not None:
        try:
            g_reward, g_detail = score_grounding(report, evidence)
            reward.update(g_reward)
            detail["grounding"] = g_detail
        except BaseException as exc:  # noqa: BLE001 — never let a metric cost the trial its reward
            detail["grounding_error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
    else:
        detail["grounding_skipped"] = "no evidence.jsonl (evidence.py did not run)"

    # --- Process rubric: NOT graded here ---
    # Graded post-hoc by eval/metrics/process.py instead. Keeping the LLM out of the trial means a
    # rubric edit is a re-grade rather than a re-sweep, judge latency stays out of the trial budget,
    # and a missing JUDGE_* credential cannot silently drop the process score from a whole run.
    # The rubric is still bundled into rubrics.json for the post-hoc scorer.
    if process_rubrics:
        detail["process_skipped"] = "by design — graded post-hoc by benchmark/eval/grade.py"
    reward["process_judge_failed"] = 0

    # --- Policy grounding (SEPARATE axis): citation correctness + condition-aware outcome ---
    # Deterministic (corpus-existence, span validity, file-level P/R/F1) plus LLM citation-support
    # and the 3-class outcome rubric. Scored via the shared core and reported as its OWN axis: the
    # policy metrics are emitted as separate reward keys and are NOT folded into the primary
    # `score` (deliberately — it keeps the headline number interpretable). See
    # _template/tests/policy_scoring.py.
    # `policy_expected` is bundled at BUILD time (policy-ON + the scenario has gold docs) and is the
    # authoritative condition — do NOT re-derive it from a local filesystem probe. The corpus is
    # mounted into the sidecar, not here, so that probe fails on every policy-ON docker trial and
    # silently flipped the whole grade to the policy-OFF branch ("expect no citations"), which
    # scores every real citation as fabricated and drops file-level P/R/F1 entirely.
    corpus_dir, corpus_source = _resolve_policy_corpus()
    policy_expected_eff = policy_expected
    reward["policy_corpus_available"] = 1 if corpus_dir else 0
    detail["policy_corpus_source"] = corpus_source
    if policy_expected and not corpus_dir:
        # Fail LOUDLY. Scoring the on-condition without a corpus produces confidently wrong
        # numbers (0 in-corpus, everything fabricated), which is worse than no numbers.
        reward["policy_expected"] = 1
        reward["policy_corpus_unavailable"] = 1
        reward["policy_judge_failed"] = 1
        detail["policy_error"] = (
            "policy_expected=True but no corpus could be resolved: POLICY_CORPUS_DIR "
            f"({os.environ.get('POLICY_CORPUS_DIR', '/workspace/policy_corpus')}) is empty/absent "
            "in this container and the sidecar at MIMIC_TOOLS_URL did not serve list_policy_docs / "
            "read_policy. Policy grounding NOT scored."
        )
        print(f"[judge] POLICY NOT SCORED: {detail['policy_error']}", file=sys.stderr)
    elif report and (policy_gold_docs or corpus_dir):
        try:
            from policy_scoring import score_policy_grounding

            # The scorer reads LLM judge creds from the environment (JUDGE_*) itself —
            # the same vars task.toml injects and judge.py uses — so we don't thread them in. With
            # creds present it runs the policy-relevance OUTCOME rubric (authored policy_rubrics,
            # LLM-judged on policy-ON) and the citation-support check (toggle POLICY_SUPPORT_CHECK);
            # deterministic citation evals run regardless.
            # corpus_dir is None only on the policy-OFF path here (the ON path fails loudly
            # above); "" keeps Path() happy and correctly resolves nothing, which is the
            # off-condition semantics — with no corpus, any citation IS unresolvable.
            p_reward, p_detail = score_policy_grounding(
                report,
                corpus_dir or "",
                policy_gold_docs,
                policy_expected_eff,
                policy_rubrics=policy_rubrics,
                prompt=task_prompt,
            )
            reward.update(p_reward)
            detail["policy"] = p_detail
            reward["policy_judge_failed"] = 0
        except BaseException as exc:  # noqa: BLE001
            detail["policy_error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
            detail["policy_traceback"] = traceback.format_exc(limit=4)
            reward["policy_judge_failed"] = 1
            print(f"[judge] policy grounding FAILED: {exc}", file=sys.stderr)
    else:
        detail["policy_skipped"] = "no report" if not report else "no gold docs and no corpus"

    # Policy grounding is reported as a SEPARATE axis — its metrics (policy_outcome_pct, citation
    # correctness, file-level P/R/F1) are emitted as their own reward keys above and are NOT folded
    # into the primary `score`, which stays the deterministic outcome-label match. Team decision on
    # deliberate: it keeps the headline score interpretable.

    # `judge_failed` flags only the (secondary) LLM process pass; the primary outcome score
    # is deterministic and always produced.
    reward["judge_failed"] = int(reward.get("process_judge_failed", 0) == 1)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(reward, f, indent=2)
    detail_path = Path(args.output).with_name("grades_detail.json")
    with open(detail_path, "w") as f:
        json.dump(detail, f, indent=2)
    print(f"Wrote {args.output}: score={reward['score']:.3f}  (detail → {detail_path.name})")


if __name__ == "__main__":
    main()
