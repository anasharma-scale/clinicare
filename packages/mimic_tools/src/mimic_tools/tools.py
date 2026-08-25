"""Canonical MIMIC-IV tool surface — read-only. Source of truth for both the
contributor chart-console UI and the agent harness.

This is the SEMANTIC surface the benchmark agent uses. The UI and the agent
import theSAME functions here, so anything a contributor can do to solve a task
is exactly what the agent can do — that shared surface is what makes the gold
trajectories valid.

Return shapes are plain JSON-friendly Python:
  - "table" tools return list[dict] (one dict per row, documented columns)
  - single-entity tools return a dict ("card") or None
Datetimes/dates are stringified; Decimals are floats.

Backend-agnostic: all SQL here uses LOGICAL table names and runs through db.py,
which targets either DuckDB over a local Parquet copy or MIMIC on PhysioNet BigQuery
(contributors) per the MIMIC_BACKEND env var. Compare timestamp columns to params
by casting BOTH sides — CAST(col AS TIMESTAMP) >= CAST(? AS TIMESTAMP). Casting only the
param breaks on BigQuery, where these columns are DATETIME (no DATETIME>=TIMESTAMP operator).
Stringify with CAST(x AS STRING); BigQuery has no VARCHAR type. Avoid `rows` as a column
alias — it is a reserved keyword in BigQuery and has no portable quoting.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any

from . import db

# (sql, params) -> list[dict]; returns [] if the source is unavailable on the backend.
_safe_rows = db.safe_query


# ==================== Shared filter helpers =============================== #
# Concept filters take one term or many, and every timestamped tool takes an inclusive
# [start_time, end_time] window. Both exist because a single-term, window-less tool forces
# the caller to either page the whole stream and filter client-side or drop to run_sql.


def _terms(value: str | list[str] | None) -> list[str]:
    """Normalize a concept filter to a list of search terms.

    A list means "match any of these" (OR). A plain string stays ONE term: we do not
    comma-split, even though FHIR spells comma-OR that way (`code=a,b,c`), because real
    values contain commas — e.g. lab_name="Bilirubin, Total" — and splitting those would
    silently broaden the match instead of narrowing it.
    """
    if value is None:
        return []
    vals = value if isinstance(value, (list, tuple)) else [value]
    return [t for t in (str(v).strip() for v in vals) if t]


def _like_any(col: str, terms: list[str], params: list[Any]) -> str:
    """`(LOWER(col) LIKE ? OR ...)` — one substring test per term, binds appended in
    order. Only call with a non-empty `terms`."""
    params.extend(f"%{t.lower()}%" for t in terms)
    return "(" + " OR ".join([f"LOWER({col}) LIKE ?"] * len(terms)) + ")"


# Each time component accepts 1-2 digits: a `(\d{2})` minute group would fail to match "8:5"
# and silently pad it to 08:00:00, moving the boundary — the exact error the *_time naming is
# meant to prevent. The trailing $ keeps trailing junk from being silently truncated.
_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[ T](\d{1,2})(?::(\d{1,2}))?(?::(\d{1,2}))?)?$")


def _norm_ts(value: str) -> str:
    """Pad a user-supplied instant to `YYYY-MM-DD HH:MM:SS`.

    The documented input is `YYYY-MM-DD[ HH:MM[:SS]]`, but BigQuery rejects a partial
    literal — `CAST('2189-06-27 08:00' AS TIMESTAMP)` fails with "Invalid timestamp" —
    while DuckDB accepts it. Padding here keeps the documented contract true on both
    backends instead of only the one it was developed against. Anything that doesn't parse
    is passed through untouched so the backend still reports its own error.
    """
    m = _TS_RE.match(value.strip())
    if not m:
        return value
    date, hh, mm, ss = m.group(1), m.group(2) or "0", m.group(3) or "0", m.group(4) or "0"
    return f"{date} {int(hh):02d}:{int(mm):02d}:{int(ss):02d}"


def _window(
    col: str,
    start_time: str | None,
    end_time: str | None,
    where: list[str],
    params: list[Any],
    *,
    grain: str = "TIMESTAMP",
) -> None:
    """Append an inclusive [start_time, end_time] filter on `col`. Both sides are cast so
    DuckDB and BigQuery agree (see the module docstring).

    grain="DATE" compares at DAY granularity, for a source column that carries no time of
    day — only procedures_icd.chartdate today. Comparing such a column as a timestamp makes
    it read as midnight, which silently biases both bounds: `end_time` on day D admits it
    while `start_time` on D with any time-of-day excludes it, so a window opening and
    closing inside one day returns none of that day's rows. Truncating both sides to a date
    instead means "any row on a day the window touches", which is the only claim the data
    supports when the event's time is unknown.
    """
    inner = (
        "CAST(? AS TIMESTAMP)" if grain == "TIMESTAMP" else f"CAST(CAST(? AS TIMESTAMP) AS {grain})"
    )
    for bound, op in ((start_time, ">="), (end_time, "<=")):
        if bound:
            where.append(f"CAST({col} AS {grain}) {op} {inner}")
            params.append(_norm_ts(bound))


# ============================= Patient ==================================== #


def get_patient_demographics(subject_id: int) -> dict[str, Any] | None:
    """Chart-overview card for one patient: demographics + lifetime encounter counts."""
    rows = _safe_rows(
        """
        SELECT
            p.subject_id, p.gender, p.anchor_age, p.anchor_year_group, p.dod,
            (SELECT COUNT(*) FROM admissions a WHERE a.subject_id = p.subject_id) AS n_admissions,
            (SELECT COUNT(*) FROM edstays  e WHERE e.subject_id = p.subject_id) AS n_ed_visits,
            (SELECT COUNT(*) FROM icustays i WHERE i.subject_id = p.subject_id) AS n_icu_stays
        FROM patients p
        WHERE p.subject_id = ?
        """,
        [subject_id],
    )
    return rows[0] if rows else None


# Per-stream (table, time column) the availability census reports, in rough clinical
# reading order. Every one carries subject_id + hadm_id + the named time column.
_AVAILABILITY_STREAMS: list[tuple[str, str]] = [
    ("admissions", "admittime"),
    ("edstays", "intime"),
    ("icustays", "intime"),
    ("transfers", "intime"),
    ("labevents", "charttime"),
    ("chartevents", "charttime"),
    ("inputevents", "starttime"),
    ("outputevents", "charttime"),
    ("procedureevents", "starttime"),
    ("datetimeevents", "charttime"),
    ("emar", "charttime"),
    ("prescriptions", "starttime"),
    ("poe", "ordertime"),
    ("microbiologyevents", "COALESCE(charttime, chartdate)"),
    ("radiology_notes", "charttime"),
    ("discharge_notes", "charttime"),
]


def get_data_availability(subject_id: int, hadm_id: int | None = None) -> list[dict[str, Any]]:
    """How much of each data stream this patient actually has, and over what span.

    One row per stream: `rows`, `first_time`, `last_time`. Answers "is this stream empty
    for this patient, or did my filter just miss?" — a distinction an empty result from any
    other tool cannot make — and "where does the record end?", without paging the data.

    A stream with rows = 0 has no data for the scope requested; that is a finding in itself,
    not a retrieval failure. (A stream the backend does not expose at all also reads as 0 —
    indistinguishable here, though on both supported backends all of these tables exist.)
    Note that labs and notes may exist for a patient OUTSIDE any admission (outpatient), so
    passing hadm_id can legitimately zero a stream that has data at the patient level —
    call it both ways when that distinction matters.

    Counts are exact, not estimates, and cover only the scope given (subject, optionally
    admission); they say nothing about which itemids or concepts are present.
    """
    where = "subject_id = ?"
    params: list[Any] = [subject_id]
    if hadm_id is not None:
        where += " AND hadm_id = ?"
        params.append(hadm_id)
    # One aggregate per stream, each GROUPed BY subject_id. Both details are load-bearing on
    # the DuckDB/parquet backend:
    #   - GROUP BY (rather than a bare aggregate) keeps DuckDB from constant-folding MIN/MAX
    #     in StatisticsPropagator::TryExecuteAggregates, which raises "INTERNAL Error:
    #     Attempted to access index 0 within vector of size 0" when the filter matches ZERO
    #     row groups. That fires on the largest partitioned table (chartevents) for any
    #     patient/admission with no rows there — i.e. exactly the empty case this tool exists
    #     to report. A grouped query instead returns no rows, which we render as rows = 0.
    #   - per-stream (rather than one UNION ALL) isolates failure: a table absent on the
    #     backend degrades to a skipped stream via _safe_rows instead of voiding the census.
    out: list[dict[str, Any]] = []
    for table, tcol in _AVAILABILITY_STREAMS:
        rows = _safe_rows(
            f"SELECT COUNT(*) AS n_rows, CAST(MIN({tcol}) AS STRING) AS first_time, "
            f"CAST(MAX({tcol}) AS STRING) AS last_time "
            f"FROM {table} WHERE {where} GROUP BY subject_id",
            params,
        )
        r = rows[0] if rows else {}
        out.append(
            {
                "stream": table,
                "rows": r.get("n_rows", 0),
                "first_time": r.get("first_time"),
                "last_time": r.get("last_time"),
            }
        )
    return out


# ============================= Admissions ================================= #


def list_admissions(subject_id: int) -> list[dict[str, Any]]:
    """All hospital admissions for a patient, chronological. Index for longitudinal reasoning."""
    # The primary diagnosis (seq_num = 1) is pulled in via a de-correlated LEFT JOIN: a
    # correlated subquery that both references the outer `a.hadm_id` and JOINs two tables
    # is rejected by BigQuery ("Correlated subqueries ... unless they can be de-correlated").
    # seq_num = 1 is unique per hadm_id, so the derived table is one row per hadm_id (no fan-out).
    return _safe_rows(
        """
        SELECT
            a.hadm_id, a.admittime, a.dischtime, a.admission_type,
            a.admission_location, a.discharge_location, a.hospital_expire_flag,
            pd.long_title AS primary_diagnosis
        FROM admissions a
        LEFT JOIN (
            SELECT di.hadm_id, dd.long_title
              FROM diagnoses_icd di
              LEFT JOIN d_icd_diagnoses dd USING (icd_code, icd_version)
             WHERE di.seq_num = 1
        ) pd ON pd.hadm_id = a.hadm_id
        WHERE a.subject_id = ?
        ORDER BY a.admittime
        """,
        [subject_id],
    )


def get_admission_details(hadm_id: int) -> dict[str, Any] | None:
    """One admission: dates/disposition, ED link, transfers, ICU stays, services, DRG."""
    base = _safe_rows(
        """
        SELECT subject_id, hadm_id, admittime, dischtime, deathtime,
               admission_type, admission_location, discharge_location,
               insurance, marital_status, race, hospital_expire_flag
        FROM admissions WHERE hadm_id = ?
        """,
        [hadm_id],
    )
    if not base:
        return None
    detail = base[0]
    detail["ed_visits"] = _safe_rows(
        "SELECT stay_id, intime, outtime, disposition FROM edstays WHERE hadm_id = ? ORDER BY intime",
        [hadm_id],
    )
    detail["transfers"] = _safe_rows(
        "SELECT transfer_id, eventtype, careunit, intime, outtime FROM transfers WHERE hadm_id = ? ORDER BY intime",
        [hadm_id],
    )
    detail["icu_stays"] = _safe_rows(
        "SELECT stay_id, first_careunit, last_careunit, intime, outtime, los AS los_days "
        "FROM icustays WHERE hadm_id = ? ORDER BY intime",
        [hadm_id],
    )
    detail["services"] = _safe_rows(
        "SELECT transfertime, prev_service, curr_service FROM services WHERE hadm_id = ? ORDER BY transfertime",
        [hadm_id],
    )
    detail["drg"] = _safe_rows(
        "SELECT drg_type, drg_code, description, drg_severity, drg_mortality FROM drgcodes WHERE hadm_id = ?",
        [hadm_id],
    )
    return detail


# ============================= ED ========================================= #


def list_ed_visits(subject_id: int) -> list[dict[str, Any]]:
    """ED visits for a patient, chronological."""
    return _safe_rows(
        """
        SELECT stay_id, hadm_id, intime, outtime, arrival_transport, disposition
        FROM edstays WHERE subject_id = ? ORDER BY intime
        """,
        [subject_id],
    )


def get_ed_visit_details(stay_id: int) -> dict[str, Any] | None:
    """Chart-review-style ED summary: triage (chief complaint, acuity, vitals),
    vital-sign trend, ED diagnoses, dispensed meds (Pyxis), disposition."""
    base = _safe_rows(
        "SELECT subject_id, hadm_id, stay_id, intime, outtime, arrival_transport, disposition "
        "FROM edstays WHERE stay_id = ?",
        [stay_id],
    )
    if not base:
        return None
    d = base[0]
    triage = _safe_rows(
        "SELECT chiefcomplaint, acuity, temperature, heartrate, resprate, o2sat, sbp, dbp, pain "
        "FROM ed_triage WHERE stay_id = ?",
        [stay_id],
    )
    d["triage"] = triage[0] if triage else None
    d["vital_trend"] = _safe_rows(
        "SELECT charttime, temperature, heartrate, resprate, o2sat, sbp, dbp, pain "
        "FROM ed_vitalsign WHERE stay_id = ? ORDER BY charttime",
        [stay_id],
    )
    d["ed_diagnoses"] = _safe_rows(
        "SELECT seq_num, icd_code, icd_version, icd_title FROM ed_diagnosis WHERE stay_id = ? ORDER BY seq_num",
        [stay_id],
    )
    d["medications_dispensed"] = _safe_rows(
        "SELECT charttime, name, gsn FROM ed_pyxis WHERE stay_id = ? ORDER BY charttime",
        [stay_id],
    )
    return d


def get_medication_reconciliation(
    subject_id: int, hadm_id: int | None = None, stay_id: int | None = None
) -> list[dict[str, Any]]:
    """Home medication list captured at ED arrival (medrecon). Anchor with the ED
    stay_id, or with hadm_id (resolved to the linked ED stay)."""
    where = ["subject_id = ?"]
    params: list[Any] = [subject_id]
    if stay_id is not None:
        where.append("stay_id = ?")
        params.append(stay_id)
    elif hadm_id is not None:
        where.append("stay_id IN (SELECT stay_id FROM edstays WHERE hadm_id = ?)")
        params.append(hadm_id)
    return _safe_rows(
        f"SELECT charttime, name, gsn, ndc, etccode, etcdescription FROM medrecon "
        f"WHERE {' AND '.join(where)} ORDER BY name",
        params,
    )


# ============================= ICU stays ================================== #


def list_icu_stays(subject_id: int, hadm_id: int | None = None) -> list[dict[str, Any]]:
    """ICU stays for a patient (optionally scoped to one admission), chronological."""
    where = ["subject_id = ?"]
    params: list[Any] = [subject_id]
    if hadm_id is not None:
        where.append("hadm_id = ?")
        params.append(hadm_id)
    return _safe_rows(
        f"""
        SELECT stay_id, hadm_id, first_careunit, last_careunit, intime, outtime, los AS los_days
        FROM icustays
        WHERE {" AND ".join(where)}
        ORDER BY intime
        """,
        params,
    )


def get_icu_stay_details(stay_id: int) -> dict[str, Any] | None:
    """ICU stay summary card: metadata + event-volume counts (chart, labs, meds, procedures, I/O)."""
    base = _safe_rows(
        "SELECT subject_id, hadm_id, stay_id, first_careunit, last_careunit, intime, outtime, los AS los_days "
        "FROM icustays WHERE stay_id = ?",
        [stay_id],
    )
    if not base:
        return None
    d = base[0]
    hadm, intime, outtime = d["hadm_id"], d["intime"], d["outtime"]

    def _count(sql: str, params: list[Any]) -> int:
        r = _safe_rows(sql, params)
        return r[0]["n"] if r else 0

    d["event_counts"] = {
        "chartevents": _count("SELECT COUNT(*) AS n FROM chartevents WHERE stay_id = ?", [stay_id]),
        "procedureevents": _count(
            "SELECT COUNT(*) AS n FROM procedureevents WHERE stay_id = ?", [stay_id]
        ),
        "inputevents": _count("SELECT COUNT(*) AS n FROM inputevents WHERE stay_id = ?", [stay_id]),
        "outputevents": _count(
            "SELECT COUNT(*) AS n FROM outputevents WHERE stay_id = ?", [stay_id]
        ),
        "labs": _count(
            "SELECT COUNT(*) AS n FROM labevents WHERE hadm_id = ? "
            "AND CAST(charttime AS TIMESTAMP) BETWEEN CAST(? AS TIMESTAMP) AND CAST(? AS TIMESTAMP)",
            [hadm, intime, outtime],
        ),
        "medications_emar": _count(
            "SELECT COUNT(*) AS n FROM emar WHERE hadm_id = ? "
            "AND CAST(charttime AS TIMESTAMP) BETWEEN CAST(? AS TIMESTAMP) AND CAST(? AS TIMESTAMP)",
            [hadm, intime, outtime],
        ),
    }
    return d


# ============================= Labs ======================================= #

# Canonical labevents itemid sets, from MIT-LCP/mimic-code mimic-iv/concepts/measurement
# (chemistry.sql, complete_blood_count.sql); lactate/a1c resolved from d_labitems (Blood
# only — excludes LDH and body-fluid variants). Selecting by itemid avoids the
# over-matching of label-substring search (e.g. it excludes ascites/joint creatinines
# and the urine albumin/creatinine ratio). Port new labs from mimic-code, not memory.
_LAB_ITEMS = {
    "creatinine": [50912],
    "bun": [51006],
    "sodium": [50983],
    "potassium": [50971],
    "chloride": [50902],
    "bicarbonate": [50882],
    "calcium": [50893],
    "anion_gap": [50868],
    "glucose": [50931],
    "albumin": [50862],
    "hematocrit": [51221],
    "hemoglobin": [51222],
    "platelets": [51265],
    "wbc": [51301],
    "lactate": [50813, 52442, 53154],
    "a1c": [50852, 50854, 51631],
    # blood gas (bg.sql)
    "ph": [50820],
    "po2": [50821],
    "pco2": [50818],
    "base_excess": [50802],
    # coagulation (coagulation.sql)
    "inr": [51237],
    "pt": [51274],
    "ptt": [51275],
    # enzyme / liver (enzyme.sql)
    "alt": [50861],
    "ast": [50878],
    "alp": [50863],
    "ggt": [50927],
    "bilirubin_total": [50885],
    "bilirubin_direct": [50883],
    "ldh": [50954],
    "ck": [50910],
    "ck_mb": [50911],
    "amylase": [50867],
    # ammonia / lipase (resolved from d_labitems, Blood only)
    "ammonia": [50866],
    "lipase": [50956],
    # cardiac markers (cardiac_marker.sql)
    "troponin_t": [51003],
    "ntprobnp": [50963],
    # inflammation (inflammation.sql)
    "crp": [50889],
}
# Free-text aliases -> canonical key (matched on the normalized lab_name).
_LAB_ALIASES = {
    "creatinine": "creatinine",
    "cr": "creatinine",
    "bun": "bun",
    "urea nitrogen": "bun",
    "urea": "bun",
    "sodium": "sodium",
    "na": "sodium",
    "potassium": "potassium",
    "k": "potassium",
    "chloride": "chloride",
    "cl": "chloride",
    "bicarbonate": "bicarbonate",
    "bicarb": "bicarbonate",
    "hco3": "bicarbonate",
    "calcium": "calcium",
    "ca": "calcium",
    "anion gap": "anion_gap",
    "anion_gap": "anion_gap",
    "glucose": "glucose",
    "albumin": "albumin",
    "hematocrit": "hematocrit",
    "hct": "hematocrit",
    "hemoglobin": "hemoglobin",
    "hgb": "hemoglobin",
    "hb": "hemoglobin",
    "platelets": "platelets",
    "platelet": "platelets",
    "plt": "platelets",
    "wbc": "wbc",
    "white blood cells": "wbc",
    "white blood cell": "wbc",
    "lactate": "lactate",
    "a1c": "a1c",
    "hba1c": "a1c",
    "hemoglobin a1c": "a1c",
    "glycated hemoglobin": "a1c",
    "glycated": "a1c",
    "ph": "ph",
    "po2": "po2",
    "pao2": "po2",
    "pco2": "pco2",
    "paco2": "pco2",
    "base excess": "base_excess",
    "base_excess": "base_excess",
    "inr": "inr",
    "pt": "pt",
    "prothrombin time": "pt",
    "ptt": "ptt",
    "aptt": "ptt",
    "alt": "alt",
    "sgpt": "alt",
    "ast": "ast",
    "sgot": "ast",
    "alp": "alp",
    "alkaline phosphatase": "alp",
    "alk phos": "alp",
    "ggt": "ggt",
    "bilirubin": "bilirubin_total",
    "total bilirubin": "bilirubin_total",
    "bilirubin total": "bilirubin_total",
    "tbili": "bilirubin_total",
    "direct bilirubin": "bilirubin_direct",
    "bilirubin direct": "bilirubin_direct",
    "ldh": "ldh",
    "ck": "ck",
    "cpk": "ck",
    "creatine kinase": "ck",
    "ck-mb": "ck_mb",
    "ckmb": "ck_mb",
    "ck mb": "ck_mb",
    "amylase": "amylase",
    "ammonia": "ammonia",
    "nh3": "ammonia",
    "lipase": "lipase",
    "troponin": "troponin_t",
    "troponin t": "troponin_t",
    "trop": "troponin_t",
    "bnp": "ntprobnp",
    "nt-probnp": "ntprobnp",
    "ntprobnp": "ntprobnp",
    "probnp": "ntprobnp",
    "crp": "crp",
    "c-reactive protein": "crp",
    "c reactive protein": "crp",
}


def get_lab_timeline(
    subject_id: int,
    lab_name: str | list[str] | None = None,
    hadm_id: int | None = None,
    stay_id: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Chronological labs (ascending) with reference ranges, flags, and comments.

    lab_name: a canonical name (creatinine, bun, sodium, potassium, hemoglobin, wbc,
              lactate, a1c, ...) resolves to the exact mimic-code labevents itemid(s) —
              precise, Blood-only. Any other free-text falls back to a case-insensitive
              label substring (which may span fluids). Pass a LIST to match any of
              several labs in one call (canonical and free-text terms may be mixed).
              Optional hadm_id / stay_id / date scoping (stay_id resolves to the ICU
              stay's [intime, outtime] window, since labevents has no stay_id).
              Ascending order so trajectory tasks never silently drop the oldest values.
    """
    where = ["l.subject_id = ?"]
    params: list[Any] = [subject_id]
    terms = _terms(lab_name)
    if terms:
        # Each term resolves independently: canonical -> exact itemids, else a label
        # substring. OR them so one call can mix e.g. ["potassium", "Bilirubin, Total"].
        # Clause and binds are built together, then appended in clause order.
        ors: list[str] = []
        binds: list[Any] = []
        itemids: list[int] = []
        for t in terms:
            key = _LAB_ALIASES.get(t.lower())
            if key:
                itemids.extend(_LAB_ITEMS[key])
            else:
                ors.append("LOWER(d.label) LIKE ?")
                binds.append(f"%{t.lower()}%")
        if itemids:
            ors.insert(0, "l.itemid IN (" + ",".join(["?"] * len(itemids)) + ")")
            binds = [*itemids, *binds]
        where.append("(" + " OR ".join(ors) + ")")
        params.extend(binds)
    if hadm_id is not None:
        where.append("l.hadm_id = ?")
        params.append(hadm_id)
    if stay_id is not None:
        where.append(
            "l.charttime BETWEEN (SELECT intime FROM icustays WHERE stay_id = ?) "
            "AND (SELECT outtime FROM icustays WHERE stay_id = ?)"
        )
        params.extend([stay_id, stay_id])
    _window("l.charttime", start_time, end_time, where, params)
    return _safe_rows(
        f"""
        SELECT l.charttime, d.label AS lab_name, l.itemid, l.valuenum, l.valueuom,
               l.ref_range_lower, l.ref_range_upper, l.flag, l.priority, l.comments, l.hadm_id
        FROM labevents l
        JOIN d_labitems d USING (itemid)
        WHERE {" AND ".join(where)}
        ORDER BY l.charttime
        LIMIT ?
        """,
        [*params, limit],
    )


# ============================= Vitals ===================================== #

# metric -> chartevents itemids, from MIT-LCP/mimic-code
# mimic-iv/concepts/measurement/vitalsign.sql (GCS from the GCS concept). All verified
# present in d_items. Update from mimic-code, not from memory, when extending.
_VITAL_ITEMS = {
    "HR": [220045],
    "BP": [
        220179,
        220180,
        220181,
        220050,
        220051,
        220052,
        225309,
        225310,
        225312,
    ],  # NBP + ART sys/dia/mean
    "RR": [220210, 224690],  # Respiratory Rate (+ Total)
    "temperature": [223761, 223762],  # F, C
    "SpO2": [220277],
    "GCS": [220739, 223900, 223901],  # eye, verbal, motor
}
_ALL_VITAL_ITEMS = sorted({i for v in _VITAL_ITEMS.values() for i in v})


def get_vitals_timeline(
    subject_id: int,
    metric: str | list[str] | None = None,
    hadm_id: int | None = None,
    stay_id: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """ICU vital signs over time (chartevents). metric: HR / BP / temperature / RR /
    SpO2 / GCS (BP -> sys+dia+mean; GCS -> eye+verbal+motor), or a LIST of those to get
    several in one call. start_time / end_time bound charttime inclusively. For ED vitals
    use get_ed_visit_details. Always restricted to vital itemids to avoid dumping
    chartevents — a metric outside the list above does not narrow the result."""
    items: list[int] = []
    for term in _terms(metric):
        for key in (term, term.upper(), term.lower()):
            if key in _VITAL_ITEMS:
                items.extend(_VITAL_ITEMS[key])
                break
    # No recognized metric (including none supplied) -> every vital itemid, as before.
    items = list(dict.fromkeys(items)) or _ALL_VITAL_ITEMS
    where = ["c.subject_id = ?", "c.itemid IN (" + ",".join(["?"] * len(items)) + ")"]
    params: list[Any] = [subject_id, *items]
    _window("c.charttime", start_time, end_time, where, params)
    if stay_id is not None:
        where.append("c.stay_id = ?")
        params.append(stay_id)
    if hadm_id is not None:
        where.append("c.hadm_id = ?")
        params.append(hadm_id)
    return _safe_rows(
        f"""
        SELECT c.charttime, di.label AS metric_name, c.valuenum, c.valueuom, c.stay_id
        FROM chartevents c
        JOIN d_items di USING (itemid)
        WHERE {" AND ".join(where)}
        ORDER BY c.charttime
        LIMIT ?
        """,
        [*params, limit],
    )


# Standard ICU instruments whose MIMIC flowsheet label is not the clinical acronym, so a
# plain substring misses the primary item: "RASS" appears only in the secondary
# 'CAM-ICU RASS LOC', while the score itself is labelled 'Richmond-RAS Scale'. Each entry
# ADDS label patterns to the caller's own term rather than replacing it, so an alias can
# only widen a search, never shadow a match the substring would have found. Same role as
# _LAB_ALIASES for labs; extend as other acronym/label mismatches turn up.
_CHART_ALIASES: dict[str, tuple[str, ...]] = {
    "rass": ("richmond-ras",),
    "sedation scale": ("richmond-ras",),
    "cam": ("cam-icu", "delirium assessment"),
    "cam-icu": ("delirium assessment",),
    "delirium": ("cam-icu",),
}


def _expand_concepts(terms: list[str]) -> list[str]:
    """Term list plus any alias patterns, de-duplicated, original order preserved."""
    out: list[str] = []
    for t in terms:
        for cand in (t, *_CHART_ALIASES.get(t.strip().lower(), ())):
            if cand.lower() not in {o.lower() for o in out}:
                out.append(cand)
    return out


def get_chart_timeline(
    subject_id: int,
    concept: str | list[str] | None = None,
    itemid: int | list[int] | None = None,
    hadm_id: int | None = None,
    stay_id: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    """Any ICU charted (flowsheet) observation over time, by concept name or itemid.

    This is the open-vocabulary counterpart to get_vitals_timeline: it reaches the whole
    chartevents/d_items vocabulary — assessment scores, neuro checks, ventilator settings,
    lines/drains, code status — rather than a fixed metric list. For the six standard
    vitals (HR, BP, temperature, RR, SpO2, GCS) prefer get_vitals_timeline: it maps each
    to a curated, mimic-code-validated itemid set (BP spans 9 invasive + non-invasive
    itemids, GCS its 3 components) that a name match here would not reproduce.

    concept matches a case-insensitive substring of the d_items label; pass a LIST to
    match any of several. itemid selects exact itemids instead (or as well). Every row
    reports the itemid and label it came from, so a concept search doubles as the
    dictionary lookup needed to find an itemid.

    Labels are the raw MIMIC flowsheet names, which often are not the clinical acronym —
    the RASS score is labelled "Richmond-RAS Scale", so concept="RASS" matches nothing.
    A concept that matches no label at all therefore RAISES rather than returning [], so
    that "no such concept" is distinguishable from "this patient has no such events";
    the error names the unmatched terms and suggests near matches.

    ONE of concept / itemid is required — chartevents is far too large to return unfiltered.
    """
    terms = _terms(concept)
    ids = [
        int(i)
        for i in (itemid if isinstance(itemid, (list, tuple)) else [itemid])
        if i is not None and str(i).strip() != ""
    ]
    if not terms and not ids:
        raise ValueError(
            "get_chart_timeline needs a concept (label substring) or an itemid — "
            "chartevents is too large to return unfiltered."
        )
    where = ["c.subject_id = ?"]
    params: list[Any] = [subject_id]
    # concept OR itemid: either match is a hit, so the caller can widen a name search
    # with a known itemid in one call.
    ors: list[str] = []
    binds: list[Any] = []
    if ids:
        ors.append("c.itemid IN (" + ",".join(["?"] * len(ids)) + ")")
        binds.extend(ids)
    if terms:
        ors.append(_like_any("di.label", _expand_concepts(terms), binds))
    where.append("(" + " OR ".join(ors) + ")")
    params.extend(binds)
    _window("c.charttime", start_time, end_time, where, params)
    if hadm_id is not None:
        where.append("c.hadm_id = ?")
        params.append(hadm_id)
    if stay_id is not None:
        where.append("c.stay_id = ?")
        params.append(stay_id)
    rows = _safe_rows(
        f"""
        SELECT c.charttime, c.itemid, di.label, di.category, c.value, c.valuenum,
               c.valueuom, c.warning, c.stay_id, c.hadm_id
        FROM chartevents c
        JOIN d_items di USING (itemid)
        WHERE {" AND ".join(where)}
        ORDER BY c.charttime, c.itemid
        LIMIT ?
        """,
        [*params, limit],
    )
    if not rows and terms:
        _raise_if_unknown_concepts(_expand_concepts(terms))
    return rows


def _raise_if_unknown_concepts(terms: list[str]) -> None:
    """Raise if any term matches no chartevents concept at all, so a vocabulary miss is
    not mistaken for an absence of patient data. Only consulted on an empty result, so it
    costs nothing on the common path."""
    unknown: list[str] = []
    for t in terms:
        hit = _safe_rows(
            "SELECT 1 FROM d_items WHERE linksto = 'chartevents' AND LOWER(label) LIKE ? LIMIT 1",
            [f"%{t.lower()}%"],
        )
        if not hit:
            unknown.append(t)
    if not unknown:
        return  # every term exists; the empty result is a genuine absence of data
    hints: list[str] = []
    for t in unknown:
        # Retry on a shortened fragment — "RASS" -> "ras" surfaces "Richmond-RAS Scale".
        frag = t[: max(3, len(t) - 1)].lower()
        near = _safe_rows(
            "SELECT DISTINCT label FROM d_items WHERE linksto = 'chartevents' "
            "AND LOWER(label) LIKE ? ORDER BY label LIMIT 5",
            [f"%{frag}%"],
        )
        if near:
            hints.append(f"{t!r} -> did you mean: " + ", ".join(repr(r["label"]) for r in near))
    raise ValueError(
        "no chartevents concept label matches "
        + ", ".join(repr(t) for t in unknown)
        + " (labels are raw MIMIC flowsheet names, not clinical acronyms). "
        + ("; ".join(hints) if hints else "Try a shorter fragment, or pass itemid directly.")
    )


# ============================= Medications ================================ #


def get_medication_administered(
    subject_id: int,
    drug_name: str | list[str] | None = None,
    hadm_id: int | None = None,
    stay_id: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """What was actually given (EMAR + emar_detail): drug, dose, route, time, event status.

    drug_name matches a case-insensitive substring of the EMAR medication name; pass a
    LIST to match any of several drugs in one call. start_time / end_time bound charttime
    inclusively (administration time, not order time)."""
    where = ["e.subject_id = ?"]
    params: list[Any] = [subject_id]
    if terms := _terms(drug_name):
        where.append(_like_any("e.medication", terms, params))
    _window("e.charttime", start_time, end_time, where, params)
    if hadm_id is not None:
        where.append("e.hadm_id = ?")
        params.append(hadm_id)
    if stay_id is not None:
        where.append(
            "e.charttime BETWEEN (SELECT intime FROM icustays WHERE stay_id = ?) "
            "AND (SELECT outtime FROM icustays WHERE stay_id = ?)"
        )
        params.extend([stay_id, stay_id])
    return _safe_rows(
        f"""
        SELECT e.charttime, e.medication, e.event_txt,
               det.dose_given, det.dose_given_unit AS dose_unit, det.route,
               e.hadm_id, e.emar_id
        FROM emar e
        LEFT JOIN emar_detail det ON det.emar_id = e.emar_id AND det.emar_seq = e.emar_seq
        WHERE {" AND ".join(where)}
        ORDER BY e.charttime
        LIMIT ?
        """,
        [*params, limit],
    )


def get_medication_prescribed(
    subject_id: int,
    drug_name: str | list[str] | None = None,
    hadm_id: int | None = None,
    stay_id: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """What was ordered (prescriptions): drug, dose, route, start/stop, doses/24h.

    drug_name matches a case-insensitive substring of the drug name; pass a LIST to match
    any of several drugs in one call. start_time / end_time bound starttime inclusively —
    an order active across the window but started before it will NOT match, and the ~0.1% of
    prescriptions with no starttime at all cannot be placed in a window so a windowed call
    omits them (there is no alternative timestamp to fall back to)."""
    where = ["p.subject_id = ?"]
    params: list[Any] = [subject_id]
    if terms := _terms(drug_name):
        where.append(_like_any("p.drug", terms, params))
    _window("p.starttime", start_time, end_time, where, params)
    if hadm_id is not None:
        where.append("p.hadm_id = ?")
        params.append(hadm_id)
    if stay_id is not None:
        where.append(
            "p.starttime BETWEEN (SELECT intime FROM icustays WHERE stay_id = ?) "
            "AND (SELECT outtime FROM icustays WHERE stay_id = ?)"
        )
        params.extend([stay_id, stay_id])
    return _safe_rows(
        f"""
        SELECT p.starttime, p.stoptime, p.drug, p.drug_type,
               p.dose_val_rx, p.dose_unit_rx, p.route, p.doses_per_24_hrs, p.hadm_id
        FROM prescriptions p
        WHERE {" AND ".join(where)}
        ORDER BY p.starttime
        LIMIT ?
        """,
        [*params, limit],
    )


def get_icu_administrations(
    subject_id: int,
    drug_name: str | list[str] | None = None,
    itemid: int | list[int] | None = None,
    hadm_id: int | None = None,
    stay_id: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    """ICU infusions and boluses per administration (inputevents): what was given, how
    much, at what rate, over what interval.

    Row-level counterpart to get_fluid_balance, which reports only per-category totals for
    a window. Use this when the timing, rate, or dose of an individual administration
    matters rather than the net balance.

    ICU-only. Floor and ED administrations are recorded in EMAR instead — see
    get_medication_administered — so a patient's full drug exposure across an admission
    may be split between the two, and neither alone is the complete record.

    drug_name matches a case-insensitive substring of the d_items label; pass a LIST to
    match any of several. itemid selects exact itemids. Both are optional: with neither,
    this returns every ICU administration for the scope given (inputevents is small enough
    per patient for that to be reasonable, unlike chartevents).
    """
    terms = _terms(drug_name)
    ids = [
        int(i)
        for i in (itemid if isinstance(itemid, (list, tuple)) else [itemid])
        if i is not None and str(i).strip() != ""
    ]
    where = ["ie.subject_id = ?"]
    params: list[Any] = [subject_id]
    if terms or ids:
        ors: list[str] = []
        binds: list[Any] = []
        if ids:
            ors.append("ie.itemid IN (" + ",".join(["?"] * len(ids)) + ")")
            binds.extend(ids)
        if terms:
            ors.append(_like_any("di.label", terms, binds))
        where.append("(" + " OR ".join(ors) + ")")
        params.extend(binds)
    # starttime, so an infusion running into the window but begun before it is not returned
    _window("ie.starttime", start_time, end_time, where, params)
    if hadm_id is not None:
        where.append("ie.hadm_id = ?")
        params.append(hadm_id)
    if stay_id is not None:
        where.append("ie.stay_id = ?")
        params.append(stay_id)
    return _safe_rows(
        f"""
        SELECT ie.starttime, ie.endtime, ie.itemid, di.label, di.category,
               ie.amount, ie.amountuom, ie.rate, ie.rateuom,
               ie.ordercategoryname, ie.statusdescription, ie.patientweight,
               ie.stay_id, ie.hadm_id
        FROM inputevents ie
        JOIN d_items di USING (itemid)
        WHERE {" AND ".join(where)}
        ORDER BY ie.starttime, ie.itemid
        LIMIT ?
        """,
        [*params, limit],
    )


# ============================= Diagnoses / Procedures ===================== #


def get_diagnosis_history(subject_id: int, keyword: str | None = None) -> list[dict[str, Any]]:
    """ICD diagnoses across all admissions + ED visits, marked by source. keyword
    matches the long title (case-insensitive substring)."""
    kw = f"%{keyword.lower()}%" if keyword else None
    inp_kw = "AND LOWER(dd.long_title) LIKE ?" if kw else ""
    ed_kw = "AND LOWER(ed.icd_title) LIKE ?" if kw else ""
    sql = f"""
        SELECT 'inpatient' AS source, di.hadm_id AS encounter_id, a.admittime, di.seq_num,
               di.icd_code, di.icd_version, dd.long_title
        FROM diagnoses_icd di
        LEFT JOIN d_icd_diagnoses dd USING (icd_code, icd_version)
        JOIN admissions a USING (hadm_id)
        WHERE di.subject_id = ? {inp_kw}
        UNION ALL
        SELECT 'ed' AS source, ed.stay_id AS encounter_id, e.intime AS admittime, ed.seq_num,
               ed.icd_code, ed.icd_version, ed.icd_title AS long_title
        FROM ed_diagnosis ed
        JOIN edstays e USING (stay_id)
        WHERE ed.subject_id = ? {ed_kw}
        ORDER BY admittime, seq_num
    """
    params = [subject_id] + ([kw] if kw else []) + [subject_id] + ([kw] if kw else [])
    return _safe_rows(sql, params)


def get_procedures(
    subject_id: int,
    keyword: str | list[str] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict[str, Any]]:
    """Procedures from procedures_icd (hospital) + procedureevents (ICU), combined.
    keyword matches the ICD long title / ICU item label; pass a LIST to match any of
    several in one call.

    start_time / end_time bound each half on its own time column, and the two halves are
    filtered at DIFFERENT granularity because the sources record time differently:

      ICU (procedureevents.starttime) is a real timestamp — filtered to the instant.
      hospital (procedures_icd.chartdate) is DATE-only, with no time of day anywhere in the
        source — so both bounds are truncated to a date and it matches any row on a day the
        window touches.

    That means a narrow window can return an ICD procedure whose actual time is unknown and
    may lie outside it: the row is included because the data cannot rule it out, not because
    it is confirmed inside. `source` and the date-only `chartdate` on each row show which
    kind of evidence you have. Only the ICU half supports a within-day timing claim."""
    terms = _terms(keyword)

    def _half(label_col: str, time_col: str, grain: str) -> tuple[str, list[Any]]:
        """Extra WHERE text + binds for one system of the UNION, in clause order."""
        clauses: list[str] = []
        binds: list[Any] = [subject_id]
        if terms:
            clauses.append(_like_any(label_col, terms, binds))
        _window(time_col, start_time, end_time, clauses, binds, grain=grain)
        return "".join(f" AND {c}" for c in clauses), binds

    icd_kw, icd_binds = _half("dp.long_title", "p.chartdate", "DATE")
    icu_kw, icu_binds = _half("di.label", "pe.starttime", "TIMESTAMP")
    sql = f"""
        SELECT 'icd' AS source, CAST(p.chartdate AS STRING) AS chartdate,
               CAST(p.icd_code AS STRING) AS code, dp.long_title AS label, p.hadm_id,
               CAST(NULL AS BIGINT) AS stay_id
        FROM procedures_icd p
        LEFT JOIN d_icd_procedures dp USING (icd_code, icd_version)
        WHERE p.subject_id = ? {icd_kw}
        UNION ALL
        SELECT 'icu' AS source, CAST(pe.starttime AS STRING) AS chartdate,
               CAST(pe.itemid AS STRING) AS code, di.label, pe.hadm_id, pe.stay_id
        FROM procedureevents pe
        LEFT JOIN d_items di USING (itemid)
        WHERE pe.subject_id = ? {icu_kw}
        ORDER BY chartdate
    """
    return _safe_rows(sql, [*icd_binds, *icu_binds])


# ============================= Imaging ==================================== #

# Heuristic modality classification from the radiology exam name. This is the one
# place we let a clinical-ish bucket live in a tool; it is intentionally NOT used by
# the cohort tasks, which classify imaging in SQL.
# Word-boundary patterns (checked in order). \bmr catches MR/MRI/MRA/MRV/MRCP;
# \bct catches CT/CTA/CTU; duplex/doppler -> US. Order matters: a "CT CHEST" must
# resolve to CT before the CXR "chest" rule. Only the 5 enum modalities are bucketed
# — plain non-chest films, fluoro, mammo, and IR procedures intentionally stay None.
_MODALITY_RULES = [
    ("MRI", r"\bmr|magnetic reson"),
    ("CT", r"\bct|cat scan|computed tomog"),
    ("US", r"\bus\b|ultrasound|sono|doppler|duplex|\bdup\b"),
    ("TEE", r"\btee\b|transesoph"),
    ("CXR", r"chest|x-?ray|radiograph|portable"),
]


def _classify_modality(label: str | None) -> str | None:
    if not label:
        return None
    low = label.lower()
    for modality, pattern in _MODALITY_RULES:
        if re.search(pattern, low):
            return modality
    return None


def get_imaging_studies(
    subject_id: int,
    modality: str | list[str] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict[str, Any]]:
    """Imaging studies derived from radiology reports, with a heuristic modality bucket
    (CXR/CT/MRI/US/TEE) and the linked note_id. Use get_note(linked_note_id) for the
    impression text. Scope is limited to imaging that produced a radiology report —
    studies without an associated report are not represented here; TEE/echo in
    particular is often not reported.

    modality accepts one bucket or a LIST of them. start_time / end_time bound the report
    charttime inclusively."""
    where = ["r.subject_id = ?"]
    params: list[Any] = [subject_id]
    _window("r.charttime", start_time, end_time, where, params)
    rows = _safe_rows(
        f"""
        SELECT r.note_id, r.hadm_id, r.charttime AS starttime,
               COALESCE(
                 MAX(CASE WHEN rd.field_name = 'exam_name' THEN rd.field_value END),
                 r.note_type
               ) AS label
        FROM radiology_notes r
        LEFT JOIN radiology_detail rd ON rd.note_id = r.note_id
        WHERE {" AND ".join(where)}
        GROUP BY r.note_id, r.hadm_id, r.charttime, r.note_type
        ORDER BY r.charttime
        """,
        params,
    )
    out = []
    for x in rows:
        out.append(
            {
                "starttime": x["starttime"],
                "modality": _classify_modality(x["label"]),
                "label": x["label"],
                "hadm_id": x["hadm_id"],
                "linked_note_id": x["note_id"],
            }
        )
    if wanted := {t.upper() for t in _terms(modality)}:
        out = [x for x in out if x["modality"] in wanted]
    return out


# ============================= Microbiology =============================== #


def get_microbiology_results(
    subject_id: int,
    specimen_type: str | list[str] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict[str, Any]]:
    """Microbiology in wide form — one row per (specimen, organism, antibiotic) so the
    sensitivity profile reads directly.

    specimen_type matches a case-insensitive substring; pass a LIST to match any of
    several specimen types in one call. start_time / end_time bound charttime inclusively
    (collection time, not result time)."""
    where = ["subject_id = ?"]
    params: list[Any] = [subject_id]
    if terms := _terms(specimen_type):
        where.append(_like_any("spec_type_desc", terms, params))
    # charttime is NULL on ~9% of rows (chartdate is always populated there) and a NULL
    # satisfies no window predicate, so filtering on charttime alone silently drops those
    # cultures — which is exactly the timing evidence a bundle question turns on.
    _window("COALESCE(charttime, chartdate)", start_time, end_time, where, params)
    return _safe_rows(
        f"""
        SELECT charttime, spec_type_desc, test_name, org_name, ab_name,
               interpretation, dilution_value, comments
        FROM microbiologyevents
        WHERE {" AND ".join(where)}
        ORDER BY charttime, org_name
        """,
        params,
    )


# ============================= Fluid balance ============================== #


# Canonical urine outputevents itemids (mimic-code measurement/urine_output.sql).
# 227488 (GU irrigant instilled) is subtracted to net out true urine.
_URINE_ITEMS = [
    226559,
    226560,
    226561,
    226563,
    226564,
    226565,
    226567,
    226584,
    226557,
    226558,
    227489,
]
_URINE_IRRIGANT_IN = 227488


def get_fluid_balance(
    subject_id: int,
    stay_id: int,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """ICU intake (inputevents) and output (outputevents) over a window, with category
    breakdowns and totals, plus a canonical net urine output (mimic-code itemids,
    irrigant netted out). NOTE: intake amounts mix units (mL, mg, units); the in/out
    totals are naive sums — read the per-category uom before interpreting volume.
    urine_output_ml is the reliable volume figure."""
    in_where = ["subject_id = ?", "stay_id = ?"]
    in_params: list[Any] = [subject_id, stay_id]
    _window("starttime", start_time, end_time, in_where, in_params)
    intake = _safe_rows(
        f"""
        SELECT ordercategoryname AS category, SUM(amount) AS total_amount,
               MAX(amountuom) AS uom, COUNT(*) AS n
        FROM inputevents WHERE {" AND ".join(in_where)}
        GROUP BY ordercategoryname ORDER BY total_amount DESC
        """,
        in_params,
    )
    out_where = ["o.subject_id = ?", "o.stay_id = ?"]
    out_params: list[Any] = [subject_id, stay_id]
    _window("o.charttime", start_time, end_time, out_where, out_params)
    output = _safe_rows(
        f"""
        SELECT di.label AS category, SUM(o.value) AS total_amount,
               MAX(o.valueuom) AS uom, COUNT(*) AS n
        FROM outputevents o LEFT JOIN d_items di USING (itemid)
        WHERE {" AND ".join(out_where)}
        GROUP BY di.label ORDER BY total_amount DESC
        """,
        out_params,
    )
    urine_ids = ",".join(str(i) for i in [*_URINE_ITEMS, _URINE_IRRIGANT_IN])
    urine_rows = _safe_rows(
        f"""
        SELECT SUM(CASE WHEN o.itemid = {_URINE_IRRIGANT_IN} THEN -o.value ELSE o.value END) AS urine_ml
        FROM outputevents o
        WHERE {" AND ".join(out_where)} AND o.itemid IN ({urine_ids})
        """,
        out_params,
    )
    urine_output = (
        urine_rows[0]["urine_ml"] if urine_rows and urine_rows[0]["urine_ml"] is not None else 0
    )
    total_in = sum((r["total_amount"] or 0) for r in intake)
    total_out = sum((r["total_amount"] or 0) for r in output)
    return {
        "stay_id": stay_id,
        "total_in": total_in,
        "total_out": total_out,
        "net_balance": total_in - total_out,
        "urine_output_ml": urine_output,
        "intake_by_category": intake,
        "output_by_category": output,
    }


# ============================= Orders (POE) =============================== #


def list_orders(
    subject_id: int,
    hadm_id: int | None = None,
    order_type: str | list[str] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    """Provider-entered orders from POE, with poe_detail key/values attached.

    order_type matches a case-insensitive substring; pass a LIST to match any of several
    types in one call. start_time / end_time bound ordertime inclusively — this is when the
    order was entered, not when it was carried out (see get_medication_administered)."""
    where = ["p.subject_id = ?"]
    params: list[Any] = [subject_id]
    if hadm_id is not None:
        where.append("p.hadm_id = ?")
        params.append(hadm_id)
    if terms := _terms(order_type):
        where.append(_like_any("p.order_type", terms, params))
    _window("p.ordertime", start_time, end_time, where, params)
    rows = _safe_rows(
        f"""
        SELECT p.poe_id, p.ordertime, p.order_type, p.order_subtype,
               p.transaction_type, p.order_status, p.order_provider_id, p.hadm_id
        FROM poe p
        WHERE {" AND ".join(where)}
        ORDER BY p.ordertime
        LIMIT ?
        """,
        [*params, limit],
    )
    if not rows:
        return rows
    # One query for the details of just the orders we returned (avoids an N+1 per order
    # and doesn't over-fetch beyond the page), then group by poe_id in Python. subject_id
    # is kept so BigQuery can prune; poe_id IN (...) scopes to the returned rows.
    poe_ids = [r["poe_id"] for r in rows]
    placeholders = ",".join(["?"] * len(poe_ids))
    details = _safe_rows(
        f"SELECT poe_id, field_name, field_value FROM poe_detail "
        f"WHERE subject_id = ? AND poe_id IN ({placeholders})",
        [subject_id, *poe_ids],
    )
    by_poe: dict[Any, dict[str, Any]] = {}
    for d in details:
        by_poe.setdefault(d["poe_id"], {})[d["field_name"]] = d["field_value"]
    for r in rows:
        r["details"] = by_poe.get(r["poe_id"], {})
    return rows


# ============================= Notes ===================================== #


def list_notes(
    subject_id: int, hadm_id: int | None = None, note_type: str | None = None
) -> list[dict[str, Any]]:
    """List note metadata (no text). note_type: 'discharge' | 'radiology' | None (both).
    Returns note_ids to pass to get_note."""
    out: list[dict[str, Any]] = []
    for table, ntype in (("discharge_notes", "discharge"), ("radiology_notes", "radiology")):
        if note_type not in (None, ntype):
            continue
        where = ["subject_id = ?"]
        params: list[Any] = [subject_id]
        if hadm_id is not None:
            where.append("hadm_id = ?")
            params.append(hadm_id)
        out.extend(
            _safe_rows(
                f"""
                SELECT note_id, '{ntype}' AS note_type, charttime, hadm_id,
                       note_type AS raw_note_type, LENGTH(text) AS text_chars
                FROM {table}
                WHERE {" AND ".join(where)}
                ORDER BY charttime
                """,
                params,
            )
        )
    out.sort(key=lambda r: r.get("charttime") or "")
    return out


def get_note(note_id: str) -> dict[str, Any] | None:
    """Full text of one note. Notes contain `___` placeholders for de-identified PHI."""
    for table, ntype in (("discharge_notes", "discharge"), ("radiology_notes", "radiology")):
        rows = _safe_rows(
            f"SELECT note_id, '{ntype}' AS note_type, subject_id, hadm_id, charttime, text "
            f"FROM {table} WHERE note_id = ?",
            [note_id],
        )
        if rows:
            return rows[0]
    return None


# ============================= Note search ================================ #


def _nearest_header(text: str, idx: int) -> str | None:
    """Best-effort: the nearest preceding line that looks like a section header."""
    head = text[:idx]
    for line in reversed(head.splitlines()):
        s = line.strip()
        if not s:
            continue
        # ALL-CAPS-ish line or a 'Header:' label
        if (s.isupper() and len(s) <= 60) or re.match(r"^[A-Z][A-Za-z /]{2,40}:\s*$", s):
            return s.rstrip(":")
    return None


def search_notes(
    subject_id: int, keyword: str, max_hits: int = 50, max_notes: int = 100
) -> list[dict[str, Any]]:
    """Keyword search across a patient's discharge + radiology notes. Returns snippets
    (±120 chars) with a best-effort section label for discharge summaries.

    Searches the most recent `max_notes` matching notes per type (bounds how much full
    text is pulled) and returns up to `max_hits` snippets.

    Caveat: substring search cannot prove a concept's ABSENCE — a zero-hit result does
    not mean the concept was not addressed. Read full notes via get_note for that.
    """
    kw = keyword.strip()
    out: list[dict[str, Any]] = []
    for table, ntype in (("discharge_notes", "discharge"), ("radiology_notes", "radiology")):
        notes = _safe_rows(
            f"SELECT note_id, charttime, hadm_id, text FROM {table} "
            f"WHERE subject_id = ? AND LOWER(text) LIKE ? "
            f"ORDER BY charttime DESC LIMIT ?",
            [subject_id, f"%{kw.lower()}%", max_notes],
        )
        for r in notes:
            text = r["text"] or ""
            low, k = text.lower(), kw.lower()
            start = 0
            while True:
                hit = low.find(k, start)
                if hit == -1:
                    break
                s, e = max(0, hit - 120), min(len(text), hit + len(kw) + 120)
                snippet = "…" + text[s:e].replace("\n", " ").strip() + "…"
                out.append(
                    {
                        "note_id": r["note_id"],
                        "note_type": ntype,
                        "charttime": r["charttime"],
                        "snippet": snippet,
                        "section": _nearest_header(text, hit) if ntype == "discharge" else None,
                    }
                )
                if len(out) >= max_hits:
                    return out
                start = hit + len(kw)
    return out


# ============================= run_sql ==================================== #

# Read-only guard: defence in depth, NOT the boundary. A SQL-text denylist cannot be the
# control, because DuckDB's file-reading table functions (read_text, read_blob, glob) contain
# none of these keywords — `SELECT * FROM read_text('/proc/self/environ')` passes every check
# below. The actual boundary is the connection-level lockdown in db._restrict_duck_filesystem,
# which confines file access to the MIMIC tree. What this guard buys is a clear error on an
# accidental write instead of a permission failure from DuckDB.
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|pragma|"
    r"install|load|export|truncate|vacuum|checkpoint)\b",
    re.IGNORECASE,
)
# The guards below scan a copy with quoted-span CONTENTS blanked, so a clinical pattern
# like LIKE '%drop%' or "drop" (or a ';' / keyword inside a literal or a `quoted` alias)
# doesn't trip the read-only check. The quote handling lives in db (single source of
# truth, shared with _bq_qualify) so both stay in sync across all three SQL quote styles.


def run_sql(query: str, max_rows: int = 1000) -> dict[str, Any]:
    """Execute a single read-only SELECT / WITH query against the MIMIC views.

    Caps the result at max_rows and surfaces a `truncated` flag (never silently
    drops rows). All logical tables in db.TABLES are available (same names on every
    backend); compare timestamps to literals via CAST(... AS TIMESTAMP).

    Don't reuse a MIMIC table name as a CTE or alias (e.g. `WITH labevents AS ...`):
    on the BigQuery backend it's rewritten to the physical table and rejected — name
    the CTE/alias something else (`labevents_cte`).
    """
    q = query.strip().rstrip(";").strip()
    low = q.lower()
    guard = db.SQL_QUOTED_SPAN_RE.sub("''", q)  # blank quoted-span contents so guards ignore them
    if not (low.startswith("select") or low.startswith("with")):
        raise ValueError("run_sql only supports read-only SELECT / WITH queries.")
    if ";" in guard:
        raise ValueError("run_sql supports a single statement (no ';').")
    if _FORBIDDEN.search(guard):
        raise ValueError("run_sql rejected: query contains a non-read-only keyword.")

    cols, rows, truncated = db.fetch(q, max_rows=max_rows)
    return {
        "columns": cols,
        "rows": rows,
        "returned": len(rows),
        "truncated": truncated,
        "note": (
            f"Showing first {max_rows} rows; result was truncated — refine or aggregate."
            if truncated
            else None
        ),
    }


# ============================= Policy docs ================================ #
# A staged, read-only Markdown corpus of clinical policy / guideline documents, searched with
# the same glob / grep / read semantics as a filesystem (mirroring the file-search harness).
# Line numbers are PHYSICAL 1-indexed file lines so a citation like `[policy: <doc> L120-L134]`
# resolves against the exact same lines a verifier reads. The corpus dir is staged into the
# trial container at POLICY_CORPUS_DIR (Harbor uploads the task's environment/ to /workspace);
# read at call time so tests can point it elsewhere.


def _policy_dir() -> Path:
    return Path(os.environ.get("POLICY_CORPUS_DIR", "/workspace/policy_corpus"))


#: Markdown files in the corpus dir that are documentation ABOUT the corpus rather than policy
#: documents. Every layout the corpus ships in can carry one -- the repo's benchmark/corpus/, and
#: any distributed bundle that keeps its licence terms next to the bytes -- and its content
#: describes the grading the agent is being scored by, so it must not be searchable.
_NOT_POLICY_DOCS = frozenset({"README.md"})


def _corpus_files() -> list[Path]:
    d = _policy_dir()
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.md") if p.name not in _NOT_POLICY_DOCS)


#: path -> ((size, mtime_ns), text, lines) for one corpus doc. One entry per path, so the
#: cache is bounded by the corpus (67 docs), and a changed file replaces its own entry.
_POLICY_TEXT_CACHE: dict[Path, tuple[tuple[int, int], str, list[str]]] = {}


def _policy_text(p: Path) -> tuple[str, list[str]]:
    """The doc's text and physical lines, re-read only when (size, mtime) changes.

    Pure caching: returns exactly what `p.read_text(errors="replace")` and `.splitlines()`
    return, so every tool's output is byte-identical with and without this.

    Why it exists. `list_policy_docs` and `search_policy` each read EVERY doc on EVERY call --
    the whole corpus, tens of MB -- and agents call them dozens to hundreds of times per trial.
    That is gigabytes of repeat reads of a corpus that is staged read-only before the agent starts
    and cannot change during the trial. Under host load it pushed a single `list_policy_docs` past
    the client's tool timeout, which stalls a trial rather than merely slowing it.

    Not cached deliberately: `_corpus_files()` still globs per call. Directory listing is one
    readdir over a few dozen entries, not the expensive part, and caching it would mean a doc added
    between two calls could be missed within one mtime tick -- a behaviour change. Only file
    CONTENT is memoised, and each file carries its own stat key.

    Callers must treat the returned list as read-only; it is shared, not copied. All three
    call sites below only index into it.
    """
    try:
        st = p.stat()
    except OSError:
        # Let the caller's own error path handle an unreadable file exactly as before.
        text = p.read_text(errors="replace")
        return text, text.splitlines()
    key = (st.st_size, st.st_mtime_ns)
    hit = _POLICY_TEXT_CACHE.get(p)
    if hit is not None and hit[0] == key:
        return hit[1], hit[2]
    text = p.read_text(errors="replace")
    lines = text.splitlines()
    # No lock: a concurrent miss costs one duplicate read and both writers store the same
    # value for the same key, so the cache cannot go inconsistent.
    _POLICY_TEXT_CACHE[p] = (key, text, lines)
    return text, lines


#: path -> ((size, mtime_ns), {doc,title,lines,words}) for `list_policy_docs`.
_POLICY_META_CACHE: dict[Path, tuple[tuple[int, int], dict[str, Any]]] = {}


def _policy_meta(p: Path) -> dict[str, Any]:
    """The `list_policy_docs` row for one doc, recomputed only when (size, mtime) changes.

    Caching the file text alone is not enough: the row's `title`/`lines`/`words` are derived by
    running a frontmatter regex, a newline count and `text.split()` over the whole document, and
    `split()` on a 12 MB corpus dominates the call once the reads are cached. Those three values
    are a pure function of the file, so they key off the same stat pair.

    Returns a fresh dict per call so a caller mutating a row cannot poison the cache.
    """
    try:
        st = p.stat()
        key = (st.st_size, st.st_mtime_ns)
    except OSError:
        key = None
    if key is not None:
        hit = _POLICY_META_CACHE.get(p)
        if hit is not None and hit[0] == key:
            return dict(hit[1])
    text, _ = _policy_text(p)
    row = {
        "doc": p.name,
        "title": _frontmatter_title(text) or p.stem,
        "lines": text.count("\n") + 1,
        "words": len(text.split()),
    }
    if key is not None:
        _POLICY_META_CACHE[p] = (key, row)
    return dict(row)


def _resolve_doc(name: str) -> Path | None:
    """Match a doc by filename or basename, with or without the .md suffix."""
    by_name = {p.name: p for p in _corpus_files()}
    for cand in (name, f"{name}.md", Path(name).name, f"{Path(name).name}.md"):
        if cand in by_name:
            return by_name[cand]
    return None


def _frontmatter_title(text: str) -> str | None:
    m = re.match(r"---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return None
    mt = re.search(r'^title:\s*"?(.*?)"?\s*$', m.group(1), re.MULTILINE)
    return mt.group(1).strip() if mt else None


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def list_policy_docs(pattern: str | None = None) -> list[dict[str, Any]]:
    """List the policy/guideline documents in the corpus (filename, title, line/word counts).
    Your index into the corpus — start here, then search_policy to find passages and read_policy
    to read them. `pattern` optionally filters filenames as a glob (e.g. '*kidney*')."""
    out: list[dict[str, Any]] = []
    for p in _corpus_files():
        if pattern and not fnmatch.fnmatch(p.name, pattern):
            continue
        out.append(_policy_meta(p))
    return out


def search_policy(
    query: str,
    regex: Any = False,
    case_sensitive: Any = False,
    context_lines: int = 0,
    max_results: int = 50,
) -> list[dict[str, Any]] | dict[str, str]:
    """Search the policy corpus (like grep). Returns line-anchored matches — {doc, line, text}
    with PHYSICAL 1-indexed line numbers — so you can cite an exact span and read_policy around
    it. `regex` treats query as a regular expression; `context_lines` attaches N surrounding
    lines (numbered) as a `context` field. Capped at `max_results` (raise it to see more)."""
    cased = _truthy(case_sensitive)
    if _truthy(regex):
        try:
            pat = re.compile(query, 0 if cased else re.IGNORECASE)
        except re.error as e:
            return {"error": f"invalid regex: {e}"}
        matches = lambda line: pat.search(line) is not None
    else:
        needle = query if cased else query.lower()
        matches = lambda line: needle in (line if cased else line.lower())

    ctx = max(0, int(context_lines or 0))
    cap = int(max_results or 50)
    results: list[dict[str, Any]] = []
    for p in _corpus_files():
        _, lines = _policy_text(p)
        for i, line in enumerate(lines, 1):
            if not matches(line):
                continue
            hit: dict[str, Any] = {"doc": p.name, "line": i, "text": line.strip()}
            if ctx:
                lo, hi = max(1, i - ctx), min(len(lines), i + ctx)
                hit["context"] = "\n".join(f"{n}: {lines[n - 1]}" for n in range(lo, hi + 1))
            results.append(hit)
            if len(results) >= cap:
                return results
    return results


def read_policy(
    doc: str, line_start: int | None = None, line_end: int | None = None
) -> dict[str, Any]:
    """Read a policy document, or a line range (like cat / head / tail). Returns the text with
    PHYSICAL 1-indexed line-number prefixes so you can quote and cite an exact span as
    `[policy: <doc> L<start>-L<end>]`. Omit line_start/line_end for the whole document."""
    p = _resolve_doc(doc)
    if p is None:
        return {
            "error": f"no such policy doc: {doc!r} (use list_policy_docs to see available files)"
        }
    _, lines = _policy_text(p)
    n = len(lines)
    start = max(1, int(line_start)) if line_start not in (None, "") else 1
    end = min(n, int(line_end)) if line_end not in (None, "") else n
    body = "" if start > end else "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1))
    return {"doc": p.name, "line_start": start, "line_end": end, "lines": n, "text": body}
