-- scenario-02 post-CT AKI (KDIGO) — 3-way silver labels (YES / NO / ESCALATE) per the clinician
-- rubric in scenario.toml. Returns (subject_id, hadm_id, expected_label).
--
-- Index CT = the single new 'CT Scan' POE order in an ICU admission (>1 CT → timing/which-CT
-- ambiguous → ESCALATE). baseline = lowest creatinine (itemid 50912) in the 7 d pre-CT, and
-- it must be STABLE (>= 2 pre values, range <= 0.3). Peak = max creatinine in (CT, CT+48h].
--   YES      : stable baseline + a post value with rise >= 0.5 OR >= 1.5x baseline (clear).
--   NO       : stable baseline + >= 2 post values + clearly no rise (peak - baseline <= 0.0).
--   ESCALATE : ESRD/dialysis; multiple CTs; no/insufficient pre baseline; labile baseline
--              (range > 0.3); no 48h-post creatinine; or only 1 post value below threshold.
-- A clear positive rise wins (YES even with 1 post value); ruling NO needs >= 2 post values.
WITH ct AS (
  SELECT subject_id, hadm_id, COUNT(*) AS n_ct, MIN(CAST(ordertime AS TIMESTAMP)) AS ct_time
  FROM poe
  WHERE order_type = 'Radiology' AND order_subtype = 'CT Scan' AND transaction_type = 'New'
    AND hadm_id IN (SELECT hadm_id FROM icustays)
  GROUP BY 1, 2),
esrd AS (SELECT DISTINCT subject_id FROM diagnoses_icd WHERE icd_code IN ('N186', 'Z992', '5856', 'V4511')),
cr AS (SELECT subject_id, CAST(charttime AS TIMESTAMP) AS t, valuenum FROM labevents
       WHERE itemid = 50912 AND valuenum IS NOT NULL AND subject_id IN (SELECT subject_id FROM ct)),
pre AS (
  SELECT ct.subject_id, ct.hadm_id, COUNT(*) AS n_pre, MIN(cr.valuenum) AS pre_min, MAX(cr.valuenum) AS pre_max
  FROM ct JOIN cr ON cr.subject_id = ct.subject_id AND cr.t BETWEEN ct.ct_time - INTERVAL 7 DAY AND ct.ct_time
  GROUP BY 1, 2),
post AS (
  SELECT ct.subject_id, ct.hadm_id, COUNT(*) AS n_post, MAX(cr.valuenum) AS post_max
  FROM ct JOIN cr ON cr.subject_id = ct.subject_id AND cr.t > ct.ct_time AND cr.t <= ct.ct_time + INTERVAL 48 HOUR
  GROUP BY 1, 2),
labeled AS (
  SELECT ct.subject_id, ct.hadm_id,
    CASE
      WHEN ct.subject_id IN (SELECT subject_id FROM esrd) THEN 'ESCALATE'
      WHEN ct.n_ct > 1 THEN 'ESCALATE'
      WHEN COALESCE(pre.n_pre, 0) < 2 THEN 'ESCALATE'
      WHEN pre.pre_max - pre.pre_min > 0.3 THEN 'ESCALATE'
      WHEN COALESCE(post.n_post, 0) = 0 THEN 'ESCALATE'
      WHEN post.post_max - pre.pre_min >= 0.5 OR post.post_max >= 1.5 * pre.pre_min THEN 'YES'
      WHEN post.n_post >= 2 AND post.post_max - pre.pre_min <= 0.0 THEN 'NO'
      WHEN post.n_post < 2 THEN 'ESCALATE'
    END AS expected_label
  FROM ct LEFT JOIN pre USING (subject_id, hadm_id) LEFT JOIN post USING (subject_id, hadm_id))
SELECT subject_id, hadm_id, expected_label FROM labeled WHERE expected_label IS NOT NULL
