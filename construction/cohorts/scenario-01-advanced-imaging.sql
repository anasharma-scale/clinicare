-- scenario-01 advanced-imaging — 3-way silver labels (YES / NO / ESCALATE) per the clinician
-- rubric in scenario.toml. Returns (subject_id, hadm_id, expected_label); select_cohort.py
-- balances + samples. CT/MRI-class = CT Scan / MRI / Cross-Sectional IR; bedside =
-- General Xray / Ultrasound / Noninvasive Vascular; ambiguous = IR / Angio / Nuclear Med / Neuro.
WITH stays AS (
  SELECT subject_id, hadm_id, intime, outtime,
         COUNT(*) OVER (PARTITION BY subject_id, hadm_id) AS n_icu
  FROM icustays),
hadm AS (SELECT subject_id, hadm_id, ANY_VALUE(n_icu) AS n_icu FROM stays GROUP BY 1, 2),
inwin AS (  -- radiology orders landing inside ANY of the hadm's ICU stay windows
  SELECT s.subject_id, s.hadm_id, p.order_subtype, p.transaction_type
  FROM stays s JOIN poe p
    ON p.subject_id = s.subject_id AND p.hadm_id = s.hadm_id AND p.order_type = 'Radiology'
   AND CAST(p.ordertime AS TIMESTAMP) BETWEEN s.intime AND s.outtime),
win AS (
  SELECT subject_id, hadm_id,
    BOOL_OR(order_subtype IN ('CT Scan', 'MRI', 'Cross-Sectional Interventional Radiology')
            AND transaction_type = 'New') AS ctmri_new,
    BOOL_OR(order_subtype IN ('General Xray', 'Ultrasound', 'Noninvasive Vascular')
            AND transaction_type = 'New') AS bedside_new,
    BOOL_OR(order_subtype IN ('Interventional Radiology', 'Angio', 'Nuclear Med', 'Interventional Neuro')
            AND transaction_type = 'New') AS ambig_new
  FROM inwin GROUP BY 1, 2),
adm_ctmri AS (  -- any CT/MRI-class radiology order anywhere in the admission
  SELECT DISTINCT subject_id, hadm_id FROM poe
  WHERE order_type = 'Radiology'
    AND order_subtype IN ('CT Scan', 'MRI', 'Cross-Sectional Interventional Radiology')),
labeled AS (
  SELECT h.subject_id, h.hadm_id,
    CASE
      -- multi-ICU-stay admission with a CT/MRI order: can't attribute to "the" stay
      WHEN h.n_icu > 1 AND ac.hadm_id IS NOT NULL THEN 'ESCALATE'
      -- single stay, a CT/MRI order placed inside the window
      WHEN h.n_icu = 1 AND COALESCE(w.ctmri_new, FALSE) THEN 'YES'
      -- single stay, only ambiguous-class imaging in window (no CT/MRI, no bedside)
      WHEN h.n_icu = 1 AND COALESCE(w.ambig_new, FALSE)
           AND NOT COALESCE(w.ctmri_new, FALSE) AND NOT COALESCE(w.bedside_new, FALSE) THEN 'ESCALATE'
      -- single stay, bedside-only imaging in window (no CT/MRI, no ambiguous)
      WHEN h.n_icu = 1 AND COALESCE(w.bedside_new, FALSE)
           AND NOT COALESCE(w.ctmri_new, FALSE) AND NOT COALESCE(w.ambig_new, FALSE) THEN 'NO'
    END AS expected_label
  FROM hadm h
  LEFT JOIN win w USING (subject_id, hadm_id)
  LEFT JOIN adm_ctmri ac USING (subject_id, hadm_id))
SELECT subject_id, hadm_id, expected_label FROM labeled WHERE expected_label IS NOT NULL
