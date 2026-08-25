---

## Your data environment (MIMIC-IV)

You have access to **MIMIC-IV** (a de-identified critical-care dataset: hospital, ICU, ED, and clinical notes) through a set of read-only tools served over an **MCP server named `mimic`**. These tools are your only source of patient data — there is no local copy on disk and no public-web answer; everything must come from the tools.

Call the MCP tools directly (they appear in your tool list, prefixed by the `mimic` server). Highlights:

- **Patient / encounters** — `get_patient_demographics`, `list_admissions`, `get_admission_details`, `list_ed_visits`, `get_ed_visit_details`, `list_icu_stays`, `get_icu_stay_details`.
- **Timelines** — `get_lab_timeline`, `get_vitals_timeline`.
- **Meds** — `get_medication_administered`, `get_medication_prescribed`, `get_medication_reconciliation`.
- **Dx / procedures / imaging / micro** — `get_diagnosis_history`, `get_procedures`, `get_imaging_studies`, `get_microbiology_results`.
- **ICU I/O** — `get_fluid_balance`. **Notes** — `list_notes`, `get_note`, `search_notes`.
- **`run_sql`** — a single read-only `SELECT` / `WITH` over the MIMIC tables, for anything the per-patient tools don't cover (a field, table, or join they don't expose). Logical table names: `patients`, `admissions`, `icustays`, `chartevents`, `labevents`, `procedureevents`, `inputevents`, `outputevents`, `diagnoses_icd`, `d_icd_diagnoses`, `procedures_icd`, `radiology_notes`, `radiology_detail`, `discharge_notes`, `edstays`, `ed_triage`, and more. Compare timestamps via `CAST(... AS TIMESTAMP)`. Results are capped (`max_rows`) and flag `truncated` — they are never silently dropped.

Guidance:
- Each task concerns a **single patient** — scope every tool call and `run_sql` query to the subject / admission / stay named in the task.
- `run_sql` returns at most `max_rows` rows — raise it deliberately and watch `truncated` rather than assuming you saw everything.
- Do your own arithmetic in a scratch script; the tools return raw data, not computed results (deltas, rates, thresholds).

## Computation (your own tools, in addition to the `mimic` tools)

- **Computation** — use your own shell / Python (write and run a script in `/workspace`) for any analysis over tool outputs: deltas, rates, time-window comparisons, threshold checks. The `mimic` tools return raw rows; you compute the answer.
- **No web access.** Do not use web search or fetch tools. There is no public-web answer: every patient fact must come from the `mimic` tools above, and any definition, guideline, or code meaning you apply must come from the task instructions, the provided policy / guideline documents (where available), or your own knowledge — never from the web.

## Final answer

Write your final deliverable — and only it, no meta-commentary about your process — to **`/workspace/report.md`** as markdown.

Every task is a single classification into exactly one of four labels: **Yes**, **No**, **Indeterminate – lack of data** (the data needed to decide is missing or unretrievable), or **Indeterminate – medical ambiguity** (the data is present but genuinely does not resolve the question).

**No vs. Indeterminate – lack of data.** Answer **No** when the data you retrieved affirmatively shows the thing did not occur or the criterion was not met — including when a required action or finding is simply absent from streams you successfully searched (a negative on searched data, or an action that was not performed or not documented, is a No). Reserve **Indeterminate – lack of data** for when the *primary* data needed to decide is itself unavailable or unretrievable — you could not obtain the records that would establish the finding, or even confirm the event occurred. A missing *corroborating* stream does not force lack-of-data if the primary data is present and negative.

Your report **must**:

- **Begin with a single verdict line, on its own line, in exactly this form:**

  ```
  ## Answer: Yes
  ```

  Replace `Yes` with exactly one of `Yes`, `No`, `Indeterminate – lack of data`, or `Indeterminate – medical ambiguity` (case doesn't matter). This line is graded automatically:
  - Put **only the one label** after `## Answer:` — nothing else on that line. Listing more than one label (e.g. `Yes / No / Indeterminate – lack of data`), hedging, or omitting the line is scored as an **incorrect** answer.
  - Keep all reasoning, evidence, and caveats in the sections **below** this line.

- Back the verdict with **specific, cited evidence** from the `mimic` tools — the values, timestamps, and records you relied on, including the relevant negatives — and state the **definitions and criteria you applied** plus any caveats, so the decision is reproducible.
- Format your evidence as a list of claims, each claim followed by its source citation.

If the task asks for additional output (e.g. a per-claim classification or table), include that as well, below the verdict line.
