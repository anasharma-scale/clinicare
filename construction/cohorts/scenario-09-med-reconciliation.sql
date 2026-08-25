-- scenario-09 medication-reconciliation discrepancy — 3-way silver labels (YES / NO / ESCALATE). This
-- is only a STRATIFIER: it splits the eligible pool into three balanced strata from cheap
-- structured signals; the real label is decided downstream by a majority vote of models doing the
-- task, so clinical precision is not required here.
-- Returns (subject_id, hadm_id, stay_id, expected_label); stay_id is the ED stay medrecon is
-- keyed on (task param). select_cohort.py balances + samples.
--
-- Eligible pool = admissions that arrived through the ED (a medrecon
-- HOME-med list exists, keyed by ED stay_id) AND have a discharge note, so all three
-- reconciliation sources exist. Structured signals:
--   n_home = number of distinct home meds (medrecon); polypharmacy raises discrepancy odds.
--   died   = hospital_expire_flag (patient died in hospital).
--   YES      : polypharmacy (>= 10 home meds) — higher chance of an unintended discrepancy.
--   NO       : fewer home meds — less to reconcile.
--   ESCALATE : patient died in hospital (no discharge list to reconcile against).
WITH ed AS (
  SELECT hadm_id, subject_id,
         arg_min(stay_id, CAST(intime AS TIMESTAMP)) AS stay_id
  FROM edstays WHERE hadm_id IS NOT NULL GROUP BY hadm_id, subject_id),
home AS (
  SELECT stay_id, COUNT(DISTINCT name) AS n_home FROM medrecon GROUP BY stay_id),
disch AS (SELECT DISTINCT hadm_id FROM discharge_notes WHERE hadm_id IS NOT NULL)
SELECT ed.subject_id, ed.hadm_id, ed.stay_id,
  CASE
    WHEN a.hospital_expire_flag = 1 THEN 'ESCALATE'
    WHEN home.n_home >= 10 THEN 'YES'
    ELSE 'NO'
  END AS expected_label
FROM ed
  JOIN home  ON home.stay_id = ed.stay_id
  JOIN disch ON disch.hadm_id = ed.hadm_id
  JOIN admissions a ON a.hadm_id = ed.hadm_id
WHERE home.n_home > 0
