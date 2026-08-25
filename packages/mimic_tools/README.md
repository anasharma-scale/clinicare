# mimic_tools — the MIMIC-IV tool surface

A read-only, patient-scoped tool surface over MIMIC-IV (v3.1 + Note v2.2 + ED v2.2). This is
what the benchmark agent calls, and it is the **only** way it reaches the data.

`tools.py` is the canonical surface. Every consumer imports the identical module — the agent's
MCP server, the HTTP sidecar, and the Streamlit console — so a task solved through the console is
solvable through exactly the tools and limits the agent has.

This is a *semantic* surface, not a FHIR layer: the tools answer clinical questions
(`get_lab_timeline`, `get_fluid_balance`) rather than exposing tables, with `run_sql` underneath
for anything they don't cover.

| File | Role |
| :---- | :---- |
| `tools.py` | The canonical tool surface (clinical logic + SQL). Backend-agnostic. |
| `db.py` | The only file that knows *where* data lives — backend, connections, the logical→physical table map. |
| `build_local.py` | One-time converter: PhysioNet `.csv.gz` → the Parquet tree `db.py` reads. |
| `mcp_server.py` | Agent-facing stdio MCP server. Proxy-only: forwards every call to the sidecar. |
| `api.py` / `serve.py` | The HTTP tool surface, and the sidecar entrypoint that runs it credentialed. |
| `streamlit_app.py` | A pull-based console over the same tools, for exploring the data by hand. |
| `smoke_test.py` | Exercises every tool on one patient; catches silent schema mismatches. |

For the credential-isolation design — why the agent can't query MIMIC directly — see
[`SIDECAR.md`](SIDECAR.md).

## Backends

Set by `MIMIC_BACKEND`. Either requires PhysioNet credentialing; neither ships data. Full setup
is in [`../../DATA_ACCESS.md`](../../DATA_ACCESS.md).

- **`duckdb`** (default) — DuckDB over a local Parquet copy at `MIMIC_DATA_ROOT`. No per-query
  cost, no auth to expire mid-run, no network. Build it once with `build_local.py`; the raw
  PhysioNet download is gzipped CSV, which DuckDB can neither prune nor push predicates into, so
  querying it directly is orders of magnitude too slow and `db.py` refuses it outright.
- **`bigquery`** — MIMIC-IV on PhysioNet's BigQuery. Convenient, but `physionet-data` is
  unclustered, so patient-scoped queries scan whole columns. Read the cost section of
  DATA_ACCESS.md before running a sweep on it.

Logical table names are identical across backends, so the same tool SQL — and the same `run_sql`
a user writes — runs unchanged on either.

## Tools

| Group | Tools |
| :---- | :---- |
| Patient & encounters | `get_patient_demographics`, `list_admissions`, `get_admission_details`, `list_ed_visits`, `get_ed_visit_details`, `list_icu_stays`, `get_icu_stay_details` |
| Notes | `list_notes`, `get_note`, `search_notes` |
| Timelines | `get_lab_timeline`, `get_vitals_timeline` |
| Medications | `get_medication_reconciliation`, `get_medication_administered`, `get_medication_prescribed` |
| Dx / procedures / imaging / micro | `get_diagnosis_history`, `get_procedures`, `get_imaging_studies`, `get_microbiology_results` |
| ICU I/O | `get_fluid_balance` (incl. canonical `urine_output_ml`) |
| Orders | `list_orders` |
| Availability | `get_data_availability` — per-stream row counts and spans |
| SQL | `run_sql` (one read-only `SELECT`/`WITH`, capped at `max_rows` with an explicit `truncated` flag) |

Each returns plain JSON-friendly Python. Lab and vital names resolve to canonical
[MIT-LCP/mimic-code](https://github.com/MIT-LCP/mimic-code) itemids (`creatinine` → serum itemid
50912), so values are precise on both backends.

`get_data_availability` exists to answer a question no other tool can: *is this stream empty for
this patient, or did my filter miss?* A stream with zero rows is a finding, not a retrieval
failure — which is exactly the distinction the benchmark's two indeterminate classes turn on.

**Provided by the harness, not this module:** `execute_python` (a compute-only scratchpad over
tool outputs) and the three policy tools. `lookup_drug_class` was dropped on purpose — classifying
drugs is part of what the agent is being tested on.

## Setup

```bash
uv sync                                     # from the repo root
export MIMIC_DATA_ROOT=/path/to/mimic-parquet
uv run python smoke_test.py 10001217        # exercises every tool on one patient
```

Every `example` in the tool registry, and the smoke test's default, use **subject `10001217`** —
one of the 100 patients in the [MIMIC-IV demo](https://physionet.org/content/mimic-iv-demo/),
which is open access under ODbL and needs no credentialing. So the examples name no
credentialed-only record. (MIMIC-IV `subject_id`s are de-identified surrogate integers, not PHI,
but keeping the published examples inside the open subset means a reader can check them without
a PhysioNet account. The `note_id` examples are the exception: MIMIC-IV-Note has no demo
release, so those resolve only against the full dataset.)

Because tools return `[]` on a missing source, a tool returning zero rows for a patient who
should have data is the signal to investigate — start with
`python -m mimic_tools.build_local --dst $MIMIC_DATA_ROOT --verify`.

The Streamlit console (`uv sync --extra ui`) is a **pull-based** view: it deliberately does not
auto-load a patient's chart. Data appears only when you invoke a tool, so a logged session
reflects which tools were actually used rather than what a UI prefetched.

## Configuration

| Var | Backend | Purpose |
| :---- | :---- | :---- |
| `MIMIC_BACKEND` | both | `duckdb` (default) or `bigquery` |
| `MIMIC_DATA_ROOT` | duckdb | the Parquet root (`<root>/{hosp,icu,ed,note}/<table>.parquet`) |
| `MIMIC_ALLOW_PARTIAL` | duckdb | `1` to start with tables missing — see the warning below |
| `MIMIC_DB_PATH` | duckdb | share an on-disk DuckDB instead of the default in-memory one |
| `MIMIC_BQ_BILLING_PROJECT` | bigquery | your GCP project; `physionet-data` can't be billed |
| `MIMIC_BQ_PROJECT` | bigquery | data project (default `physionet-data`; point at a clustered copy) |
| `MIMIC_BQ_DATASET_{HOSP,ICU,ED,NOTE}` | bigquery | dataset name overrides |
| `MIMIC_BQ_PER_REQUEST_AUTH` | bigquery | multi-tenant only; forwarded tokens expire after ~1h |

`MIMIC_ALLOW_PARTIAL` defaults off for a reason: a missing table makes its tools return empty,
and an agent reading empty results reports "Indeterminate – lack of data" — a plausible wrong
answer rather than an error, and one that looks like a model failure rather than a setup one.

## Scale notes

- Every query is patient-scoped, or an explicit `run_sql`. Nothing prefetches a whole chart.
- `labevents` is ~158M rows and `chartevents` ~433M; patient-scoped queries touch a tiny
  fraction of either, because Parquet lets DuckDB prune row groups and read only the columns
  asked for. Neither is possible against the gzipped CSV the download ships as — that is what
  the conversion buys. (The converter also sorts by `subject_id`, but PhysioNet already ships
  the CSVs in that order, so on v3.1 the sort is a guarantee rather than an improvement.)
- No note-module cache is needed: reads are local files. The note tables have few, physically
  large row groups, so pruning does less for them than for `chartevents` — locally that is a fast
  few-hundred-MB read.
- `run_sql` caps at `max_rows` (default 5000) and flags truncation — it never silently drops rows.
- Note text is fetched only when `get_note` is called explicitly.
