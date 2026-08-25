# Third-party content

The [MIT License](LICENSE) covers everything in this repository that this project authored: the
tool surface, the evaluation and construction pipelines, the scenario specifications
(`benchmark/_scenarios/`, including `scenario.toml`, `rubrics.toml` and `policy_rubrics.toml`), the
task templates, the judge prompts, and the documentation.

It does **not** and cannot cover the third-party material described below. Nothing here restricts
your use of the MIT-licensed code; this file exists so the provenance of the rest is unambiguous.

## Policy corpus

The policy-grounding axis is backed by 67 clinical, regulatory and operational guideline documents
authored by third parties. `benchmark/corpus_manifest.csv` is the authoritative per-document record:
its `license` column classifies every one of them, and `source_url` names where it came from.

| Class | Count | Shipped here? |
| :-- | --: | :-- |
| `PD-USGOV` — United States Government works | 16 | Yes, as Markdown under `benchmark/corpus_public/` |
| `RESTRICTED` / `RESTRICTED-NO-REDIST` — publisher terms permit retrieval, not redistribution | 40 | No |
| `CC-BY-NC-ND-4.0`, `CC-BY-NC-ND`, `CC-BY-NC-4.0` — NonCommercial and/or NoDerivatives | 6 | No |
| `PMC-AUTHOR-MS` — PubMed Central author manuscripts | 3 | No |
| `CC-BY-4.0` | 1 | No |
| `CC-BY-NC-SA-3.0-IGO` — WHO intergovernmental licence | 1 | No |

Every document carries exactly one classification, and the classes above are disjoint and sum to
67. The 51 documents not shipped are assembled on your own machine by
`construction/scripts/acquire_corpus.py` from the sources the manifest names.

Redistribution is blocked for different reasons across these classes, which is why the recipe
ships instead of the corpus. Forty documents are under publisher terms that permit retrieval but
not redistribution, and three are PubMed Central author manuscripts, which are free to read but
carry no redistribution grant. Seven are Creative Commons but NonCommercial. Five of those seven
are also NoDerivatives and could not be redistributed in this form even with a redistribution
right, because converting a PDF to Markdown produces a derivative work; one is ShareAlike, which
would require any derivative to carry the same licence and so could not sit in an MIT-licensed
repository.

The single `CC-BY-4.0` document is not blocked by its licence at all. It is fetched rather than
shipped so that every document committed here is a United States Government work, leaving no
attribution or licence obligation attached to anything in this repository.

Each of the 51 documents retrieved during a corpus build remains governed by the terms of its own
publisher, which the `license` column names per document. Complying with those terms is the
responsibility of whoever builds the corpus. See
[DATA_ACCESS.md](DATA_ACCESS.md#5-build-the-policy-corpus).

### United States Government works

Works of the United States Government are not subject to copyright protection in the United States
(17 U.S.C. § 105). The 16 documents below are therefore in the public domain. They are redistributed
here as a convenience, converted to Markdown; **they are not original works of this project and are
not covered by the MIT grant in LICENSE**, which cannot be applied to them. No endorsement by any
United States Government agency is claimed or implied.

| File | Title |
| :-- | :-- |
| `BPCIAdvanced_AltFS_MY4_Sepsis_08112020_508.md` | Severe Sepsis and Septic Shock: Management Bundle Measure — BPCI Advanced Quality Measures Fact Sheet |
| `antibiotic-use-in-the-united-states.md` | Antibiotic Use in the United States |
| `care-transitions.md` | Care Transitions (AHRQ PSNet Perspective) |
| `caring-for-patients-with-sepsis.md` | Caring for Patients with Sepsis |
| `cdc-core-elements-hospital-antibiotic-stewardship.md` | The Core Elements of Hospital Antibiotic Stewardship Programs: 2019 |
| `cdc-hospital-sepsis-core-elements.md` | Hospital Sepsis Program Core Elements: 2023 |
| `cdc-naloxone-distribution-eval.md` | Evaluation Profile for Naloxone Distribution Programs (OD2A) |
| `cdc-nhsn-ssi-definitions.md` | Surgical Site Infection Event (SSI) — NHSN Patient Safety Component Manual, Chapter 9 |
| `cdc-protect-patients-from-sepsis-factsheet.md` | Get Ahead of Sepsis: Protect Your Patients From Sepsis |
| `cms-appropriate-use-criteria-program.md` | Appropriate Use Criteria Program |
| `cms-cctp-fact-sheet.md` | Community-Based Care Transitions Program Fact Sheet |
| `cms-hrrp-planned-readmission-algorithm.md` | CMS Planned Readmission Algorithm, Version 2.1 |
| `cms-hwr-readmission-methodology.md` | Hospital-Wide (All-Condition) 30-Day Risk-Standardized Readmission Measure: Methodology Report |
| `cms-reducing-disparities-in-readmissions-2024.md` | Guide to Reducing Disparities in Readmissions |
| `hospital-readmissions-reduction-program.md` | Hospital Readmissions Reduction Program (HRRP) |
| `samhsa-tip63-moud.md` | TIP 63: Medications for Opioid Use Disorder |


## Patient data

No patient data appears in this repository. MIMIC-IV, MIMIC-IV-Note and MIMIC-IV-ED are distributed
by PhysioNet under the PhysioNet Credentialed Health Data Use Agreement, which prohibits
redistribution; the cohort bundle carrying case identifiers and reference labels is a MIMIC
derivative and is distributed separately to credentialed users. See
[DATA_ACCESS.md](DATA_ACCESS.md).

## Dependencies

Third-party Python packages are declared in `pyproject.toml` and pinned in `uv.lock`, each under its
own license. They are neither vendored nor redistributed here.
