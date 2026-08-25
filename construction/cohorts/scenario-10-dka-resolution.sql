-- scenario-10 DKA resolution & protocol adherence — 3-way silver labels (YES / NO / ESCALATE; the
-- two indeterminate classes merge to ESCALATE) per the clinician rubric in scenario.toml. Returns
-- (subject_id, hadm_id, stay_id, expected_label); select_cohort.py balances + samples.
--
-- Cohort = ICU stays on a DKA-coded admission. Window = [ICU intime, intime + 24 h]. Resolution
-- = two CONSECUTIVE anion-gap draws (itemid 50868) both ≤ 12 within the window. Insulin =
-- regular insulin (itemid 223258) started in the window. This silver rule scores the
-- resolution axis; the fuller protocol-concordance judgment (dextrose trigger, SC overlap,
-- K-hold) is left to the golden pass.
--   YES      : resolved in 24 h (2 consecutive AG ≤ 12) with insulin given.
--   NO       : adequate AG sampling (≥ 2 draws) + insulin given, but no 2-consecutive AG ≤ 12
--              in 24 h — clear non-resolution.
--   ESCALATE : ESRD/dialysis confound; < 2 AG draws in-window (insufficient sampling); or no
--              in-window regular-insulin event attributable to the stay.
WITH dka AS (
  SELECT DISTINCT hadm_id FROM diagnoses_icd
  WHERE regexp_matches(icd_code, '^(2501[0-3]|E(08|09|10|11|13)1[01])$')),
stays AS (
  SELECT s.subject_id, s.hadm_id, s.stay_id, s.intime
  FROM icustays s WHERE s.hadm_id IN (SELECT hadm_id FROM dka)),
ag AS (
  SELECT st.stay_id, l.valuenum,
         ROW_NUMBER() OVER (PARTITION BY st.stay_id ORDER BY CAST(l.charttime AS TIMESTAMP)) AS rn
  FROM stays st JOIN labevents l
    ON l.subject_id = st.subject_id AND l.itemid = 50868 AND l.valuenum IS NOT NULL
   AND CAST(l.charttime AS TIMESTAMP) BETWEEN st.intime AND st.intime + INTERVAL 24 HOUR),
ag_pairs AS (
  SELECT stay_id, valuenum, LAG(valuenum) OVER (PARTITION BY stay_id ORDER BY rn) AS prev FROM ag),
resolved AS (SELECT DISTINCT stay_id FROM ag_pairs WHERE valuenum <= 12 AND prev <= 12),
ag_cnt AS (SELECT stay_id, COUNT(*) AS n_ag FROM ag GROUP BY 1),
insulin AS (
  SELECT DISTINCT st.stay_id FROM stays st JOIN inputevents ie
    ON ie.stay_id = st.stay_id AND ie.itemid = 223258
   AND CAST(ie.starttime AS TIMESTAMP) BETWEEN st.intime AND st.intime + INTERVAL 24 HOUR),
esrd AS (SELECT DISTINCT subject_id FROM diagnoses_icd WHERE icd_code IN ('N186', 'Z992', '5856', 'V4511')),
labeled AS (
  SELECT st.subject_id, st.hadm_id, st.stay_id,
    CASE
      WHEN st.subject_id IN (SELECT subject_id FROM esrd) THEN 'ESCALATE'
      WHEN COALESCE(ac.n_ag, 0) < 2 THEN 'ESCALATE'
      WHEN st.stay_id NOT IN (SELECT stay_id FROM insulin) THEN 'ESCALATE'
      WHEN st.stay_id IN (SELECT stay_id FROM resolved) THEN 'YES'
      ELSE 'NO'
    END AS expected_label
  FROM stays st LEFT JOIN ag_cnt ac USING (stay_id))
SELECT subject_id, hadm_id, stay_id, expected_label FROM labeled
