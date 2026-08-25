-- scenario-22 eol-goal-concordance — 3-way silver STRATIFIER (YES / NO / ESCALATE; the two
-- indeterminate classes merge to ESCALATE). Returns (subject_id, hadm_id). This label is only a
-- cheap structured splitter — the real Yes/No/Escalate is decided downstream; here we just carve
-- the in-hospital-death pool into three balanced strata from structured signals only
-- (no notes, no LLM).
--
-- NOTE: this scenario's cohort is overwhelmingly YES. Concordant care appears to be the genuine
-- base rate, so widening the sample does not produce NO rows — reaching them would need a
-- different signal (e.g. an explicit comfort-goal note followed by escalation).
--
-- Eligible = an admission where the patient died in hospital (hospital_expire_flag = 1 with a
-- recorded deathtime, so the final-72-h window is anchorable). has_code_status = any code-status
-- charting exists on the admission (needed to locate the documented goals). intensive = any
-- intensive intervention (pressors, dialysis/CRRT, intubation/lines, or mechanical-ventilation
-- charting) in the final 72 h before death — the structured signal most correlated with potential
-- non-concordant aggressive care.
-- The criterion for NO is aggressive care continued or escalated AFTER a documented
-- comfort-oriented goal — not merely aggressive care in the final 72 h. Most patients who die in
-- hospital receive pressors or ventilation right up to death without any prior DNR/CMO order, which
-- is not non-concordance, so the previous NO stratum was largely mislabelled and the real NO cases
-- (the care-quality failures the scenario is about) were never sought. The intervention is now required
-- to postdate the comfort-goal charting.
--   ESCALATE : no code-status documentation at all — goals can't be established, so concordance is
--              unassessable (indeterminate, lack of data).
--   NO       : a comfort-oriented goal (DNR / DNI / comfort measures) is charted, and an intensive
--              intervention STARTS AFTER that charttime — potential non-beneficial aggressive care.
--   YES      : goals documented and no intensive intervention after the goal was set (de-escalated,
--              concordant).
WITH died AS (
  SELECT subject_id, hadm_id, CAST(deathtime AS TIMESTAMP) AS deathtime FROM admissions
  WHERE hospital_expire_flag = 1 AND deathtime IS NOT NULL
),
code_status AS (
  SELECT DISTINCT ce.hadm_id
    FROM chartevents ce JOIN died d ON d.hadm_id = ce.hadm_id
    WHERE ce.itemid IN (223758, 229784, 228687) AND ce.value IS NOT NULL
),
-- earliest charted COMFORT-ORIENTED goal; interventions before this are not non-concordant
comfort_goal AS (
  SELECT ce.hadm_id, MIN(CAST(ce.charttime AS TIMESTAMP)) AS goal_time
    FROM chartevents ce JOIN died d ON d.hadm_id = ce.hadm_id
    WHERE ce.itemid IN (223758, 229784, 228687) AND ce.value IS NOT NULL
      AND (ce.value ILIKE '%DNR%' OR ce.value ILIKE '%DNI%' OR ce.value ILIKE '%comfort%'
           OR ce.value ILIKE '%CMO%' OR ce.value ILIKE '%do not resus%')
    GROUP BY ce.hadm_id
),
intensive AS (
  SELECT DISTINCT ie.hadm_id
    FROM inputevents ie JOIN died d ON d.hadm_id = ie.hadm_id
                        JOIN comfort_goal g ON g.hadm_id = ie.hadm_id
    WHERE ie.itemid IN (221906, 221289, 221749, 222315, 221662, 221653)
      AND CAST(ie.starttime AS TIMESTAMP) >= d.deathtime - INTERVAL 72 HOUR
      AND CAST(ie.starttime AS TIMESTAMP) > g.goal_time
  UNION
  SELECT DISTINCT pe.hadm_id
    FROM procedureevents pe JOIN died d ON d.hadm_id = pe.hadm_id
                            JOIN comfort_goal g ON g.hadm_id = pe.hadm_id
    WHERE pe.itemid IN (224385, 225802, 225803, 225809, 225955, 225441)
      AND CAST(pe.starttime AS TIMESTAMP) >= d.deathtime - INTERVAL 72 HOUR
      AND CAST(pe.starttime AS TIMESTAMP) > g.goal_time
  UNION
  SELECT DISTINCT ce.hadm_id
    FROM chartevents ce JOIN died d ON d.hadm_id = ce.hadm_id
                        JOIN comfort_goal g ON g.hadm_id = ce.hadm_id
    WHERE ce.itemid IN (223849, 229314)
      AND CAST(ce.charttime AS TIMESTAMP) >= d.deathtime - INTERVAL 72 HOUR
      AND CAST(ce.charttime AS TIMESTAMP) > g.goal_time
)
SELECT d.subject_id, d.hadm_id,
  CASE
    WHEN d.hadm_id NOT IN (SELECT hadm_id FROM code_status) THEN 'ESCALATE'
    WHEN d.hadm_id IN (SELECT hadm_id FROM intensive) THEN 'NO'
    ELSE 'YES'
  END AS expected_label
FROM died d
ORDER BY d.hadm_id
