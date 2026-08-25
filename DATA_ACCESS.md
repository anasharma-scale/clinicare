# Data access

CliniCARE runs against real patient records. **This repository ships no patient data**, and
nothing here substitutes for PhysioNet credentialing.

Four things have to be in place. Only the first two are credentialed:

| | What | Where it comes from |
| :-- | :-- | :-- |
| 1 | **MIMIC-IV** | PhysioNet, credentialed |
| 2 | **Cohort bundle** — `full750.csv`, `dev148.csv` | MedHELM, credentialed |
| 3 | **Policy corpus** | Built from this repo — no credential, but ~18 documents need a browser |
| 4 | A **Docker** daemon | Required to run trials — see [README](README.md#data-access-is-credential-isolated) |

---

## 1. Get credentialed on PhysioNet

1. Create a [PhysioNet](https://physionet.org/) account.
2. Complete the **CITI "Data or Specimens Only Research"** course and submit the completion
   report to PhysioNet. This is the slow step — allow days, not minutes.
3. Sign the data use agreement on the [MIMIC-IV project
   page](https://physionet.org/content/mimiciv/).

The DUA governs what you may do with the data. In particular you may not redistribute it, so
please don't commit any of it back into a fork of this repo — `.gitignore` is set up to make
that hard, but it isn't a guarantee.

## 2. Download MIMIC-IV

MIMIC-IV ships as **three separate PhysioNet projects**. CliniCARE needs all three; forgetting
Note or ED is the single most common setup mistake, and the converter will tell you so by name.

| Project | Modules | Approx. compressed |
| :-- | :-- | :-- |
| [MIMIC-IV v3.1](https://physionet.org/content/mimiciv/) | `hosp`, `icu` | ~8 GB |
| [MIMIC-IV-Note v2.2](https://physionet.org/content/mimic-iv-note/) | `note` | ~1.5 GB |
| [MIMIC-IV-ED v2.2](https://physionet.org/content/mimic-iv-ed/) | `ed` | ~0.5 GB |

```bash
mkdir -p ~/physionet && cd ~/physionet
wget -r -N -c -np --user <your-physionet-username> --ask-password \
  https://physionet.org/files/mimiciv/3.1/ \
  https://physionet.org/files/mimic-iv-note/2.2/ \
  https://physionet.org/files/mimic-iv-ed/2.2/
```

Unpack them wherever you like — side by side, nested, or in three unrelated places. The
converter searches recursively for `<module>/<table>.csv.gz`, so the layout doesn't matter.

**Version matters.** The published labels are pinned to MIMIC-IV **v3.1** + Note **v2.2** + ED
**v2.2**. On other versions, subject ids and cohort membership differ and the benchmark will
not reproduce.

## 3. Convert to Parquet

```bash
uv run python -m mimic_tools.build_local --src ~/physionet --dst ~/mimic-parquet
```

Run this once. Budget a few hours and roughly 2–3× the download size in free disk (output plus
sort spill); `chartevents` alone is ~433M rows and dominates both.

**The conversion is not optional.** The raw download is gzipped CSV, which DuckDB cannot push
predicates into or prune columns from, and gzip isn't splittable — so every tool call would
re-read and re-decompress entire tables, single-threaded. Parquet turns each call into a
row-group-pruned, column-pruned local read. Pointing `MIMIC_DATA_ROOT` at the raw download is
refused rather than allowed to be silently slow.

Useful flags:

```bash
--dry-run                    # show what would be converted
--tables labevents patients  # a subset
--overwrite                  # redo tables already present
--memory-limit 32GB          # raise on a big machine; default 8GB
--temp-dir /fast/disk/tmp    # sort spill; wants tens of GB
--verify                     # re-check an existing tree against its manifest
```

It's resumable: interrupted tables are written via a temp file and renamed, so a re-run picks
up where it stopped. Each table's row count is checked against the source, and the result is
recorded in `_manifest.json` so `--verify` can confirm the tree later without the source.

Then point the tools at it:

```bash
MIMIC_DATA_ROOT=~/mimic-parquet
```

Check it works:

```bash
uv run python -m mimic_tools.build_local --dst ~/mimic-parquet --verify
uv run python packages/mimic_tools/smoke_test.py 10001217
```

The smoke test exercises every tool against one patient. Because tools return `[]` on a missing
source, a tool returning zero rows for a patient who should have data is the signal to
investigate.

## 4. Get the cohort bundle

The cohort comes from MedHELM, which verifies PhysioNet credentialing. Show the same credential
you used for MIMIC itself.

```bash
CLINICARE_COHORT_DIR=/path/to/clinicare-cohort
```

The policy corpus is NOT part of that request. It is third-party guideline text under its
publishers' terms rather than a MIMIC derivative, so it cannot be redistributed at all — it is
assembled on your machine from sources this repo names. See section 5.

### The cohort bundle

`full750.csv` is the label source of truth (`task_id,scenario_id,params_json,expected_label`).
`dev148.csv` is the frozen membership of the 148-case development subset the paper's
reliability tables are computed on — membership only; labels are read live from `full750.csv`.
It deliberately oversamples the two indeterminate classes (53 of 148, against 150 of 750 in the
full set), so its class balance is not the full set's — don't quote one for the other.

Note that `construction/` can regenerate *silver* labels from the cohort SQL, but **not** these
— the published labels went through consensus adjudication. The bundle is the only source of
the exact labels behind the paper.

---

## 5. Build the policy corpus

67 clinical guideline documents back the policy-grounding axis. There is no archive to download:
most are under publisher terms that let you fetch a copy but not redistribute one, so the repo
ships the acquisition recipe instead — `benchmark/corpus_manifest.csv`, plus the 16 documents
that are US government works and carry no restriction. Every other document is governed by its
publisher's terms, and complying with them is your responsibility.

```bash
uv sync --extra construction
uv run python construction/scripts/acquire_corpus.py --list-downloads   # what needs a browser
uv run python construction/scripts/acquire_corpus.py                    # build everything else
export CLINICARE_CORPUS_DIR=/path/to/corpus-build
```

Expect to fetch about 18 documents by hand. Their publishers sit behind bot challenges that
answer any HTTP client with a block page — including for open-access and public-domain files — so
a browser gets them and a script does not. Save them anywhere under `corpus-inbox/`; they are
identified by content hash and embedded DOI, so filenames do not matter. Re-run the script as
often as you like, and it will skip what is already built.

Unlike the cohort, the corpus is **not content-pinned**, because it cannot be: 51 of the 67
documents are converted on your machine and the PDF path transcribes pages with a vision model,
which is not deterministic. Verification is per-document instead — a source checksum where the
artifact is stable, and content assertions that fail the build if a conversion drops a
load-bearing fact such as a transfusion threshold or a diagnostic window. Full detail in
[`benchmark/corpus/README.md`](benchmark/corpus/README.md).

Practically, this means your corpus will not be byte-identical to the one behind the published
policy-grounding numbers, and neither will anyone else's. Treat those numbers as reproducible in
distribution, not to the digit.

---

## Alternative: BigQuery instead of a local copy

If you'd rather not hold a local copy, MIMIC-IV is also on PhysioNet's BigQuery. On the
project page request **"Access using Google BigQuery"** and link your Google account, then:

```bash
gcloud auth application-default login
export MIMIC_BACKEND=bigquery
export MIMIC_BQ_BILLING_PROJECT=<your-own-gcp-project>   # physionet-data can't be billed
```

Application Default Credentials hold a refresh token and renew themselves, so a long sweep
won't die mid-run. (Don't set `MIMIC_BQ_PER_REQUEST_AUTH` unless you're running a multi-tenant
sidecar — a forwarded access token has no refresh material and expires after about an hour.)

### Read this before running a sweep on BigQuery

BigQuery bills by **bytes scanned**, and the `physionet-data` tables are **not clustered**. So
every patient-scoped query scans whole columns of the underlying table rather than one
patient's rows. On `chartevents` (~433M rows) a single `get_vitals_timeline` call can scan tens
of GB. Across ~100 tool calls per trial and 750 trials, a full sweep plausibly costs **four
figures**. Measure before you commit:

```bash
bq query --dry_run --use_legacy_sql=false \
  'SELECT charttime, valuenum FROM `physionet-data.mimiciv_3_1_icu.chartevents`
   WHERE subject_id = 10001217'
```

**Fix it with a one-time clustered copy** into your own project. One full scan per table
(~$1 total) plus a few dollars a month of storage, after which patient-scoped queries scan
almost nothing:

```sql
CREATE SCHEMA IF NOT EXISTS `myproj.mimiciv_3_1_icu`;
CREATE OR REPLACE TABLE `myproj.mimiciv_3_1_icu.chartevents`
CLUSTER BY subject_id AS
SELECT * FROM `physionet-data.mimiciv_3_1_icu.chartevents`;
-- repeat per table, then:
```

```bash
export MIMIC_BQ_PROJECT=myproj    # dataset names are unchanged
```

No code change is needed — the project and dataset names are configuration
(`MIMIC_BQ_PROJECT`, `MIMIC_BQ_DATASET_{HOSP,ICU,ED,NOTE}`). Keep the copy in a private project;
it's MIMIC data and the DUA still applies.

Also worth knowing: BigQuery caps concurrent interactive queries per project, which a
parallel 750-task sweep can hit. Queries retry, but it adds wall-clock time.

---

## Troubleshooting

**`MIMIC_DATA_ROOT is not set`** — the DuckDB backend needs a local Parquet root. Step 3.

**`… holds the raw PhysioNet .csv.gz download, not Parquet`** — you pointed at the download
rather than the converter's output. Step 3.

**`N of 41 MIMIC tables are missing`** — the conversion is incomplete, usually because one of
the three PhysioNet projects wasn't downloaded. Re-run the converter; it names what's missing.
`MIMIC_ALLOW_PARTIAL=1` proceeds anyway, but tools over the missing tables return empty, which
an agent reports as "Indeterminate – lack of data" — a plausible wrong answer rather than an
error. Don't use it for a real run.

**Trials fail with no tool calls** — the sidecar didn't start. It refuses to come up without
`MIMIC_API_SECRET`, and its `${MIMIC_DATA_ROOT}` bind mount fails loudly if that isn't set on
the host. Check `docker compose logs mimic-tools`.

**Tools return empty for a patient who should have data** — run `--verify`. A silently partial
conversion is the usual cause.
