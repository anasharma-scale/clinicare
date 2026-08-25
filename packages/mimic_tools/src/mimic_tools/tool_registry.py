"""Declarative tool registry — the single source of truth for the tool surface as
*presented* (param specs, docs, form rendering), shared by both consumers:

  - app.py        the Streamlit contributor console
  - api.py        the FastAPI backend for the deployed webapp

It maps each tool name to its tools.py function plus a declarative param spec that
drives generic form rendering. Keeping this in one module (rather than inlined in the
UI) means the UI and the hosted API expose the identical surface — the same principle
that makes tools.py itself canonical between the console and the agent harness.

param kind: int | str | text | enum | enum_dynamic
  enum         -> options is a fixed list
  enum_dynamic -> source is a (column, table) pair; distinct values fetched at runtime

param flag `multi: True` -> the tool also accepts a LIST for this param, matching any of
  the values. Orthogonal to `kind`, so form rendering is unaffected: the Streamlit widgets
  key off `kind` alone and keep submitting a single value, which stays valid. Only the
  JSON-Schema surface (mcp_server._input_schema) and coerce_params widen.

Per-tool presentation metadata (all optional; consumed by the UIs, ignored by the agent):
  group    -> category bucket for the grouped tool selector (display order: GROUP_ORDER)
  tables   -> logical table(s) the tool reads, for deep-linking to the Tables/schema view
  example  -> a known-good param set, surfaced as a "load example" affordance and checked
              against the live backend by validate_examples.py
"""

from __future__ import annotations

import os
from typing import Any

from . import tools

# Display order for the grouped tool selector; a tool whose group is missing/unknown
# sorts last. Mirrors the functional sections in tools.py and the README tool table.
GROUP_ORDER = [
    "Patient & encounters",
    "Notes",
    "Timelines",
    "Medications",
    "Dx / procedures / imaging / micro",
    "ICU I/O",
    "Orders",
    "Policy docs",
    "SQL",
    "Manual",
]


def _time_window() -> list[dict]:
    """The inclusive [start_time, end_time] param pair, spelled identically on every
    timestamped tool so the agent never has to recall which tool names it differently.
    Returns fresh dicts per call, since consumers are free to annotate a param spec.

    Named *_time, not date_*, because these bounds are instants: the windows these tasks
    turn on are hours, not days (a 4 h post-anchor window, a 6 h bundle), and a name that
    says "date" invites a date-only value that silently rounds to midnight and moves the
    boundary. Accepts full timestamp precision; a bare date still works as midnight."""
    return [
        {
            "name": "start_time",
            "kind": "str",
            "required": False,
            "help": "YYYY-MM-DD[ HH:MM[:SS]] — inclusive lower bound",
        },
        {
            "name": "end_time",
            "kind": "str",
            "required": False,
            "help": "YYYY-MM-DD[ HH:MM[:SS]] — inclusive upper bound",
        },
    ]


TOOLS: dict[str, dict] = {
    "get_patient_demographics": {
        "fn": tools.get_patient_demographics,
        "doc": "Demographics + lifetime admission / ED / ICU counts.",
        "group": "Patient & encounters",
        "tables": ["patients", "admissions", "edstays", "icustays"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True, "help": "Patient subject_id"},
        ],
    },
    "get_data_availability": {
        "fn": tools.get_data_availability,
        "doc": (
            "Row count + first/last timestamp for every data stream this patient has, "
            "optionally scoped to one admission. Distinguishes 'this stream is empty for this "
            "patient' from 'my filter missed' — which an empty result from any other tool cannot "
            "— and shows where the record ends, without paging the data. rows = 0 is a genuine "
            "absence for the scope asked. Labs and notes can exist outside any admission, so "
            "passing hadm_id may legitimately zero a stream that has patient-level data."
        ),
        "group": "Patient & encounters",
        "tables": [t for t, _ in tools._AVAILABILITY_STREAMS],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {"name": "hadm_id", "kind": "int", "required": False},
        ],
    },
    "list_admissions": {
        "fn": tools.list_admissions,
        "doc": "All hospital admissions, chronological. Index for longitudinal reasoning.",
        "group": "Patient & encounters",
        "tables": ["admissions", "diagnoses_icd", "d_icd_diagnoses"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
        ],
    },
    "get_admission_details": {
        "fn": tools.get_admission_details,
        "doc": "One admission: dates/disposition, ED link, transfers, ICU stays, services, DRG.",
        "group": "Patient & encounters",
        "tables": ["admissions", "edstays", "transfers", "icustays", "services", "drgcodes"],
        "example": {"hadm_id": 29654838},
        "params": [
            {"name": "hadm_id", "kind": "int", "required": True},
        ],
    },
    "list_ed_visits": {
        "fn": tools.list_ed_visits,
        "doc": "ED visits for a patient, chronological.",
        "group": "Patient & encounters",
        "tables": ["edstays"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
        ],
    },
    "get_ed_visit_details": {
        "fn": tools.get_ed_visit_details,
        "doc": "ED summary: triage (chief complaint, acuity, vitals), vital trend, diagnoses, dispensed meds.",
        "group": "Patient & encounters",
        "tables": ["edstays", "ed_triage", "ed_vitalsign", "ed_diagnosis", "ed_pyxis"],
        "example": {"stay_id": 34592300},
        "params": [
            {"name": "stay_id", "kind": "int", "required": True, "help": "ED stay_id"},
        ],
    },
    "get_medication_reconciliation": {
        "fn": tools.get_medication_reconciliation,
        "doc": "Home meds captured at ED arrival (medrecon). Anchor with ED stay_id or hadm_id.",
        "group": "Medications",
        "tables": ["medrecon", "edstays"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {"name": "hadm_id", "kind": "int", "required": False},
            {"name": "stay_id", "kind": "int", "required": False, "help": "ED stay_id"},
        ],
    },
    "list_icu_stays": {
        "fn": tools.list_icu_stays,
        "doc": "ICU stays for a patient, optionally scoped to one admission.",
        "group": "Patient & encounters",
        "tables": ["icustays"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {"name": "hadm_id", "kind": "int", "required": False},
        ],
    },
    "get_icu_stay_details": {
        "fn": tools.get_icu_stay_details,
        "doc": "ICU stay summary: metadata + event-volume counts (chart, labs, meds, procedures, I/O).",
        "group": "Patient & encounters",
        "tables": [
            "icustays",
            "chartevents",
            "procedureevents",
            "inputevents",
            "outputevents",
            "labevents",
            "emar",
        ],
        "example": {"stay_id": 34592300},
        "params": [
            {"name": "stay_id", "kind": "int", "required": True, "help": "ICU stay_id"},
        ],
    },
    "get_lab_timeline": {
        "fn": tools.get_lab_timeline,
        "doc": "Chronological labs (ascending) with ref ranges, flags, comments. Common lab names (creatinine, sodium, lactate, …) resolve to precise Blood-only itemids; other free text falls back to a label substring that may span body fluids. lab_name accepts a list to return several labs in one call.",
        "group": "Timelines",
        "tables": ["labevents", "d_labitems"],
        "example": {"subject_id": 10001217, "lab_name": "creatinine"},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {
                "name": "lab_name",
                "kind": "str",
                "required": False,
                "multi": True,
                "help": "e.g. creatinine, potassium, lactate — or a list of them",
                "placeholder": "creatinine",
            },
            {"name": "hadm_id", "kind": "int", "required": False},
            {
                "name": "stay_id",
                "kind": "int",
                "required": False,
                "help": "ICU stay_id — scopes to that stay's [intime, outtime] window",
            },
            *_time_window(),
            {"name": "limit", "kind": "int", "required": False, "default": 1000},
        ],
    },
    "list_notes": {
        "fn": tools.list_notes,
        "doc": "Note metadata only (no text). Returns note_ids for get_note.",
        "group": "Notes",
        "tables": ["discharge_notes", "radiology_notes"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {"name": "hadm_id", "kind": "int", "required": False},
            {
                "name": "note_type",
                "kind": "enum",
                "required": False,
                "options": ["", "discharge", "radiology"],
            },
        ],
    },
    "get_note": {
        "fn": tools.get_note,
        "doc": "Full text of one note (contains `___` PHI placeholders).",
        "group": "Notes",
        "tables": ["discharge_notes", "radiology_notes"],
        "example": {"note_id": "10001217-DS-4"},
        "params": [
            {"name": "note_id", "kind": "str", "required": True},
        ],
    },
    "search_notes": {
        "fn": tools.search_notes,
        "doc": "Keyword search across a patient's notes → {items: [...]} of snippets (±120 chars). Can't prove absence.",
        "group": "Notes",
        "tables": ["discharge_notes", "radiology_notes"],
        "example": {"subject_id": 10001217, "keyword": "discharge"},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {"name": "keyword", "kind": "str", "required": True},
            {"name": "max_hits", "kind": "int", "required": False, "default": 50},
            {"name": "max_notes", "kind": "int", "required": False, "default": 100},
        ],
    },
    "get_vitals_timeline": {
        "fn": tools.get_vitals_timeline,
        "doc": "ICU vital signs over time (chartevents). metric: HR/BP/temperature/RR/SpO2/GCS, or a list of them. ICU-charted only — an encounter with no ICU stay returns nothing here.",
        "group": "Timelines",
        "tables": ["chartevents", "d_items"],
        "example": {"subject_id": 10001217, "metric": "HR"},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {
                "name": "metric",
                "kind": "enum",
                "required": False,
                "multi": True,
                "options": ["", "HR", "BP", "temperature", "RR", "SpO2", "GCS"],
            },
            {"name": "hadm_id", "kind": "int", "required": False},
            {"name": "stay_id", "kind": "int", "required": False},
            *_time_window(),
            {"name": "limit", "kind": "int", "required": False, "default": 5000},
        ],
    },
    "get_chart_timeline": {
        "fn": tools.get_chart_timeline,
        "doc": (
            "Any ICU charted (flowsheet) observation over time, by concept name or itemid — "
            "assessment scores, neuro checks, ventilator settings, lines, code status. The "
            "open-vocabulary counterpart to get_vitals_timeline, which is preferred for the six "
            "standard vitals because it maps each to a curated itemid set. Every row reports its "
            "itemid and label, so a concept search also serves as the itemid lookup. Requires a "
            "concept or itemid — chartevents is too large to return unfiltered."
        ),
        "group": "Timelines",
        "tables": ["chartevents", "d_items"],
        "example": {"subject_id": 10001217, "concept": "heart rhythm"},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {
                "name": "concept",
                "kind": "str",
                "required": False,
                "multi": True,
                "placeholder": "CAM-ICU",
                "help": "d_items label substring, or a list of them",
            },
            {
                "name": "itemid",
                "kind": "int",
                "required": False,
                "multi": True,
                "help": "exact chartevents itemid(s), instead of or alongside concept",
            },
            {"name": "hadm_id", "kind": "int", "required": False},
            {"name": "stay_id", "kind": "int", "required": False},
            *_time_window(),
            {"name": "limit", "kind": "int", "required": False, "default": 2000},
        ],
    },
    "get_icu_administrations": {
        "fn": tools.get_icu_administrations,
        "doc": (
            "ICU infusions and boluses per administration (inputevents): drug, amount, rate, "
            "start/end, status. Row-level counterpart to get_fluid_balance, which reports only "
            "per-category totals — use this when the timing, rate, or dose of an individual "
            "administration matters. ICU-only: floor and ED administrations are in EMAR "
            "(get_medication_administered), so a full admission's exposure may span both."
        ),
        "group": "ICU I/O",
        "tables": ["inputevents", "d_items"],
        "example": {"subject_id": 10001217, "stay_id": 34592300},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {
                "name": "drug_name",
                "kind": "str",
                "required": False,
                "multi": True,
                "placeholder": "insulin",
                "help": "d_items label substring, or a list of them",
            },
            {
                "name": "itemid",
                "kind": "int",
                "required": False,
                "multi": True,
                "help": "exact inputevents itemid(s), instead of or alongside drug_name",
            },
            {"name": "hadm_id", "kind": "int", "required": False},
            {"name": "stay_id", "kind": "int", "required": False, "help": "ICU stay_id"},
            *_time_window(),
            {"name": "limit", "kind": "int", "required": False, "default": 2000},
        ],
    },
    "get_medication_administered": {
        "fn": tools.get_medication_administered,
        "doc": "What was actually given (EMAR): drug, dose, route, time, event status. drug_name accepts a list; start_time/end_time bound administration time.",
        "group": "Medications",
        "tables": ["emar", "emar_detail"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {
                "name": "drug_name",
                "kind": "str",
                "required": False,
                "multi": True,
                "placeholder": "vancomycin",
                "help": "one drug name, or a list of them",
            },
            {"name": "hadm_id", "kind": "int", "required": False},
            {"name": "stay_id", "kind": "int", "required": False},
            *_time_window(),
            {"name": "limit", "kind": "int", "required": False, "default": 5000},
        ],
    },
    "get_medication_prescribed": {
        "fn": tools.get_medication_prescribed,
        "doc": "What was ordered (prescriptions): drug, dose, route, start/stop, doses/24h. drug_name accepts a list; start_time/end_time bound starttime, so an order that began before the window is not returned.",
        "group": "Medications",
        "tables": ["prescriptions"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {
                "name": "drug_name",
                "kind": "str",
                "required": False,
                "multi": True,
                "placeholder": "vancomycin",
                "help": "one drug name, or a list of them",
            },
            {"name": "hadm_id", "kind": "int", "required": False},
            {"name": "stay_id", "kind": "int", "required": False},
            *_time_window(),
            {"name": "limit", "kind": "int", "required": False, "default": 5000},
        ],
    },
    "get_diagnosis_history": {
        "fn": tools.get_diagnosis_history,
        "doc": "ICD diagnoses across admissions + ED visits, marked by source. keyword matches the title (case-insensitive substring).",
        "group": "Dx / procedures / imaging / micro",
        "tables": ["diagnoses_icd", "d_icd_diagnoses", "admissions", "ed_diagnosis", "edstays"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {"name": "keyword", "kind": "str", "required": False},
        ],
    },
    "get_procedures": {
        "fn": tools.get_procedures,
        "doc": (
            "Procedures from procedures_icd (hospital) + procedureevents (ICU). keyword matches "
            "label, and accepts a list. start_time/end_time filter the two halves at different "
            "granularity, because the sources differ: procedureevents.starttime is a real "
            "timestamp (filtered to the instant), while procedures_icd.chartdate is DATE-only "
            "(both bounds truncated to a date, matching any row on a day the window touches). So "
            "a narrow window may return an ICD procedure whose actual time is unknown and could "
            "fall outside it — included because the data can't rule it out. Only the ICU half "
            "supports a within-day timing claim; check `source` and the date-only `chartdate`."
        ),
        "group": "Dx / procedures / imaging / micro",
        "tables": ["procedures_icd", "d_icd_procedures", "procedureevents", "d_items"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {
                "name": "keyword",
                "kind": "str",
                "required": False,
                "multi": True,
                "help": "one label keyword, or a list of them",
            },
            *_time_window(),
        ],
    },
    "get_imaging_studies": {
        "fn": tools.get_imaging_studies,
        "doc": "Imaging studies from radiology reports (heuristic modality bucket + linked note_id). Scope is limited to imaging that produced a radiology report; studies without an associated report are not represented.",
        "group": "Dx / procedures / imaging / micro",
        "tables": ["radiology_notes", "radiology_detail"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {
                "name": "modality",
                "kind": "enum",
                "required": False,
                "multi": True,
                "options": ["", "CXR", "CT", "MRI", "US", "TEE"],
            },
            *_time_window(),
        ],
    },
    "get_microbiology_results": {
        "fn": tools.get_microbiology_results,
        "doc": "Microbiology in wide form — one row per (specimen, organism, antibiotic). specimen_type accepts a list; start_time/end_time bound collection charttime.",
        "group": "Dx / procedures / imaging / micro",
        "tables": ["microbiologyevents"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {
                "name": "specimen_type",
                "kind": "enum_dynamic",
                "required": False,
                "multi": True,
                "source": ["spec_type_desc", "microbiologyevents"],
                "help": "specimen type (e.g. blood culture, urine, sputum) — or a list of them",
            },
            *_time_window(),
        ],
    },
    "get_fluid_balance": {
        "fn": tools.get_fluid_balance,
        "doc": "ICU intake/output over a window with category breakdowns + totals (unit caveats apply).",
        "group": "ICU I/O",
        "tables": ["inputevents", "outputevents", "d_items"],
        "example": {"subject_id": 10001217, "stay_id": 34592300},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {"name": "stay_id", "kind": "int", "required": True},
            *_time_window(),
        ],
    },
    "list_orders": {
        "fn": tools.list_orders,
        "doc": "Provider-entered POE orders with poe_detail key/values attached. order_type accepts a list; start_time/end_time bound ordertime (entry time, not administration time).",
        "group": "Orders",
        "tables": ["poe", "poe_detail"],
        "example": {"subject_id": 10001217},
        "params": [
            {"name": "subject_id", "kind": "int", "required": True},
            {"name": "hadm_id", "kind": "int", "required": False},
            {
                "name": "order_type",
                "kind": "enum_dynamic",
                "required": False,
                "multi": True,
                "source": ["order_type", "poe"],
                "help": "order type (e.g. Medications, Lab, Nutrition) — or a list of them",
            },
            *_time_window(),
            {"name": "limit", "kind": "int", "required": False, "default": 2000},
        ],
    },
    "run_sql": {
        "fn": tools.run_sql,
        "doc": "Single read-only SELECT / WITH over the MIMIC views. Capped, with truncation flag.",
        "group": "SQL",
        "tables": [],
        "example": {
            "query": (
                "SELECT d.label AS lab, COUNT(*) AS n "
                "FROM labevents l JOIN d_labitems d USING (itemid) "
                "WHERE l.subject_id = 10001217 GROUP BY d.label ORDER BY n DESC"
            )
        },
        "params": [
            {
                "name": "query",
                "kind": "text",
                "required": True,
                "help": "Single read-only SELECT / WITH. Logical table names; CAST(... AS TIMESTAMP) for time literals.",
                "placeholder": "SELECT charttime, valuenum FROM labevents WHERE subject_id = 10001217 AND itemid = 50912",
            },
            {"name": "max_rows", "kind": "int", "required": False, "default": 1000},
        ],
    },
}


# Harness-side tools the agent has but the data layer does NOT execute. The contributor
# performs these themselves (their own Python / web search) and LOGS them, so the gold
# trajectory matches the agent's full surface. No `fn` — the API refuses to execute them
# and the console renders them as log-only. Param names match the agent's signatures.
# Log-only "manual" tools (contributor records their own step; never executed by the data
# layer). Now EMPTY: `execute_python` and `web_search` were removed — the benchmark grounds
# external knowledge solely in the staged policy corpus (list_policy_docs / search_policy /
# read_policy), and web egress is denied in the isolated setup (network_mode = "allowlist";
# see SIDECAR.md), so a live web-search stub is neither used nor wanted. The dict + machinery
# stay so a future manual tool can be added without re-plumbing api.py / validate_examples.
MANUAL_TOOLS: dict[str, dict] = {}


# Output schema per tool — the shape of what each tool RETURNS, so the console can show
# "what you'll get back" without calling it. `kind` is "table" (list[dict], one row per item)
# or "card" (a single dict; list/dict fields are nested sub-tables). Authored from tools.py
# and ground-truthed against live output by validate_examples.py. Attached onto TOOLS below.
OUTPUT_SCHEMAS: dict[str, dict] = {
    "get_patient_demographics": {
        "kind": "card",
        "fields": [
            {"name": "subject_id", "type": "int", "description": "Patient identifier."},
            {"name": "gender", "type": "str", "description": "Administrative gender (F/M)."},
            {"name": "anchor_age", "type": "int", "description": "Age during anchor_year_group."},
            {
                "name": "anchor_year_group",
                "type": "str",
                "description": "De-identified 3-year window.",
            },
            {
                "name": "dod",
                "type": "timestamp",
                "description": "Date of death, if recorded (nullable).",
            },
            {"name": "n_admissions", "type": "int", "description": "Lifetime hospital admissions."},
            {"name": "n_ed_visits", "type": "int", "description": "Lifetime ED visits."},
            {"name": "n_icu_stays", "type": "int", "description": "Lifetime ICU stays."},
        ],
    },
    "get_data_availability": {
        "kind": "table",
        "fields": [
            {"name": "stream", "type": "str", "description": "Logical table the row summarizes."},
            {
                "name": "rows",
                "type": "int",
                "description": "Exact row count for the requested scope; 0 means genuinely absent.",
            },
            {
                "name": "first_time",
                "type": "str",
                "description": "Earliest event time in the stream; null when rows = 0.",
            },
            {
                "name": "last_time",
                "type": "str",
                "description": "Latest event time in the stream; null when rows = 0.",
            },
        ],
    },
    "list_admissions": {
        "kind": "table",
        "fields": [
            {"name": "hadm_id", "type": "int", "description": "Hospital admission id."},
            {"name": "admittime", "type": "timestamp", "description": "Admission datetime."},
            {"name": "dischtime", "type": "timestamp", "description": "Discharge datetime."},
            {"name": "admission_type", "type": "str", "description": "e.g. EW EMER., ELECTIVE."},
            {
                "name": "admission_location",
                "type": "str",
                "description": "Where the patient came from.",
            },
            {"name": "discharge_location", "type": "str", "description": "Where the patient went."},
            {
                "name": "hospital_expire_flag",
                "type": "int",
                "description": "1 if died in hospital.",
            },
            {
                "name": "primary_diagnosis",
                "type": "str",
                "description": "seq_num=1 ICD long title.",
            },
        ],
    },
    "get_admission_details": {
        "kind": "card",
        "fields": [
            {"name": "subject_id", "type": "int", "description": "Patient identifier."},
            {"name": "hadm_id", "type": "int", "description": "Hospital admission id."},
            {"name": "admittime", "type": "timestamp", "description": "Admission datetime."},
            {"name": "dischtime", "type": "timestamp", "description": "Discharge datetime."},
            {
                "name": "deathtime",
                "type": "timestamp",
                "description": "In-hospital death time (nullable).",
            },
            {"name": "admission_type", "type": "str", "description": "e.g. EW EMER., ELECTIVE."},
            {"name": "admission_location", "type": "str", "description": "Source of admission."},
            {"name": "discharge_location", "type": "str", "description": "Discharge destination."},
            {"name": "insurance", "type": "str", "description": "Insurance category."},
            {"name": "marital_status", "type": "str", "description": "Marital status."},
            {"name": "race", "type": "str", "description": "Recorded race/ethnicity."},
            {
                "name": "hospital_expire_flag",
                "type": "int",
                "description": "1 if died in hospital.",
            },
            {
                "name": "ed_visits",
                "type": "list",
                "description": "Linked ED stays for this admission.",
            },
            {
                "name": "transfers",
                "type": "list",
                "description": "Ward transfers (eventtype, careunit, in/out).",
            },
            {
                "name": "icu_stays",
                "type": "list",
                "description": "ICU stays (careunits, in/out, los_days).",
            },
            {
                "name": "services",
                "type": "list",
                "description": "Service changes (prev/curr service).",
            },
            {
                "name": "drg",
                "type": "list",
                "description": "DRG codes (type, code, description, severity).",
            },
        ],
    },
    "list_ed_visits": {
        "kind": "table",
        "fields": [
            {"name": "stay_id", "type": "int", "description": "ED stay id."},
            {
                "name": "hadm_id",
                "type": "int",
                "description": "Linked admission, if admitted (nullable).",
            },
            {"name": "intime", "type": "timestamp", "description": "ED arrival."},
            {"name": "outtime", "type": "timestamp", "description": "ED departure."},
            {"name": "arrival_transport", "type": "str", "description": "How the patient arrived."},
            {
                "name": "disposition",
                "type": "str",
                "description": "ED disposition (e.g. ADMITTED, HOME).",
            },
        ],
    },
    "get_ed_visit_details": {
        "kind": "card",
        "fields": [
            {"name": "subject_id", "type": "int", "description": "Patient identifier."},
            {"name": "hadm_id", "type": "int", "description": "Linked admission (nullable)."},
            {"name": "stay_id", "type": "int", "description": "ED stay id."},
            {"name": "intime", "type": "timestamp", "description": "ED arrival."},
            {"name": "outtime", "type": "timestamp", "description": "ED departure."},
            {"name": "arrival_transport", "type": "str", "description": "How the patient arrived."},
            {"name": "disposition", "type": "str", "description": "ED disposition."},
            {
                "name": "triage",
                "type": "dict",
                "description": "Triage row: chief complaint, acuity, vitals.",
            },
            {
                "name": "vital_trend",
                "type": "list",
                "description": "ED vital-sign series over the stay.",
            },
            {"name": "ed_diagnoses", "type": "list", "description": "ED ICD diagnoses."},
            {
                "name": "medications_dispensed",
                "type": "list",
                "description": "Pyxis-dispensed meds.",
            },
        ],
    },
    "get_medication_reconciliation": {
        "kind": "table",
        "fields": [
            {
                "name": "charttime",
                "type": "timestamp",
                "description": "When the home-med list was recorded.",
            },
            {"name": "name", "type": "str", "description": "Medication name."},
            {"name": "gsn", "type": "str", "description": "GSN drug code."},
            {"name": "ndc", "type": "str", "description": "NDC code."},
            {"name": "etccode", "type": "str", "description": "Enhanced Therapeutic Class code."},
            {
                "name": "etcdescription",
                "type": "str",
                "description": "Therapeutic class description.",
            },
        ],
    },
    "list_icu_stays": {
        "kind": "table",
        "fields": [
            {"name": "stay_id", "type": "int", "description": "ICU stay id."},
            {"name": "hadm_id", "type": "int", "description": "Hospital admission id."},
            {"name": "first_careunit", "type": "str", "description": "Care unit at admission."},
            {"name": "last_careunit", "type": "str", "description": "Care unit at discharge."},
            {"name": "intime", "type": "timestamp", "description": "ICU in-time."},
            {"name": "outtime", "type": "timestamp", "description": "ICU out-time."},
            {"name": "los_days", "type": "float", "description": "Length of stay (days)."},
        ],
    },
    "get_icu_stay_details": {
        "kind": "card",
        "fields": [
            {"name": "subject_id", "type": "int", "description": "Patient identifier."},
            {"name": "hadm_id", "type": "int", "description": "Hospital admission id."},
            {"name": "stay_id", "type": "int", "description": "ICU stay id."},
            {"name": "first_careunit", "type": "str", "description": "Care unit at admission."},
            {"name": "last_careunit", "type": "str", "description": "Care unit at discharge."},
            {"name": "intime", "type": "timestamp", "description": "ICU in-time."},
            {"name": "outtime", "type": "timestamp", "description": "ICU out-time."},
            {"name": "los_days", "type": "float", "description": "Length of stay (days)."},
            {
                "name": "event_counts",
                "type": "dict",
                "description": "Row counts per source (chart/labs/meds/I-O).",
            },
        ],
    },
    "get_lab_timeline": {
        "kind": "table",
        "fields": [
            {"name": "charttime", "type": "timestamp", "description": "Specimen/measurement time."},
            {"name": "lab_name", "type": "str", "description": "Lab label (d_labitems.label)."},
            {"name": "itemid", "type": "int", "description": "labevents itemid."},
            {
                "name": "valuenum",
                "type": "float",
                "description": "Numeric value (nullable for text results).",
            },
            {"name": "valueuom", "type": "str", "description": "Unit of measure."},
            {"name": "ref_range_lower", "type": "float", "description": "Reference range low."},
            {"name": "ref_range_upper", "type": "float", "description": "Reference range high."},
            {"name": "flag", "type": "str", "description": "Abnormal flag (e.g. abnormal)."},
            {"name": "priority", "type": "str", "description": "STAT / ROUTINE."},
            {"name": "comments", "type": "str", "description": "Free-text comment (nullable)."},
            {"name": "hadm_id", "type": "int", "description": "Admission id (nullable)."},
        ],
    },
    "list_notes": {
        "kind": "table",
        "fields": [
            {"name": "note_id", "type": "str", "description": "Note id — pass to get_note."},
            {"name": "note_type", "type": "str", "description": "discharge | radiology."},
            {"name": "charttime", "type": "timestamp", "description": "Note charttime."},
            {"name": "hadm_id", "type": "int", "description": "Admission id (nullable)."},
            {"name": "raw_note_type", "type": "str", "description": "Source note_type code."},
            {"name": "text_chars", "type": "int", "description": "Length of the note text."},
        ],
    },
    "get_note": {
        "kind": "card",
        "fields": [
            {"name": "note_id", "type": "str", "description": "Note id."},
            {"name": "note_type", "type": "str", "description": "discharge | radiology."},
            {"name": "subject_id", "type": "int", "description": "Patient identifier."},
            {"name": "hadm_id", "type": "int", "description": "Admission id (nullable)."},
            {"name": "charttime", "type": "timestamp", "description": "Note charttime."},
            {
                "name": "text",
                "type": "str",
                "description": "Full note text (___ = de-identified PHI).",
            },
        ],
    },
    "search_notes": {
        "kind": "table",
        "fields": [
            {"name": "note_id", "type": "str", "description": "Note id — pass to get_note."},
            {"name": "note_type", "type": "str", "description": "discharge | radiology."},
            {"name": "charttime", "type": "timestamp", "description": "Note charttime."},
            {"name": "snippet", "type": "str", "description": "±120-char match snippet."},
            {
                "name": "section",
                "type": "str",
                "description": "Nearest discharge-summary header (nullable).",
            },
        ],
    },
    "get_vitals_timeline": {
        "kind": "table",
        "fields": [
            {"name": "charttime", "type": "timestamp", "description": "Charted time."},
            {"name": "metric_name", "type": "str", "description": "Vital label (d_items.label)."},
            {"name": "valuenum", "type": "float", "description": "Numeric value."},
            {"name": "valueuom", "type": "str", "description": "Unit of measure."},
            {"name": "stay_id", "type": "int", "description": "ICU stay id."},
        ],
    },
    "get_chart_timeline": {
        "kind": "table",
        "fields": [
            {"name": "charttime", "type": "timestamp", "description": "Charted time."},
            {
                "name": "itemid",
                "type": "int",
                "description": "chartevents itemid the row came from.",
            },
            {"name": "label", "type": "str", "description": "Concept label (d_items.label)."},
            {"name": "category", "type": "str", "description": "d_items category grouping."},
            {
                "name": "value",
                "type": "str",
                "description": "Charted value as text — the only populated form for "
                "categorical concepts (e.g. a CAM-ICU result).",
            },
            {
                "name": "valuenum",
                "type": "float",
                "description": "Numeric value; null when non-numeric.",
            },
            {"name": "valueuom", "type": "str", "description": "Unit of measure."},
            {"name": "warning", "type": "int", "description": "Charted out-of-range warning flag."},
            {"name": "stay_id", "type": "int", "description": "ICU stay id."},
            {"name": "hadm_id", "type": "int", "description": "Admission id."},
        ],
    },
    "get_icu_administrations": {
        "kind": "table",
        "fields": [
            {"name": "starttime", "type": "timestamp", "description": "Administration start."},
            {
                "name": "endtime",
                "type": "timestamp",
                "description": "Administration end; equals starttime for an instantaneous bolus.",
            },
            {"name": "itemid", "type": "int", "description": "inputevents itemid."},
            {"name": "label", "type": "str", "description": "Drug / fluid label (d_items.label)."},
            {"name": "category", "type": "str", "description": "d_items category grouping."},
            {"name": "amount", "type": "float", "description": "Amount given over the interval."},
            {
                "name": "amountuom",
                "type": "str",
                "description": "Amount unit (mL, mg, units — mixed).",
            },
            {"name": "rate", "type": "float", "description": "Infusion rate; null for a bolus."},
            {"name": "rateuom", "type": "str", "description": "Rate unit."},
            {
                "name": "ordercategoryname",
                "type": "str",
                "description": "Order category (matches get_fluid_balance's intake categories).",
            },
            {
                "name": "statusdescription",
                "type": "str",
                "description": "Terminal status (FinishedRunning, Stopped, Rewritten, …) — "
                "a Rewritten row continues as a later row, so summing naively double-counts.",
            },
            {
                "name": "patientweight",
                "type": "float",
                "description": "Weight used for weight-based rates.",
            },
            {"name": "stay_id", "type": "int", "description": "ICU stay id."},
            {"name": "hadm_id", "type": "int", "description": "Admission id."},
        ],
    },
    "get_medication_administered": {
        "kind": "table",
        "fields": [
            {"name": "charttime", "type": "timestamp", "description": "Administration time."},
            {"name": "medication", "type": "str", "description": "Medication name (EMAR)."},
            {
                "name": "event_txt",
                "type": "str",
                "description": "Administration status (e.g. Administered).",
            },
            {
                "name": "dose_given",
                "type": "str",
                "description": "Dose given (nullable; from emar_detail).",
            },
            {"name": "dose_unit", "type": "str", "description": "Dose unit (nullable)."},
            {"name": "route", "type": "str", "description": "Route (nullable)."},
            {"name": "hadm_id", "type": "int", "description": "Admission id (nullable)."},
            {"name": "emar_id", "type": "str", "description": "EMAR event id."},
        ],
    },
    "get_medication_prescribed": {
        "kind": "table",
        "fields": [
            {"name": "starttime", "type": "timestamp", "description": "Order start."},
            {"name": "stoptime", "type": "timestamp", "description": "Order stop."},
            {"name": "drug", "type": "str", "description": "Drug name."},
            {"name": "drug_type", "type": "str", "description": "MAIN / BASE / ADDITIVE."},
            {"name": "dose_val_rx", "type": "str", "description": "Prescribed dose value."},
            {"name": "dose_unit_rx", "type": "str", "description": "Dose unit."},
            {"name": "route", "type": "str", "description": "Route."},
            {"name": "doses_per_24_hrs", "type": "int", "description": "Doses per 24h (nullable)."},
            {"name": "hadm_id", "type": "int", "description": "Admission id."},
        ],
    },
    "get_diagnosis_history": {
        "kind": "table",
        "fields": [
            {"name": "source", "type": "str", "description": "inpatient | ed."},
            {"name": "encounter_id", "type": "int", "description": "hadm_id or ED stay_id."},
            {"name": "admittime", "type": "timestamp", "description": "Encounter time."},
            {"name": "seq_num", "type": "int", "description": "Diagnosis rank (1 = primary)."},
            {"name": "icd_code", "type": "str", "description": "ICD code."},
            {"name": "icd_version", "type": "int", "description": "9 or 10."},
            {"name": "long_title", "type": "str", "description": "Diagnosis description."},
        ],
    },
    "get_procedures": {
        "kind": "table",
        "fields": [
            {"name": "source", "type": "str", "description": "icd | icu."},
            {"name": "chartdate", "type": "str", "description": "Date/time of the procedure."},
            {"name": "code", "type": "str", "description": "ICD code or ICU itemid."},
            {"name": "label", "type": "str", "description": "Procedure description."},
            {"name": "hadm_id", "type": "int", "description": "Admission id."},
            {
                "name": "stay_id",
                "type": "int",
                "description": "ICU stay id (nullable for ICD rows).",
            },
        ],
    },
    "get_imaging_studies": {
        "kind": "table",
        "fields": [
            {"name": "starttime", "type": "timestamp", "description": "Study time."},
            {
                "name": "modality",
                "type": "str",
                "description": "Heuristic bucket CXR/CT/MRI/US/TEE (nullable).",
            },
            {"name": "label", "type": "str", "description": "Exam name / note type."},
            {"name": "hadm_id", "type": "int", "description": "Admission id (nullable)."},
            {
                "name": "linked_note_id",
                "type": "str",
                "description": "Radiology note_id — pass to get_note.",
            },
        ],
    },
    "get_microbiology_results": {
        "kind": "table",
        "fields": [
            {"name": "charttime", "type": "timestamp", "description": "Specimen time."},
            {"name": "spec_type_desc", "type": "str", "description": "Specimen type."},
            {"name": "test_name", "type": "str", "description": "Microbiology test."},
            {
                "name": "org_name",
                "type": "str",
                "description": "Organism grown (nullable if no growth).",
            },
            {"name": "ab_name", "type": "str", "description": "Antibiotic tested (nullable)."},
            {
                "name": "interpretation",
                "type": "str",
                "description": "Susceptibility S/I/R (nullable).",
            },
            {"name": "dilution_value", "type": "float", "description": "MIC dilution (nullable)."},
            {"name": "comments", "type": "str", "description": "Free-text comment (nullable)."},
        ],
    },
    "get_fluid_balance": {
        "kind": "card",
        "fields": [
            {"name": "stay_id", "type": "int", "description": "ICU stay id."},
            {
                "name": "total_in",
                "type": "float",
                "description": "Naive sum of intake amounts (mixed units!).",
            },
            {"name": "total_out", "type": "float", "description": "Sum of outputs."},
            {"name": "net_balance", "type": "float", "description": "total_in − total_out."},
            {
                "name": "urine_output_ml",
                "type": "float",
                "description": "Canonical net urine output (mL).",
            },
            {
                "name": "intake_by_category",
                "type": "list",
                "description": "Intake grouped by category (amount, uom, n).",
            },
            {
                "name": "output_by_category",
                "type": "list",
                "description": "Output grouped by category.",
            },
        ],
    },
    "list_orders": {
        "kind": "table",
        "fields": [
            {"name": "poe_id", "type": "str", "description": "Provider-order-entry id."},
            {"name": "ordertime", "type": "timestamp", "description": "Order time."},
            {
                "name": "order_type",
                "type": "str",
                "description": "Order type (e.g. Medications, Lab).",
            },
            {"name": "order_subtype", "type": "str", "description": "Order subtype (nullable)."},
            {"name": "transaction_type", "type": "str", "description": "New / Change / etc."},
            {"name": "order_status", "type": "str", "description": "Order status."},
            {
                "name": "order_provider_id",
                "type": "str",
                "description": "Ordering provider (anon).",
            },
            {"name": "hadm_id", "type": "int", "description": "Admission id."},
            {
                "name": "details",
                "type": "dict",
                "description": "poe_detail key/values for the order.",
            },
        ],
    },
    "run_sql": {
        "kind": "card",
        "fields": [
            {
                "name": "columns",
                "type": "list",
                "description": "Result column names (depends on your query).",
            },
            {"name": "rows", "type": "list", "description": "Result rows (list of dicts)."},
            {"name": "returned", "type": "int", "description": "Number of rows returned."},
            {"name": "truncated", "type": "bool", "description": "True if capped at max_rows."},
            {"name": "note", "type": "str", "description": "Truncation note (nullable)."},
        ],
    },
}

for _name, _out in OUTPUT_SCHEMAS.items():
    TOOLS[_name]["output"] = _out


# Policy-document search tools — a staged, read-only Markdown corpus of clinical guidelines /
# policy documents, exposed with glob/grep/read semantics (list_policy_docs / search_policy /
# read_policy). Gated on MIMIC_POLICY_TOOLS so the benchmark's policy-OFF ablation omits them
# entirely (no tools, and build_tasks stages no corpus). Line-anchored returns let the agent
# cite exact spans as `[policy: <doc> L<start>-L<end>]` for the citation verifier.
POLICY_TOOLS: dict[str, dict] = {
    "list_policy_docs": {
        "fn": tools.list_policy_docs,
        "doc": "List the policy/guideline documents in the corpus. Returns {items: [{filename, title, size}]} — your index into the policy corpus; start here, then search_policy / read_policy.",
        "group": "Policy docs",
        "tables": [],
        "example": {},
        "params": [
            {
                "name": "pattern",
                "kind": "str",
                "required": False,
                "help": "optional filename glob, e.g. *kidney*",
            },
        ],
    },
    "search_policy": {
        "fn": tools.search_policy,
        "doc": "Search the policy corpus (grep). Returns {items: [{doc, line, text}]} — line-anchored matches with physical line numbers; cite the span and read_policy around it.",
        "group": "Policy docs",
        "tables": [],
        "example": {"query": "iodinated contrast", "context_lines": 2},
        "params": [
            {
                "name": "query",
                "kind": "str",
                "required": True,
                "help": "keyword, or a regex if regex=true",
            },
            {
                "name": "regex",
                "kind": "enum",
                "required": False,
                "options": ["false", "true"],
                "default": "false",
            },
            {
                "name": "case_sensitive",
                "kind": "enum",
                "required": False,
                "options": ["false", "true"],
                "default": "false",
            },
            {
                "name": "context_lines",
                "kind": "int",
                "required": False,
                "default": 0,
                "help": "numbered context lines on each side of a match",
            },
            {"name": "max_results", "kind": "int", "required": False, "default": 50},
        ],
    },
    "read_policy": {
        "fn": tools.read_policy,
        "doc": "Read a policy document, or a line range (cat / head / tail). Returns text with physical line numbers so you can quote and cite an exact span as [policy: <doc> L<start>-L<end>].",
        "group": "Policy docs",
        "tables": [],
        "example": {
            "doc": "davenport-et-al-2020-use-of-intravenous-iodinated-contrast-media-in-patients-with-kidney-disease-consensus-statements.md",
            "line_start": 100,
            "line_end": 140,
        },
        "params": [
            {
                "name": "doc",
                "kind": "str",
                "required": True,
                "help": "document filename from list_policy_docs",
            },
            {
                "name": "line_start",
                "kind": "int",
                "required": False,
                "help": "1-indexed start line (omit for whole doc)",
            },
            {"name": "line_end", "kind": "int", "required": False, "help": "1-indexed end line"},
        ],
    },
}


def _policy_tools_enabled() -> bool:
    """Policy tools are ON unless explicitly disabled — policy-ON is the benchmark's normal
    condition and `--no-policy` is the ablation, so an UNSET var must not silently mean OFF.

    Failing closed here is a trap: every layer above already defaults to on
    (`sidecar.compose.yml` writes `${MIMIC_POLICY_TOOLS:-1}`, `task.toml` sets "1"), so a var
    that goes missing in transit yields a tool list indistinguishable from an intentional
    policy-OFF run — the whole policy axis silently scores ~0 for harness reasons. Note that
    some agent harnesses scrub the spawned MCP server's environment, so the var reaching the
    shim is not guaranteed; see `mcp_server._PROXY_ENV_VARS`.
    """
    return os.environ.get("MIMIC_POLICY_TOOLS", "").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def apply_policy_gate() -> None:
    """(Re)sync TOOLS with MIMIC_POLICY_TOOLS, adding or removing the policy tools.

    Callable more than once because the import-time pass below is too early for the stdio shim: the
    launching agent CLI (codex) scrubs the spawned server's env, so the gate would be read from a
    stripped environment. `mcp_server.main` calls this again right after `_recover_proxy_env()` so a
    recovered explicit OFF still takes effect — otherwise the policy-OFF ablation would silently run
    policy-ON now that the gate fails open.
    """
    if _policy_tools_enabled():
        TOOLS.update(POLICY_TOOLS)
    else:
        for _policy_name in POLICY_TOOLS:
            TOOLS.pop(_policy_name, None)


apply_policy_gate()


def coerce_params(spec: dict, raw: dict) -> tuple[dict, str | None]:
    """Coerce raw inputs into typed kwargs for a tool. Returns (kwargs, error).

    Accepts both Streamlit form strings and native JSON values (the API path), so an
    int that already arrives as an int passes through unchanged. Empty optional params
    are omitted; missing required params return an error; declared defaults are applied.
    """
    kwargs: dict[str, Any] = {}
    for p in spec["params"]:
        name, kind = p["name"], p["kind"]
        val = raw.get(name, "")
        if isinstance(val, str):
            val = val.strip()
        if val in ("", None):
            if p.get("required"):
                return {}, f"Missing required parameter: {name}"
            if "default" in p:
                kwargs[name] = p["default"]
            continue
        # `multi` is checked BEFORE kind so a list reaching an int param coerces
        # element-wise; int(a_list) would raise.
        if p.get("multi") and isinstance(val, (list, tuple)):
            # Drop blanks so a UI that submits empty slots doesn't widen the match to '%%'.
            vals = [str(v).strip() for v in val if str(v).strip()]
            if not vals:
                if p.get("required"):
                    return {}, f"Missing required parameter: {name}"
                continue
            if kind == "int":
                try:
                    vals = [int(v) for v in vals]
                except (ValueError, TypeError):
                    return {}, f"{name} must be integers (got {val!r})"
            kwargs[name] = vals
        elif kind == "int":
            try:
                kwargs[name] = int(val)
            except (ValueError, TypeError):
                return {}, f"{name} must be an integer (got {val!r})"
        else:  # str | text | enum | enum_dynamic
            kwargs[name] = val
    return kwargs, None
