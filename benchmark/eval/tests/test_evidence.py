"""Tests for _template/tests/evidence.py — the per-harness trajectory→evidence.jsonl extractor.

Every failure mode below is SILENT: extraction yields zero calls and the run reads as "the agent
touched no data" rather than raising. That is what these tests exist to catch.

  1. opencode names its tools ``mimic_get_note`` (bare prefix). An extractor that strips only
     ``mcp__mimic__`` / ``mcp_mimic_`` returns nothing for the whole harness.
  2. codex "code mode" issues ONE ``exec`` call per step and drives MIMIC from inside a script.
     Without exec parsing, those systems also extract zero calls.
  3. Policy-document text is full of 6-digit reference numbers that the record-ID regex cannot
     distinguish from a ``subject_id``. Pooling them would let a report cite a FABRICATED id and be
     scored grounded because some PDF contains that number — silently weakening T1's whole purpose.

Each is cheap to assert and none was caught by review, so they are asserted here. Fixtures are
synthetic minimal ATIF trajectories (no job dirs, no network, no MIMIC), so this runs anywhere.

    python benchmark/eval/tests/test_evidence.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from clinicare_core.paths import bootstrap

HC = Path(__file__).resolve().parents[2]

bootstrap(__file__, "container_tests", "eval")  # "eval" so `core.trajectory` resolves below
import evidence as EV  # noqa: E402

_fails: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    print(
        f"  {'ok  ' if cond else 'FAIL'}  {label}"
        + (f"   [{detail}]" if detail and not cond else "")
    )
    if not cond:
        _fails.append(label)


def traj(*steps: dict) -> dict:
    return {"schema_version": "1", "steps": list(steps)}


def step(tool: str, args: dict, content, call_id: str = "c1", step_id: int = 1) -> dict:
    """One ATIF step: a tool call plus its paired observation result."""
    return {
        "step_id": step_id,
        "tool_calls": [{"function_name": tool, "arguments": args, "tool_call_id": call_id}],
        "observation": {"results": [{"content": content, "source_call_id": call_id}]},
    }


ROWS = json.dumps([{"subject_id": 10001217, "hadm_id": 20449658, "value": 0.9}])


def main() -> int:
    print("== 1. tool-name prefixes: every harness dialect must normalize ==")
    for raw, want in [
        ("mcp__mimic__get_note", "get_note"),  # claude-code
        ("mcp_mimic_get_note", "get_note"),  # gemini-cli
        ("mimic_get_note", "get_note"),  # opencode  <-- regression #1
        ("get_note", "get_note"),  # codex (bare)
        ("Bash", "Bash"),  # not a MIMIC tool
    ]:
        check(
            f"normalize {raw!r} -> {want!r}", EV.normalize_tool(raw) == want, EV.normalize_tool(raw)
        )
    check("opencode-prefixed tool is recognized as MIMIC", EV.is_mimic_tool("mimic_get_note"))
    check("harness tool is not", not EV.is_mimic_tool("Write"))

    print("\n== 2. a typed MIMIC call yields one record with rows + ids ==")
    recs = list(
        EV.iter_evidence(traj(step("mcp__mimic__get_lab_timeline", {"subject_id": 1}, ROWS)))
    )
    check("one record", len(recs) == 1, str(len(recs)))
    if recs:
        r = recs[0]
        check("tool normalized", r["tool"] == "get_lab_timeline", r["tool"])
        check("kind=mimic", r["kind"] == "mimic", r["kind"])
        check("status=ok", r["status"] == "ok", r["status"])
        check("n_rows parsed", r["n_rows"] == 1, str(r["n_rows"]))
        check(
            "record ids extracted",
            "10001217" in r["record_ids"] and "20449658" in r["record_ids"],
            str(r["record_ids"]),
        )

    print("\n== 3. the artifact records the CALL, never a tool->table mapping ==")
    # tool->tables is revisable SCORING POLICY, not a raw fact: the consumer's map deliberately
    # zeroes get_data_availability, whose 16 registry tables would otherwise let one row-count call
    # score ~0.87 mean retrieval recall. Freezing it per trial would make a later gold correction
    # unrecomputable.
    recs = list(EV.iter_evidence(traj(step("run_sql", {"query": "SELECT * FROM labevents"}, ROWS))))
    check(
        "no `tables` field in the artifact",
        bool(recs) and "tables" not in recs[0],
        str(sorted(recs[0])) if recs else "-",
    )
    check(
        "run_sql keeps its query so the consumer can map it",
        bool(recs) and "labevents" in str(recs[0]["args"].get("query", "")),
    )

    print("\n== 4. policy-tool output must contribute NO record ids (regression #3) ==")
    # A guideline passage whose reference numbers look exactly like subject_ids.
    policy_text = "See refs 101759, 102366 and section 118272 of the KDIGO guideline."
    recs = list(
        EV.iter_evidence(traj(step("mcp__mimic__search_policy", {"q": "aki"}, policy_text)))
    )
    check("policy call is recorded", len(recs) == 1 and recs[0]["tool"] == "search_policy")
    if recs:
        check("kind=policy", recs[0]["kind"] == "policy", recs[0]["kind"])
        check(
            "NO record ids from policy text",
            recs[0]["record_ids"] == [],
            str(recs[0]["record_ids"]),
        )
        check("policy call carries no ids either way", recs[0]["record_ids"] == [])

    print("\n== 5. codex exec scaffold: calls recovered from the script (regression #2) ==")
    script = (
        "const a = await mcp__mimic__get_imaging_studies({subject_id: 1});\n"
        "const q = `SELECT charttime FROM labevents WHERE itemid = 50912`;\n"
        "const b = await mcp__mimic__run_sql({query: q});\n"
    )
    recs = list(EV.iter_evidence(traj(step("exec", {"input": script}, ROWS))))
    tools = [r["tool"] for r in recs]
    check("imaging call recovered", "get_imaging_studies" in tools, str(tools))
    check("run_sql recovered", "run_sql" in tools, str(tools))
    sql = next((r for r in recs if r["tool"] == "run_sql"), None)
    check(
        "run_sql query recovered from the script literal",
        bool(sql) and "labevents" in str(sql["args"].get("query", "")),
        str(sql["args"]) if sql else "-",
    )
    check(
        "script-derived calls are flagged",
        all(r.get("from_exec_script") for r in recs if r["tool"] != "exec"),
    )
    check(
        "script-derived calls are status=unattributed (NOT 'empty')",
        all(r["status"] == "unattributed" for r in recs if r.get("from_exec_script")),
    )
    out = next((r for r in recs if r["kind"] == "exec_output"), None)
    check("exec output captured as its own record", out is not None)
    check(
        "ids come from the exec OUTPUT, not the script",
        bool(out) and "10001217" in out["record_ids"],
        str(out["record_ids"]) if out else "-",
    )

    print("\n== 6. call health: an error result is not mistaken for an empty one ==")
    for content, want in [
        # auth failures are tagged distinctly from other errors — they are the infra signal
        ("<untrusted_context>\nERROR: 401: Unauthorized\n</untrusted_context>", "auth_error"),
        ("[]", "empty"),
        ("", "empty"),
        (ROWS, "ok"),
    ]:
        recs = list(
            EV.iter_evidence(
                traj(step("mcp__mimic__run_sql", {"query": "SELECT 1 FROM patients"}, content))
            )
        )
        got = recs[0]["status"] if recs else "(none)"
        check(f"status({content[:26]!r}) == {want}", got == want, got)
    # A long legitimate payload that merely CONTAINS the word "error" must stay ok.
    noisy = json.dumps(
        [{"text": "medication error documented in note", "subject_id": 10001217}] * 60
    )
    recs = list(EV.iter_evidence(traj(step("mcp__mimic__get_note", {}, noisy))))
    check(
        "long payload mentioning 'error' is still ok",
        recs and recs[0]["status"] == "ok",
        recs[0]["status"] if recs else "-",
    )

    print("\n== 7. envelope unwrapping across harnesses ==")
    for label, content in [
        ("claude nested {'type':'text'}", json.dumps({"type": "text", "text": ROWS})),
        ("gemini <untrusted_context>", f"<untrusted_context>\n{ROWS}\n</untrusted_context>"),
        ("codex 'Wall time:' prefix", f"Wall time: 1.2 seconds\nOutput:\n{ROWS}"),
    ]:
        recs = list(
            EV.iter_evidence(
                traj(step("mcp__mimic__run_sql", {"query": "SELECT 1 FROM patients"}, content))
            )
        )
        ids = recs[0]["record_ids"] if recs else []
        check(f"{label} -> ids recovered", "10001217" in ids, str(ids))

    print("\n== 8. summary counts ==")
    recs = list(
        EV.iter_evidence(
            traj(
                step("mcp__mimic__get_note", {}, ROWS, call_id="a", step_id=1),
                step("mcp__mimic__search_policy", {}, "refs 101759", call_id="b", step_id=2),
            )
        )
    )
    summ = EV.summarize(recs)
    check("2 calls", summ["evidence_calls"] == 2, str(summ["evidence_calls"]))
    check("1 policy call", summ["evidence_calls_policy"] == 1, str(summ["evidence_calls_policy"]))
    check(
        "ids counted from the mimic call only",
        summ["evidence_record_ids"] == 2,
        str(summ["evidence_record_ids"]),
    )

    print("\n== 9c. TRUST BOUNDARY: agent-authored text must not mint grounding credit ==")
    import importlib.util as _il

    _js = _il.spec_from_file_location("_t_judge", HC / "_template" / "tests" / "judge.py")
    _J = _il.module_from_spec(_js)
    sys.modules["_t_judge"] = _J
    _js.loader.exec_module(_J)

    # A code-mode script whose only action is printing a fabricated id.
    faked = traj(
        {
            "step_id": 1,
            "tool_calls": [
                {
                    "function_name": "exec",
                    "arguments": {"input": 'console.log("subject_id 99999999")'},
                    "tool_call_id": "e1",
                }
            ],
            "observation": {
                "results": [{"content": "subject_id 99999999", "source_call_id": "e1"}]
            },
        }
    )
    recs = list(EV.iter_evidence(faked))
    check("exec stdout is tagged kind=exec_output", any(r["kind"] == "exec_output" for r in recs))
    rw, det = _J.score_grounding("The patient 99999999 had AKI.", recs)
    check(
        "a fabricated id printed by the script gets NO grounding credit",
        rw["grounding_ids_grounded"] == 0,
        str(rw["grounding_ids_grounded"]),
    )
    check(
        "it is reported as agent-authored-only, not silently dropped",
        rw["grounding_ids_agent_authored_only"] == 1,
        str(rw),
    )
    check(
        "precision is OMITTED (no trusted pool) rather than 1.0 or 0.0",
        "grounding_id_precision" not in rw and rw.get("grounding_id_untrustworthy_pool") == 1,
        str(sorted(rw)),
    )
    # Same for a sub-agent summary, which is model-written text.
    sub2 = traj(
        {
            "step_id": 1,
            "tool_calls": [{"function_name": "Agent", "arguments": {}, "tool_call_id": "s9"}],
            "observation": {
                "results": [{"content": "subject_id 88888888", "source_call_id": "s9"}]
            },
        }
    )
    rw2, _ = _J.score_grounding("Cited 88888888.", list(EV.iter_evidence(sub2)))
    check("sub-agent summary ids are also not credited", rw2["grounding_ids_grounded"] == 0)
    # A real tool observation still grounds normally.
    rw3, _ = _J.score_grounding(
        "Cited 10001217.", list(EV.iter_evidence(traj(step("mcp__mimic__get_note", {}, ROWS))))
    )
    check("tool-authored ids DO ground", rw3["grounding_ids_grounded"] == 1)
    check("and precision is reported", rw3.get("grounding_id_precision") == 1.0, str(rw3))

    print("\n== 9d. exec refs must be live CALLS, not mentions (greptile P1) ==")
    # Agents build introspection arrays of tool NAMES; a bare-name match credited every tool listed,
    # and retrieval coverage is a set union over tables so one such line can flip a case.
    got = EV.exec_script_calls(
        'const names = ["mcp__mimic__list_policy_docs","mcp__mimic__get_admission_details"];\n'
        "// TODO: mcp__mimic__get_note({})\n"
        "/* mcp__mimic__get_procedures({}) */\n"
        "await mcp__mimic__list_icu_stays({subject_id:1});"
    )
    names = [t for t, _ in got]
    check("names in an array are NOT counted", "list_policy_docs" not in names, str(names))
    check("name in a // comment is NOT counted", "get_note" not in names, str(names))
    check("name in a /* */ block is NOT counted", "get_procedures" not in names, str(names))
    check("the one real call IS counted", names == ["list_icu_stays"], str(names))
    # run_sql's query lives in a string literal, which comment/string stripping must not lose
    got = EV.exec_script_calls(
        "const q = `SELECT x FROM labevents`; await mcp__mimic__run_sql({query:q});"
    )
    check(
        "run_sql still recovered with its query",
        got and got[0][0] == "run_sql" and "labevents" in got[0][1].get("query", ""),
        str(got),
    )

    print("\n== 9e. harness output-spill is a SUCCESS, not an error (found by smoke trial) ==")
    notice = (
        "Error: result (71,480 characters across 1 line) exceeds maximum allowed tokens. "
        "Output has been saved to /logs/agent/sessions/x/tool-results/mcp-mimic-search_policy-1.txt.\n"
        "Format: Plain text"
    )
    st = EV._status(notice, EV._row_count(notice))
    check("spill notice -> 'spilled', not 'error'", st == "spilled", st)
    check(
        "auth failure is tagged distinctly",
        EV._status("ERROR: 401: Unauthorized", None) == "auth_error",
        EV._status("ERROR: 401: Unauthorized", None),
    )
    check(
        "a non-auth failure stays 'error'",
        EV._status("ERROR: 404: Unknown tool: get_data_availability", None) == "error",
        EV._status("ERROR: 404: Unknown tool: get_data_availability", None),
    )
    # the trailing period after the filename must not defeat path resolution
    m = EV._SPILL_RX.search(notice)
    check("spill path captured", bool(m), str(m))
    check(
        "trailing '.' stripped when resolving",
        EV._resolve_spill(m.group(1), None) is None and m.group(1).endswith(".txt."),
        str(m.group(1)),
    )

    print("\n== 9b. the prefix list has ONE owner (drift here silently zeroes a harness) ==")
    import importlib.util

    def _load(rel, name):
        spec = importlib.util.spec_from_file_location(name, HC / rel)
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
        return m

    _traj = _load("eval/core/trajectory.py", "_t_traj")
    check(
        "eval/core/trajectory.py agrees with evidence.py",
        tuple(_traj.MCP_PREFIXES) == tuple(EV._MCP_PREFIXES),
        f"{_traj.MCP_PREFIXES} vs {EV._MCP_PREFIXES}",
    )
    _sc = _load("eval/report/score_clinicare.py", "_t_sc")
    check(
        "eval/report/score_clinicare.py agrees with evidence.py",
        tuple(_sc._MCP_PREFIXES) == tuple(EV._MCP_PREFIXES),
        f"{_sc._MCP_PREFIXES} vs {EV._MCP_PREFIXES}",
    )
    check("opencode prefix present in the owner", "mimic_" in EV._MCP_PREFIXES)

    print("\n== 9. regressions found in review ==")
    for payload, want in [
        ('[{"subject_id":10001217,"valuenum":500,"label":"Glucose"}]', "ok"),
        ('[{"subject_id":10001217,"text":"Patient denied chest pain."}]', "ok"),
        ('[{"subject_id":10001217,"dilution":403}]', "ok"),
        ("ERROR: 401: Unauthorized", "auth_error"),
        ("Access denied", "error"),
    ]:
        got = EV._status(payload, EV._row_count(payload))
        check(f"clinical-vs-error status({payload[:30]!r}) == {want}", got == want, got)
    sub = traj(
        {
            "step_id": 1,
            "tool_calls": [{"function_name": "Agent", "arguments": {}, "tool_call_id": "s1"}],
            "observation": {
                "results": [{"content": "found subject_id 10001217", "source_call_id": "s1"}]
            },
        }
    )
    recs = list(EV.iter_evidence(sub))
    check("sub-agent summary recorded", bool(recs) and recs[0]["kind"] == "subagent")
    check("sub-agent ids pooled", bool(recs) and "10001217" in recs[0]["record_ids"])
    check(
        "summary flags the pool as incomplete",
        EV.summarize(recs)["evidence_subagent_summaries"] == 1,
    )
    recs = list(EV.iter_evidence(traj(step("wait", {}, ROWS))))
    check("async `wait`-step output captured", bool(recs) and recs[0]["kind"] == "exec_output")
    check("`wait`-step ids pooled", bool(recs) and "10001217" in recs[0]["record_ids"])
    check("recognition survives a missing registry", len(EV._FALLBACK_TOOLS) > 20)
    check("registry-load state is reported", "evidence_registry_loaded" in EV.summarize([]))

    # Both recognizers keep a hand-written fallback for when `mimic_tools` is not importable.
    # A fallback that drifts behind the registry fails silently: the tools it omits are treated
    # as harness noise, their rows never reach the evidence pool, and record IDs the agent really
    # did retrieve are then scored as fabricated. Assert each still matches the live surface.
    try:
        from mimic_tools.tool_registry import POLICY_TOOLS, TOOLS

        live, policy = set(TOOLS), set(POLICY_TOOLS)
        ev_known = set(EV._FALLBACK_TOOLS) | set(EV._POLICY_TOOLS)
        check(
            "evidence.py fallback covers the whole registry",
            ev_known == live,
            f"drift: {sorted(ev_known ^ live)}",
        )

        from core.trajectory import _FALLBACK_MIMIC_TOOLS, MIMIC_TOOLS

        check(
            "trajectory.py fallback covers the patient-data surface",
            set(_FALLBACK_MIMIC_TOOLS) == live - policy,
            f"drift: {sorted(set(_FALLBACK_MIMIC_TOOLS) ^ (live - policy))}",
        )
        check(
            "trajectory.py keeps policy tools out of the patient-evidence pool",
            not (set(MIMIC_TOOLS) & policy),
        )
    except ImportError:  # no registry to compare against — not a failure
        print("  skip  fallback/registry parity (mimic_tools not importable)")

    print()
    if _fails:
        print(f"{len(_fails)} FAILURE(S): " + "; ".join(_fails))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
