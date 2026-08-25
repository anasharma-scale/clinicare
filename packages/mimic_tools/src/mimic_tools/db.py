"""Database backend for the MIMIC tool surface — the only file that knows *where*
the data lives. tools.py is backend-agnostic: it writes SQL against LOGICAL table
names (labevents, discharge_notes, ed_triage, ...) and calls db.safe_query / db.fetch.

Either backend requires PhysioNet credentialing for MIMIC-IV; neither ships any data.
Backend is chosen by the MIMIC_BACKEND env var:

  duckdb   (default) — DuckDB over a LOCAL Parquet copy of MIMIC-IV, at MIMIC_DATA_ROOT.
                       Recommended: no per-query cost, no auth to expire mid-run, and a
                       frozen snapshot so results stay reproducible. Build it once with
                       the converter (see DATA_ACCESS.md) — the raw PhysioNet download is
                       gzipped CSV, which DuckDB cannot prune or push predicates into, so
                       querying it directly is orders of magnitude too slow to be usable.
  bigquery           — MIMIC-IV on PhysioNet's BigQuery: credential on PhysioNet, link
                       your Google account, `gcloud auth application-default login`, and
                       set MIMIC_BQ_BILLING_PROJECT to your own GCP project. Mind the
                       cost — physionet-data is unclustered, so every patient-scoped query
                       scans whole columns. DATA_ACCESS.md has the clustered-copy recipe.

Logical table names are identical across backends, so the same tool SQL — and the same
run_sql queries a user writes — run unchanged on either.
"""

from __future__ import annotations

import contextlib
import contextvars
import datetime
import json
import os
import re
import threading
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

BACKEND = os.environ.get("MIMIC_BACKEND", "duckdb").lower()

# logical name -> (module, physical table). module is hosp | icu | ed | note.
# The DuckDB backend creates a view per logical name; the BigQuery backend rewrites
# logical names to `project.dataset.table`. Note the logical names intentionally
# differ from physical ones in a few places (ed_triage->triage, discharge_notes->discharge).
#
# This mirrors the ENTIRE mimic-parquet bucket so run_sql has no blind spots — every
# table is reachable; the semantic tools use a subset. Low-signal tables (de-identified
# id dictionaries, note author) are included for completeness and flagged inline.
TABLES: dict[str, tuple[str, str]] = {
    "patients": ("hosp", "patients"),
    "admissions": ("hosp", "admissions"),
    "transfers": ("hosp", "transfers"),
    "services": ("hosp", "services"),
    "drgcodes": ("hosp", "drgcodes"),
    "diagnoses_icd": ("hosp", "diagnoses_icd"),
    "d_icd_diagnoses": ("hosp", "d_icd_diagnoses"),
    "procedures_icd": ("hosp", "procedures_icd"),
    "d_icd_procedures": ("hosp", "d_icd_procedures"),
    "hcpcsevents": ("hosp", "hcpcsevents"),
    "labevents": ("hosp", "labevents"),
    "d_labitems": ("hosp", "d_labitems"),
    "prescriptions": ("hosp", "prescriptions"),
    "emar": ("hosp", "emar"),
    "emar_detail": ("hosp", "emar_detail"),
    "poe": ("hosp", "poe"),
    "poe_detail": ("hosp", "poe_detail"),
    "microbiologyevents": ("hosp", "microbiologyevents"),
    "omr": ("hosp", "omr"),
    "pharmacy": ("hosp", "pharmacy"),
    "d_hcpcs": ("hosp", "d_hcpcs"),
    "provider": ("hosp", "provider"),
    "icustays": ("icu", "icustays"),
    "chartevents": ("icu", "chartevents"),
    "d_items": ("icu", "d_items"),
    "inputevents": ("icu", "inputevents"),
    "outputevents": ("icu", "outputevents"),
    "procedureevents": ("icu", "procedureevents"),
    "datetimeevents": ("icu", "datetimeevents"),
    "ingredientevents": ("icu", "ingredientevents"),
    "caregiver": ("icu", "caregiver"),
    "edstays": ("ed", "edstays"),
    "ed_triage": ("ed", "triage"),
    "ed_vitalsign": ("ed", "vitalsign"),
    "ed_diagnosis": ("ed", "diagnosis"),
    "ed_pyxis": ("ed", "pyxis"),
    "medrecon": ("ed", "medrecon"),
    "discharge_notes": ("note", "discharge"),
    "discharge_detail": ("note", "discharge_detail"),
    "radiology_notes": ("note", "radiology"),
    "radiology_detail": ("note", "radiology_detail"),
}


def _coerce(v: Any) -> Any:
    if isinstance(v, datetime.datetime):
        return v.isoformat(sep=" ")
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


# ----------------------------- DuckDB (local Parquet) --------------------- #
# Expects <MIMIC_DATA_ROOT>/{hosp,icu,ed,note}/<table>.parquet — the layout the converter
# emits, which mirrors PhysioNet's own module directories. Everything is a plain local file
# read: no network, no credentials, no extensions to install.


def data_root() -> Path:
    """The configured Parquet root, validated. Raises a RuntimeError that says what to do."""
    raw = os.environ.get("MIMIC_DATA_ROOT", "").strip()
    if not raw:
        raise RuntimeError(
            "MIMIC_DATA_ROOT is not set. The DuckDB backend reads a local Parquet copy of "
            "MIMIC-IV; point MIMIC_DATA_ROOT at it (expects <root>/{hosp,icu,ed,note}/"
            "<table>.parquet). You need PhysioNet credentialing for MIMIC-IV first — see "
            "DATA_ACCESS.md for obtaining it and building the Parquet copy."
        )
    root = Path(raw).expanduser()
    if not root.is_dir():
        raise RuntimeError(f"MIMIC_DATA_ROOT does not exist or is not a directory: {root}")
    # A very common wrong turn: pointing this at the raw PhysioNet download. Gzipped CSV can't
    # be column-pruned or predicate-pushed and gzip isn't splittable, so DuckDB re-reads and
    # re-decompresses whole tables on every call — chartevents alone is ~433M rows. It "works"
    # and is unusably slow, which is far worse to debug than a refusal, so refuse.
    if not any(root.glob("*/*.parquet")) and any(root.glob("*/*.csv.gz")):
        raise RuntimeError(
            f"{root} holds the raw PhysioNet .csv.gz download, not Parquet. Querying gzipped "
            "CSV directly is not viable (no predicate pushdown, no column pruning, and gzip "
            "is not splittable, so every tool call rescans entire tables). Convert it once "
            "first — see DATA_ACCESS.md."
        )
    return root


def _table_path(module: str, table: str) -> Path:
    return data_root() / module / f"{table}.parquet"


def _build_duck_conn():
    """Open the DuckDB connection and define one view per logical table over the Parquet root.

    In-memory by default: the views are cheap to recreate, and a persistent file would take an
    exclusive lock that collides with anything else opening the same path — a second tool
    process, or an agent running its own DuckDB script against the same path. Set MIMIC_DB_PATH
    only to deliberately share an on-disk database."""
    import duckdb

    root = data_root()
    missing = [
        f"{module}/{table}.parquet"
        for module, table in TABLES.values()
        if not _table_path(module, table).is_file()
    ]
    # Refuse a partial dataset rather than serving it. A missing table degrades into empty tool
    # results, and an agent reading empty results concludes "Indeterminate - lack of data" —
    # a plausible-looking wrong answer instead of an error, and one that reads as a model
    # failure rather than a setup one. A loud failure at startup is strictly cheaper.
    if missing and os.environ.get("MIMIC_ALLOW_PARTIAL", "").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        shown = ", ".join(missing[:6]) + (
            f" (+{len(missing) - 6} more)" if len(missing) > 6 else ""
        )
        raise RuntimeError(
            f"{len(missing)} of {len(TABLES)} MIMIC tables are missing under {root}: {shown}. "
            "The conversion is probably incomplete — re-run the converter (DATA_ACCESS.md). "
            "Set MIMIC_ALLOW_PARTIAL=1 to proceed anyway, but expect tools over the missing "
            "tables to return empty rather than to fail."
        )

    path = os.environ.get("MIMIC_DB_PATH") or ":memory:"
    if path != ":memory:":
        os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = duckdb.connect(path)
    for logical, (module, table) in TABLES.items():
        src = _table_path(module, table)
        if not src.is_file():
            continue  # only reachable under MIMIC_ALLOW_PARTIAL; the view is simply not created
        conn.execute(
            f"CREATE OR REPLACE VIEW {logical} AS SELECT * FROM read_parquet('{src.as_posix()}')"
        )
    _restrict_duck_filesystem(conn, path)
    return conn


def _restrict_duck_filesystem(conn, db_path: str) -> None:
    """Confine this connection's file access to the MIMIC tree, then lock the config.

    THIS is the security boundary for run_sql, not the keyword denylist in tools.py. DuckDB's
    file-reading table functions (read_text, read_blob, read_csv, glob) contain none of the
    denylisted keywords, so `SELECT * FROM read_text('/proc/self/environ')` sails through a
    SQL-text guard and executes here — in the one process holding the MIMIC credentials. That
    hands the agent the creds and lets it query the raw tables outside the governed tool
    surface, which is the exact bypass the sidecar exists to remove (SIDECAR.md).

    Order matters and is not obvious:
      1. views first — they read Parquet lazily, so they must be *created* before access closes,
         and the data root must stay reachable *after* it, or every view raises at query time.
      2. allowed_directories is INERT on its own; it only becomes an allowlist once
         enable_external_access is false. Setting just the directories restricts nothing.
      3. lock_configuration last, so the agent cannot SET its way back out.
    Neither setting can be passed to duckdb.connect(config=...) — allowed_directories rejects
    being set before the database starts. It has to be this post-connect sequence.
    """
    allowed = [data_root().as_posix()]
    if db_path != ":memory:":
        # The database file (and its WAL) live outside the data root; DuckDB needs them
        # reachable for checkpoints.
        allowed.append(os.path.dirname(os.path.abspath(db_path)))
    dirs = ", ".join("'" + d.replace("'", "''") + "'" for d in allowed)
    try:
        conn.execute(f"SET allowed_directories=[{dirs}]")
        conn.execute("SET enable_external_access=false")
        conn.execute("SET lock_configuration=true")
    except Exception as exc:
        # Fail closed. A DuckDB too old for allowed_directories (<1.2) would otherwise serve an
        # unrestricted connection while looking healthy, and the bypass is silent by nature —
        # nothing in a trial's output would reveal that the boundary was never applied.
        raise RuntimeError(
            "Could not restrict DuckDB file access, so run_sql would be able to read arbitrary "
            f"files in this process (see SIDECAR.md): {exc}. This needs duckdb>=1.2 for "
            "allowed_directories; check the installed version."
        ) from exc


_duck_conn_holder: list = [None]
_duck_conn_lock = threading.Lock()


def _duck_conn():
    """Process-wide DuckDB connection, built once under a lock.

    The lock is the whole point: an agent's first tool calls can fire concurrently (each tool
    runs on its own thread) and would otherwise race to build the connection. There is no retry
    — these are local file reads, so a failure here means misconfiguration or an incomplete
    dataset, and neither improves by trying again."""
    conn = _duck_conn_holder[0]
    if conn is not None:
        return conn
    with _duck_conn_lock:
        if _duck_conn_holder[0] is None:  # may have been built while we waited on the lock
            _duck_conn_holder[0] = _build_duck_conn()
        return _duck_conn_holder[0]


def warmup() -> None:
    """Build the connection eagerly at startup, single-threaded, so the ~40 view definitions
    are paid once rather than racing an agent's first concurrent tool calls. No-op on BigQuery.
    Raises if the connection can't be built; callers that must still serve a tool list on a
    data failure (the MCP server) should catch and log."""
    if BACKEND != "duckdb":
        return
    _duck_conn()


def preflight() -> None:
    """Fail-fast data check, cheap enough to run as a per-trial healthcheck: validate the root
    and read one row from a small dimension table on a throwaway connection (it does NOT build
    all ~40 views like warmup). Raises RuntimeError with an actionable message. No-op on
    BigQuery, whose credentials are per-request."""
    if BACKEND != "duckdb":
        return
    import duckdb

    probe = _table_path("hosp", "d_icd_procedures")  # small hosp dimension table
    if not probe.is_file():
        raise RuntimeError(
            f"MIMIC preflight failed: {probe} not found. MIMIC_DATA_ROOT={data_root()} does not "
            "contain a complete Parquet conversion — see DATA_ACCESS.md."
        )
    conn = duckdb.connect()
    try:
        conn.execute(f"SELECT 1 FROM read_parquet('{probe.as_posix()}') LIMIT 1").fetchone()
    except Exception as exc:
        raise RuntimeError(f"MIMIC preflight failed reading {probe}: {exc}") from exc
    finally:
        conn.close()


def _duck_fetch(sql, params, max_rows):
    # .cursor() shares the catalog (so the table views are visible) but isolates execution
    # state — a single DuckDB connection isn't safe for concurrent .execute(), and the MCP
    # server runs each tool call on its own thread, so parallel tool calls would otherwise
    # corrupt each other's cursor (IndexError / wrong rows).
    cur = _duck_conn().cursor().execute(sql, list(params or []))
    cols = [c[0] for c in cur.description]
    if max_rows is None:
        data, truncated = cur.fetchall(), False
    else:
        data = cur.fetchmany(max_rows + 1)
        truncated = len(data) > max_rows
        data = data[:max_rows]
    return cols, [{c: _coerce(v) for c, v in zip(cols, r)} for r in data], truncated


# ----------------------------- BigQuery (PhysioNet) ----------------------- #
# Dataset names VARY BY MIMIC VERSION — these defaults target MIMIC-IV v3.1 hosp/icu/ed
# + the Note module. VERIFY them against your PhysioNet BigQuery access and override
# via env (MIMIC_BQ_DATASET_HOSP, ...) if they differ.
BQ_PROJECT = os.environ.get("MIMIC_BQ_PROJECT", "physionet-data")
_BQ_DATASETS = {
    "hosp": os.environ.get("MIMIC_BQ_DATASET_HOSP", "mimiciv_3_1_hosp"),
    "icu": os.environ.get("MIMIC_BQ_DATASET_ICU", "mimiciv_3_1_icu"),
    "ed": os.environ.get("MIMIC_BQ_DATASET_ED", "mimiciv_ed"),
    "note": os.environ.get("MIMIC_BQ_DATASET_NOTE", "mimiciv_note"),
}
# Match logical table names as whole words (longest first so e.g. emar_detail beats emar).
_TABLE_ALT = "|".join(sorted(TABLES, key=len, reverse=True))
_TABLE_RE = re.compile(r"\b(" + _TABLE_ALT + r")\b")
# Quoted spans in SQL that must be treated as opaque — a logical table name, keyword, or
# separator appearing INSIDE one is data/identifier text, not something to rewrite or
# scan. Three quote styles, each backend-dependent:
#   '...'  string literal (both backends; '' escapes a quote)
#   "..."  string literal in BigQuery / quoted identifier in DuckDB ("" escapes a quote)
#   `...`  quoted identifier in BigQuery (e.g. an `AS `labevents`` alias)
# A logical table name inside any of these (a literal value, or an aliased identifier)
# must be left untouched. SINGLE SOURCE OF TRUTH: tools.run_sql's read-only guard imports
# this too, so the guard and _bq_qualify agree on what counts as an inert span — keep the
# quote handling here, not duplicated per call site.
SQL_QUOTED_SPAN_RE = re.compile(
    r"'(?:[^']|'')*'"  # '...'  single-quoted literal
    r'|"(?:[^"]|"")*"'  # "..."  double-quoted literal / identifier
    r"|`(?:[^`])*`"  # `...`  backtick identifier (BigQuery)
)


# A contributor's run_sql query can't reuse a MIMIC table name as a CTE or alias: the
# rewrite below would turn the *declaration* into a qualified physical name — invalid SQL
# (WITH `physionet-data...labevents` AS ...), or silently repoint an alias at the real
# table. A regex can't track SQL scope to rewrite these correctly, so instead we detect
# the two collision shapes and fail with a clear message. BigQuery-only: DuckDB does no
# rewrite, so the same query runs fine there (the table name is just shadowed normally).
# The table name matches case-sensitively (mirroring _TABLE_RE, so we only flag names the
# rewrite would actually touch); the AS keyword is case-insensitive.
_CTE_COLLISION_RE = re.compile(r"\b(" + _TABLE_ALT + r")\s+[Aa][Ss]\s*\(")  # `<table> AS (`
_ALIAS_COLLISION_RE = re.compile(r"\b[Aa][Ss]\s+(" + _TABLE_ALT + r")\b")  # `AS <table>`


def _bq_qualify(sql: str) -> str:
    def repl(m: re.Match) -> str:
        module, table = TABLES[m.group(1)]
        return f"`{BQ_PROJECT}.{_BQ_DATASETS[module]}.{table}`"

    # Detect CTE/alias collisions on a literal-masked copy (so names inside quoted spans
    # don't false-trigger), and reject before producing broken SQL.
    masked = SQL_QUOTED_SPAN_RE.sub("''", sql)
    collision = _CTE_COLLISION_RE.search(masked) or _ALIAS_COLLISION_RE.search(masked)
    if collision:
        name = collision.group(1)
        raise ValueError(
            f"run_sql: '{name}' is a MIMIC table name and can't be reused as a CTE or "
            f"alias name — on the BigQuery backend it is rewritten to the physical table, "
            f"which produces invalid SQL. Rename it (e.g. '{name}_cte')."
        )

    # Qualify table names only OUTSIDE quoted spans, so neither a literal value
    # (WHERE x = 'patients') nor a quoted alias (AS `patients`) is corrupted. (Comments
    # are not special-cased — run_sql rejects multi-statement input but doesn't strip
    # comments.)
    parts: list[str] = []
    last = 0
    for lit in SQL_QUOTED_SPAN_RE.finditer(sql):
        parts.append(_TABLE_RE.sub(repl, sql[last : lit.start()]))
        parts.append(lit.group(0))
        last = lit.end()
    parts.append(_TABLE_RE.sub(repl, sql[last:]))
    return "".join(parts)


def _bq_params(params):
    from google.cloud import bigquery

    def bq_type(v: Any) -> str:
        if isinstance(v, bool):
            return "BOOL"
        if isinstance(v, int):
            return "INT64"
        if isinstance(v, float):
            return "FLOAT64"
        return "STRING"  # timestamps are passed as strings and CAST in-SQL

    return [bigquery.ScalarQueryParameter(None, bq_type(v), v) for v in (params or [])]


# Per-request BigQuery credentials (multi-tenant hosted API). Each contributor queries
# MIMIC on PhysioNet under THEIR OWN credentialed Google identity (the DUA requires
# individual, non-shared access) and billed to THEIR OWN GCP project. We can't use one
# ADC identity for everyone, and we must NOT thread a credential argument through every
# tool — that would change the canonical tools.py surface the agent harness shares. So
# the API layer sets a context-local credential for the duration of a request (see
# bq_credentials) and we pick it up in _bq_client. When unset — local single-user dev,
# the agent harness, smoke_test — we fall back to Application Default Credentials.
_BQ_REQUEST_CREDS: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "bq_request_creds", default=None
)


@contextlib.contextmanager
def bq_credentials(access_token: str, billing_project: str | None = None):
    """Scope a contributor's BigQuery OAuth token + billing project to the current
    context (thread / async task). Every db.fetch/safe_query/schema call made inside the
    `with` block runs as that contributor. Used by the hosted API per request; callers
    that don't set it keep the ADC behavior unchanged."""
    token = _BQ_REQUEST_CREDS.set(
        {"access_token": access_token, "billing_project": billing_project}
    )
    try:
        yield
    finally:
        _BQ_REQUEST_CREDS.reset(token)


@lru_cache(maxsize=1)
def _bq_adc_client():
    """Single-identity client from Application Default Credentials — local dev / harness."""
    from google.cloud import bigquery

    return bigquery.Client(project=os.environ.get("MIMIC_BQ_BILLING_PROJECT") or None)


def _bq_client():
    """Request-scoped client built from the contributor's OAuth token when one is set
    (see bq_credentials); otherwise the cached ADC client. Not cached in the per-request
    case — credentials and billing project vary by contributor."""
    from google.cloud import bigquery

    creds = _BQ_REQUEST_CREDS.get()
    if creds and creds.get("access_token"):
        from google.oauth2.credentials import Credentials

        return bigquery.Client(
            credentials=Credentials(token=creds["access_token"]),
            project=(
                creds.get("billing_project") or os.environ.get("MIMIC_BQ_BILLING_PROJECT") or None
            ),
        )
    return _bq_adc_client()


def _bq_fetch(sql, params, max_rows):
    from google.cloud import bigquery

    job_config = bigquery.QueryJobConfig(query_parameters=_bq_params(params))
    iterator = (
        _bq_client()
        .query(_bq_qualify(sql), job_config=job_config)
        .result(max_results=(max_rows + 1) if max_rows else None)
    )
    cols = [f.name for f in iterator.schema]
    rows, truncated = [], False
    for i, row in enumerate(iterator):
        if max_rows is not None and i >= max_rows:
            truncated = True
            break
        rows.append({k: _coerce(v) for k, v in dict(row).items()})
    return cols, rows, truncated


# ----------------------------- public interface -------------------------- #


def fetch(sql: str, params=None, max_rows: int | None = None):
    """Run a read query. Returns (columns, rows[list[dict]], truncated). Raises on error.

    SQL uses logical table names and `?` positional params. Compare timestamp columns
    to params via CAST(? AS TIMESTAMP) so both backends agree (BigQuery won't compare
    STRING to TIMESTAMP implicitly).
    """
    if BACKEND == "bigquery":
        return _bq_fetch(sql, params, max_rows)
    return _duck_fetch(sql, params, max_rows)


def _missing_source_types() -> tuple:
    """Exception types that mean 'this logical table isn't present on the backend' —
    the ONLY thing safe_query swallows. Everything else (auth/token expiry, network,
    SQL errors) must propagate so it never masquerades as an empty result."""
    if BACKEND == "bigquery":
        try:
            from google.api_core import exceptions as gexc

            return (gexc.NotFound,)
        except Exception:
            return ()
    try:
        import duckdb

        return (duckdb.CatalogException,)
    except Exception:
        return ()


_MISSING_SOURCE = _missing_source_types()


def safe_query(sql: str, params=None) -> list[dict[str, Any]]:
    """Rows only. Swallows ONLY 'table/source absent' (so the surface can come online
    incrementally); auth/token-expiry, network, and SQL errors propagate — a dead token
    must not look like 'no data'. (Empty tuple => nothing swallowed => all errors raise.)"""
    try:
        return fetch(sql, params)[1]
    except _MISSING_SOURCE:
        return []


@lru_cache(maxsize=1)
def _schema_docs() -> dict[str, dict[str, str]]:
    """Curated column descriptions {logical_table: {column: text}} from the public MIMIC-IV
    docs (MIT-LCP/mimic-website), shipped alongside this module as schema_docs.json. Public
    reference text, not patient data. Optional: a missing/!valid file just means no
    descriptions (the column type still shows), so the Tables view degrades gracefully."""
    try:
        return json.loads(Path(__file__).with_name("schema_docs.json").read_text())
    except Exception:
        return {}


@lru_cache(maxsize=1)
def schema() -> dict[str, list[dict[str, Any]]]:
    """{logical_table: [{name, type, description}]} for every available table — the run_sql
    data dictionary that drives the Tables view. `type` is the backend column type; `description`
    is the public MIMIC-IV doc text (schema_docs.json), preferring the BigQuery column
    description when the backend has one. Cached; introspected via free metadata (no data scan).
    Tables absent on the backend are omitted.

    The cache is process-global and identical for every contributor, so after the first
    (credentialed) call warms it, later /schema requests return without re-validating the
    caller's token. That's intentional and safe: this returns only table/column NAMES, types,
    and public reference descriptions (mimic.mit.edu/docs/iv, MIT-LCP/mimic-code), not
    DUA-covered patient data. PHI never comes through here: patient rows go via
    fetch()/_bq_fetch(), which is never cached and always runs under the live credential."""
    docs = _schema_docs()
    out: dict[str, list[dict[str, Any]]] = {}
    for logical, (module, table) in TABLES.items():
        tdocs = docs.get(logical, {})
        try:
            if BACKEND == "bigquery":
                t = _bq_client().get_table(f"{BQ_PROJECT}.{_BQ_DATASETS[module]}.{table}")
                out[logical] = [
                    {
                        "name": f.name,
                        "type": f.field_type,
                        "description": f.description or tdocs.get(f.name),
                    }
                    for f in t.schema
                ]
            else:
                # DESCRIBE gives (column_name, column_type, ...) without scanning rows.
                # .cursor() for the same thread-safety reason as _duck_fetch.
                rows = _duck_conn().cursor().execute(f"DESCRIBE SELECT * FROM {logical}").fetchall()
                out[logical] = [
                    {"name": r[0], "type": r[1], "description": tdocs.get(r[0])} for r in rows
                ]
        except _MISSING_SOURCE:
            pass  # table genuinely absent on this backend; infra/auth errors propagate
    return out
