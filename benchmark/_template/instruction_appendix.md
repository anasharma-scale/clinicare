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
- This is a **fixed extract**, not a live record: each patient's data ends at an arbitrary cut-off, not at the end of their care. Before concluding something did not happen within a time window, check the window falls inside the record you can see — one running past the patient's last record of any kind is **unobserved, not negative**.

## Computation (your own tools, in addition to the `mimic` tools)

- **Computation** — use your own shell / Python (write and run a script in `/workspace`) for any analysis over tool outputs: deltas, rates, time-window comparisons, threshold checks. The `mimic` tools return raw rows; you compute the answer.
- **No web access.** Do not use web search or fetch tools. There is no public-web answer: every patient fact must come from the `mimic` tools above, and any definition, guideline, or code meaning you apply must come from the task instructions, the provided policy / guideline documents (where available), or your own knowledge — never from the web.

## Choosing among the four labels

Every task ends in exactly one of four labels: **Yes**, **No**, **Indeterminate – lack of data** (the data needed to decide is missing or unretrievable), or **Indeterminate – medical ambiguity** (the data is present and complete but genuinely does not resolve the question). Most tasks read like a yes/no question, but the two Indeterminate labels are **first-class determinations, not fallbacks** — returning one when it truly applies is the right call, and forcing a Yes/No onto a record that does not support one is a clinical error, not a tie-break. Apply these principles when deciding:

1. **A negative finding, an unavailable record, and a criterion you could not apply are three different things.**
   - You searched the streams where the action or finding would be documented, and it is not there — not performed, not documented, no positive result → **No**. A gap in a *corroborating* source does not undermine a determination whose primary source is present and negative.
   - You could not retrieve the primary record at all — the documentation that would establish the finding is unavailable, or you cannot confirm the event took place → **Indeterminate – lack of data**.
   - You have the finding, but the criterion needs a reference point the record does not give you: no pre-event **baseline** to measure a change against, no anchor **time** to compute an interval from, no denominator, or no prior comparator → **Indeterminate – lack of data**. Judge this against what the criterion's own definition requires, not against the ideal record: a reference point the definition does not call for, or one you can defensibly substitute from what you retrieved, does not make the criterion unevaluable.

   Recording a criterion **not met** asserts you applied it and it failed — a claim nothing downstream can distinguish from a true negative. So name the reference point you measured against, or the substitute you used; if you have neither, you have not evaluated it.

   **An unevaluable criterion forces an Indeterminate verdict only if it could change the answer.** If the verdict would be the same either way, answer the question and note the gap as a caveat; if not, record **Indeterminate – lack of data**.

2. **Confirm the premise before assessing against it.** Each task carries a clinical premise: that the patient has the condition, was on the drug, presented in the way described. If the record contradicts that premise or cannot establish it, the assessment has no purchase on this patient and there is no Yes or No to give — record **Indeterminate – lack of data** and say which part of the premise failed. This holds even when the record is unambiguous that the premise does not hold: the criteria simply do not apply here, which is a different situation from a record that leaves a genuine clinical question unresolved.

3. **Trust what was done over what was ordered.** Prefer administration / result / report records over order records — an order alone does not establish that a drug was given, a test resulted, or a procedure happened. **No order and no result** means the thing was not done → **No**; an **order but no administration, result or report** confirming it happened means you cannot tell whether it was done → **Indeterminate – lack of data**. The same applies when the timing or sequence of care cannot be reconstructed.

4. **Genuine ambiguity is an answer.** If the data is present and complete but still does not resolve the question — conflicting values, more than one defensible reading, a finding whose clinical significance is genuinely contested, a confounder that defeats the measure, or the treating team's own documented uncertainty (a differential left open, a cause recorded as "X and/or Y") — answer **Indeterminate – medical ambiguity** rather than picking the more likely side. The test: if two readings both remain defensible on what you retrieved, that is ambiguity to surface, not a close call for you to settle.

5. **Look for a documented reason before faulting an omission.** A deviation from the ideal that carries a documented, clinically appropriate justification (contraindication, patient refusal, out-of-window for a valid reason, etc.) is generally acceptable — don't fault it without first checking the record for such a reason.

6. **Prefer clinical values over billing codes.** When a diagnosis or status can be read from a clinical value (an echo EF, a lab, a note) and it conflicts with an ICD/billing code, rely on the clinical value.

These are general defaults; follow any more-specific definition or rule stated in the task itself where it applies.

## Final answer

Write your final deliverable — and only it, no meta-commentary about your process — to **`/workspace/report.md`** as markdown.

**Write the file early, then keep it current.** As soon as you have a provisional verdict — not at the very end — create `/workspace/report.md` with the verdict line and whatever you have so far, and rewrite it as your analysis firms up. Nothing outside this file is graded: if your session ends unexpectedly (a wall-clock limit, a tool or connection failure), whatever is on disk at that moment is your entire answer, and an absent or empty file is scored exactly like a wrong one.

**Confirm the file before you finish.** Your last action must be to check your own deliverable: read `/workspace/report.md` back and verify that (a) it exists at exactly that path, (b) it is not empty, and (c) its first line is the `## Answer:` verdict line. A shell redirect or heredoc that reports success can still leave a zero-byte file, and a report written to any other path is not collected. If the check fails, write it again and re-check.

**Never report the deliverable as done unless you have written it.** Do not state that the report is written, saved, or complete unless you created the file in this session and confirmed it as above.

**If the `mimic` tools stop working, still write the report.** Tool calls that time out, return `Connection closed` / `Not connected`, or disappear from your tool list are an environment failure, not a cue to keep retrying. After a couple of failed attempts, stop and write the report with whatever verdict the evidence you did retrieve supports — `## Answer: Indeterminate – lack of data` if you could not retrieve enough to decide. When you do this, you **must** also:

- Add a line, anywhere in the report, in exactly this form — it is read programmatically:

  ```
  ## Environment: degraded
  ```

- In `## Method / criteria applied`, name the tools that failed and the error text you saw.

Both are required because a verdict of `Indeterminate – lack of data` otherwise conflates two different things: the patient's record genuinely lacking the data, and the tools failing to retrieve data that is there. Only the first is a clinical finding. Omit the `## Environment: degraded` line when the tools worked — an unmarked report is taken to mean the verdict reflects the record itself.

Every task is a single classification into exactly one of four labels: **Yes**, **No**, **Indeterminate – lack of data** (the data needed to decide is missing or unretrievable), or **Indeterminate – medical ambiguity** (the data is present but genuinely does not resolve the question). Your report **must**:

- **Begin with a single verdict line, on its own line, in exactly this form:**

  ```
  ## Answer: Yes
  ```

  Replace `Yes` with exactly one of `Yes`, `No`, `Indeterminate – lack of data`, or `Indeterminate – medical ambiguity` (case doesn't matter). This line is read programmatically:
  - Put **only the one label** after `## Answer:` — nothing else on that line, and never more than one label (e.g. `Yes / No / Indeterminate – lack of data`). Hedging on this line, or omitting it, leaves the report with no verdict.
  - Keep all reasoning, evidence, and caveats in the sections **below** this line. If the verdict is Indeterminate, put that on this line and explain the uncertainty below — not a Yes or No on the line, qualified underneath.

- Follow with your confidence score for your verdict as a percentage between 0% and 100% (e.g. `## Confidence: 80%`).
- Include a **`## Method / criteria applied`** section. For each criterion the verdict depends on, state:
  1. the criterion, and where its definition comes from;
  2. the **reference point you evaluated it against** — the baseline value, index time, denominator, or comparator, and the record it came from;
  3. whether you were able to evaluate it at all.

  If a criterion could not be evaluated, say so and name what was missing — not "not met" or "absent", which both state that you applied it and it failed. Recording a criterion as unevaluable here is a note about **that criterion**; it does not by itself decide the verdict (see principle 1 for when it does). Write this section even when the verdict is a straightforward Yes or No.
- Back the verdict with **specific, cited evidence** from the `mimic` tools — the values, timestamps, and records you relied on, including the relevant negatives — plus any caveats, so the decision is reproducible.

If the task asks for additional output (e.g. a per-claim classification or table), include that as well, below the verdict line.
