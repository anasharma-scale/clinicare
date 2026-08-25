"""Smoke test for the canonical MIMIC tool surface.

Exercises every tool in tools.py against a data-rich patient. Because the tools
degrade to [] on schema errors (see _safe_rows), this is how we catch silent
mismatches: a tool that returns 0 rows for a patient who *should* have data is
suspect. It bootstraps real ids (hadm_id, stay_id, ED stay_id, note_id) from the
list_* tools, then feeds them into the id-scoped tools.

    uv run python smoke_test.py [subject_id]
"""

from __future__ import annotations

import sys

from mimic_tools import tools

SUBJECT_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 10001217


def _summarize(result) -> str:
    if result is None:
        return "None"
    if isinstance(result, list):
        return f"{len(result)} row(s)" + (f"  e.g. keys={list(result[0])}" if result else "")
    if isinstance(result, dict):
        if "rows" in result and "columns" in result:
            return f"sql: {result['returned']} row(s), truncated={result['truncated']}"
        return f"dict keys={list(result)}"
    return repr(result)[:80]


def _run(label: str, fn, *args, **kwargs):
    try:
        res = fn(*args, **kwargs)
        print(f"  [ok]  {label}: {_summarize(res)}")
        return res
    except Exception as exc:  # noqa: BLE001 - smoke test wants every failure surfaced
        print(f"  [ERR] {label}: {type(exc).__name__}: {exc}")
        return None


def main() -> None:
    sid = SUBJECT_ID
    print(f"=== smoke test: subject_id={sid} ===\n")

    print("patient / encounters")
    _run("get_patient_demographics", tools.get_patient_demographics, sid)
    admissions = _run("list_admissions", tools.list_admissions, sid) or []
    icu_stays = _run("list_icu_stays", tools.list_icu_stays, sid) or []
    ed_visits = _run("list_ed_visits", tools.list_ed_visits, sid) or []
    notes = _run("list_notes", tools.list_notes, sid) or []

    # Bootstrap ids from the list tools.
    hadm_id = admissions[0]["hadm_id"] if admissions else None
    icu_stay_id = icu_stays[0]["stay_id"] if icu_stays else None
    ed_stay_id = ed_visits[0]["stay_id"] if ed_visits else None
    note_id = notes[0]["note_id"] if notes else None
    print(
        f"\n  bootstrapped: hadm_id={hadm_id} icu_stay_id={icu_stay_id} "
        f"ed_stay_id={ed_stay_id} note_id={note_id}\n"
    )

    print("encounter detail")
    if hadm_id:
        _run("get_admission_details", tools.get_admission_details, hadm_id)
    if icu_stay_id:
        _run("get_icu_stay_details", tools.get_icu_stay_details, icu_stay_id)
    if ed_stay_id:
        _run("get_ed_visit_details", tools.get_ed_visit_details, ed_stay_id)

    print("\nmeds")
    _run("get_medication_reconciliation", tools.get_medication_reconciliation, sid, hadm_id=hadm_id)
    _run("get_medication_administered", tools.get_medication_administered, sid, hadm_id=hadm_id)
    _run("get_medication_prescribed", tools.get_medication_prescribed, sid, hadm_id=hadm_id)

    print("\ntimelines")
    _run("get_lab_timeline (creatinine)", tools.get_lab_timeline, sid, lab_name="creatinine")
    if icu_stay_id:
        _run(
            "get_vitals_timeline (HR)",
            tools.get_vitals_timeline,
            sid,
            metric="HR",
            stay_id=icu_stay_id,
        )
        _run("get_fluid_balance", tools.get_fluid_balance, sid, icu_stay_id)

    print("\ndiagnoses / procedures / imaging / micro")
    _run("get_diagnosis_history", tools.get_diagnosis_history, sid)
    _run("get_procedures", tools.get_procedures, sid)
    _run("get_imaging_studies", tools.get_imaging_studies, sid)
    _run("get_microbiology_results", tools.get_microbiology_results, sid)

    print("\norders / notes")
    _run("list_orders", tools.list_orders, sid, hadm_id=hadm_id)
    if note_id:
        _run("get_note", tools.get_note, note_id)
    _run("search_notes (the)", tools.search_notes, sid, "the")

    print("\nrun_sql")
    _run(
        "run_sql",
        tools.run_sql,
        "SELECT COUNT(*) AS n FROM icustays WHERE subject_id = " + str(sid),
    )


if __name__ == "__main__":
    main()
