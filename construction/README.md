# construction/ — how the benchmark was built

**You do not need any of this to run CliniCARE.** It is here so the benchmark's construction is
inspectable rather than asserted: how each cohort was defined, how the gold labels were produced,
and how the policy corpus was assembled. To run the benchmark, see [`../benchmark/`](../benchmark/).

```
construction/
├── cohorts/scenario-NN-<slug>.sql   the cohort-defining SQL, one per scenario
├── configs/oracle_{opus,gpt,gemini}.yaml   the three label-generation oracle runs
└── scripts/
    ├── select_cohort.py             1. cohort SQL -> silver_patients.csv (sampling pool)
    ├── analyze_labels.py            4. oracle verdicts -> per-task consensus
    ├── finalize_cohort.py           5. consensus -> full750.csv
    ├── build_cohort_bundle.py       assemble the gated bundle from per-scenario CSVs
    ├── draft_policy_rubrics.py      seed a scenario's policy_rubrics.toml
    ├── acquire_corpus.py            assemble the policy corpus from corpus_manifest.csv
    └── ingest_corpus.py             PDFs / EPUBs / URLs -> Markdown (the converter)
```

## The label pipeline

```
cohorts/<scenario>.sql
  └─ select_cohort.py            → silver_patients.csv    (balanced sampling pool)
       └─ build_tasks.py --include-answer                 (rubric baked into the prompt)
            └─ harbor run -c configs/oracle_{opus,gpt,gemini}.yaml
                 └─ analyze_labels.py   → label_agreement.csv   (3-model consensus)
                      └─ finalize_cohort.py → full750.csv
```

**The cohort SQL is a sampling stratifier, never ground truth.** This was a recurring confusion
worth stating plainly: the SQL picks a balanced pool of candidate patients and assigns a *silver*
label to stratify that sample. The published labels are the three-model consensus, with
three-way splits adjudicated by hand — which the SQL neither produces nor can reproduce.

Which means: **running this pipeline end to end does not regenerate the published labels.** It
regenerates the *process*. `full750.csv` in the cohort bundle is the only source of the labels
behind the paper. `finalize_cohort.py` is dry-run by default for that reason.

## The oracle configs

`configs/oracle_{opus,gpt,gemini}.yaml` are harbor `JobConfig` files — agent, model, dataset and
concurrency in one reviewable file instead of a hand-copied `harbor run` command. Each header
carries its docker launch line. **API keys never go in them**; pass those at launch with `--ae`,
along with `--extra-docker-compose` for the sidecar — a CLI flag rather than a config key on
purpose, for the reason `oracle_opus.yaml` gives.

All three are closed-book: the tasks must be answerable only from the `mimic` tools and the policy
corpus, so web search is disabled on each — but by a different mechanism per vendor, which is easy
to get wrong when adding a fourth. `oracle_gpt.yaml` sets `kwargs.web_search: disabled`,
`oracle_opus.yaml` sets `kwargs.disallowed_tools`, and `oracle_gemini.yaml` relies on the
`GeminiNoWeb` agent injecting gemini's `excludeTools` denylist.

## Reproducibility caveats

Two steps here are not reproducible from this repository alone, both deliberately:

- **`build_gold.py` / `build_required_evidence.py`** distil the clinician annotation delivery.
  That delivery is a MIMIC-derived working artifact and is not publicly distributed, so both
  scripts require `--annotation` with your own copy. Their outputs (`gold_sources.json`,
  `required_evidence.json`) are committed under `benchmark/eval/gold/`, so nothing downstream
  needs them re-run.
- **`acquire_corpus.py`** is the entry point for the policy corpus: it reads
  `benchmark/corpus_manifest.csv`, copies the committed public-domain documents, fetches what can
  be fetched, tells you which ~19 to download in a browser, and ends on the content check.
  **`ingest_corpus.py`** is the converter underneath it, usable directly on a PDF, EPUB or URL.
  Its PDF path transcribes pages with a vision model and is not deterministic, so no two builds
  of the corpus are byte-identical — verification is per-document rather than a corpus-wide pin
  (see [`../benchmark/corpus/README.md`](../benchmark/corpus/README.md)).

## Rebuilding the cohort bundle

```bash
python scripts/build_cohort_bundle.py \
    --scenarios <dir of scenario-NN-*/patients.csv> --pin <dev148_pin.csv> --dst <bundle dir>
```

Every task id is **recomputed from `scenario.toml`'s declared parameter order and compared
against the input**; a single mismatch aborts the run. That check is not paranoia: two scenarios
declare the same three parameters in different orders, so a merge that canonicalised parameter
order would renumber their tasks and quietly invalidate every published result keyed by task id.
The script also refuses a bundle whose dev pin references ids absent from the cohort.
