# Policy corpus

67 clinical guideline and policy documents (AHA/ACC, IDSA, NICE, KDIGO, SCCM, CDC/CMS, and
others) in Markdown. The policy-grounding axis of the benchmark searches, reads, and cites these
through three read-only tools (`list_policy_docs` / `search_policy` / `read_policy`), gated by
`MIMIC_POLICY_TOOLS` for the policy-on/off ablation.

**This directory is assembled, not committed.** There is no single archive to hand out: the
documents sit under a mix of terms, and most of them we have no right to redistribute. What is
committed is everything needed to rebuild the corpus from its sources —
`benchmark/corpus_manifest.csv` and the 16 documents that are US government works. Everything you
fetch to complete the corpus is governed by its publisher's terms, and complying with them is your
responsibility.

## Building it

```bash
uv sync --extra construction     # pymupdf + trafilatura; the base install cannot convert
uv run python construction/scripts/acquire_corpus.py --list-downloads   # what needs a browser
uv run python construction/scripts/acquire_corpus.py                    # build everything else
```

A targeted run is useful for checking the pipeline without transcribing every page:

```bash
uv run python construction/scripts/acquire_corpus.py --only davenport curb65 aabb
uv run python construction/scripts/acquire_corpus.py --verify-only   # fetch + hash, no conversion
```

Output goes to `$CLINICARE_CORPUS_DIR`, else `corpus-build/`. `build_tasks.py` reads that path
and stages the corpus into the sidecar, so nothing needs to live in this directory.

Each manifest row carries an `action` saying how that document is obtained:

| action | n | what happens |
|---|---|---|
| `ship-md` | 16 | copied from `benchmark/corpus_public/` — US government work, no restrictions |
| `fetch-pdf` | 29 | downloaded, hash-checked, transcribed by a vision model |
| `fetch-html` | 4 | fetched and extracted with trafilatura |
| `download-pdf` | 17 | **you** download in a browser — the publisher blocks scripted access |
| `download-epub` | 1 | same, but choose EPUB in the viewer's download menu |

The 18 manual documents are not an oversight. Their publishers sit behind Cloudflare or PMC
interstitials that return a challenge page to any HTTP client, including for open-access and
public-domain files. A browser gets them; a script does not. Save them anywhere under
`corpus-inbox/` — they are matched by content hash, so filenames do not matter — and re-run.
Finished documents are skipped, so the manual half can be done a few files at a time.

## Verification

There is **no corpus-wide pin**, because there cannot be one: 51 of the 67 documents are
converted on your machine, and the PDF path transcribes pages with a vision model, which is not
deterministic. Two people building this corpus will not get byte-identical Markdown, and neither
will match whatever produced any published number.

Verification is per-document instead, and `acquire_corpus.py` runs both layers:

- **`source_sha256`** proves you fetched the same source artifact we did. This is the strong
  check and it covers 38 documents; another 16 are committed to the repo, where git serves
  the same purpose. Which applies to a given document is recorded in `verify_method`.
- **`eval/gold/policy_facts.json`** asserts that the load-bearing content of each governing
  document survived conversion — the AABB transfusion thresholds, the KDIGO creatinine criteria,
  the CURB-65 bands, and so on. `validate_policy_facts.py` runs at the end of every build and
  fails it if any assertion is missing.

The second layer is what catches the failure the first cannot. A conversion defect that drops a
threshold makes the affected rubric unsatisfiable for every agent, and the benchmark would
otherwise report that as a model weakness rather than a corpus defect.

The remaining 13 cannot be hash-checked. Most carry a per-download watermark
(`Downloaded from … on <date>`), so their bytes differ for every person who downloads them and
`source_sha256` records our copy rather than a value to compare against; the rest are
web-sourced, with no stable artifact to hash. 10 of them are covered by content assertions
(`verify_method = content-assertions`). The other 3 are non-governing distractor documents that no
scenario cites, so a conversion defect there cannot affect any rubric — marked `not-required`
rather than left looking like a gap.

A hash mismatch on a `fetch-pdf` document is reported as a warning rather than an error: some
publisher URLs serve a revised file at the same address, and the content check is what decides
whether the difference actually matters.

## Regenerating

`construction/scripts/ingest_corpus.py` is the underlying converter, usable directly on a PDF,
EPUB, or URL. Its EPUB and web paths are deterministic; its PDF path is not.
