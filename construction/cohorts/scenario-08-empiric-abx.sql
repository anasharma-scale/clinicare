-- scenario-08 empiric-antibiotic appropriateness (stewardship) — 3-way silver labels
-- (YES / NO / ESCALATE). This is only a STRATIFIER: it splits the eligible pool into three
-- balanced strata from cheap structured signals; the real label is decided downstream by a
-- majority vote of models doing the task, so clinical precision is not required here.
-- Returns (subject_id, hadm_id, expected_label); select_cohort.py balances + samples.
--
-- Eligible pool = ICU admissions with a radiology note (the CXR) and
-- a positive blood culture reported WITH a susceptibility panel (org_name + ab_name +
-- interpretation present). Structured signals over the blood-culture panel:
--   any_r    = any antibiotic reported RESISTANT.
--   pos_spec = number of positive blood-culture specimens.
--   YES      : all panel results susceptible AND >1 positive specimen (empiric choice covered,
--              growth is a plausible pathogen).
--   NO       : some antibiotic reported RESISTANT (empiric choice may miss the organism).
--   ESCALATE : only a single positive specimen (contaminant-vs-pathogen ambiguity).
WITH bc AS (
  SELECT hadm_id,
         MAX(CASE WHEN interpretation = 'R' THEN 1 ELSE 0 END) AS any_resistant,
         COUNT(DISTINCT CASE WHEN org_name IS NOT NULL THEN micro_specimen_id END) AS pos_spec
  FROM microbiologyevents
  WHERE spec_type_desc ILIKE '%blood cult%' AND hadm_id IS NOT NULL
    AND org_name IS NOT NULL AND ab_name IS NOT NULL AND interpretation IS NOT NULL
  GROUP BY hadm_id),
cxr AS (SELECT DISTINCT hadm_id FROM radiology_notes WHERE hadm_id IS NOT NULL),
icu AS (SELECT DISTINCT hadm_id FROM icustays WHERE hadm_id IS NOT NULL)
SELECT a.subject_id, a.hadm_id,
  CASE
    WHEN bc.pos_spec = 1 THEN 'ESCALATE'
    WHEN bc.any_resistant = 1 THEN 'NO'
    ELSE 'YES'
  END AS expected_label
FROM admissions a
  JOIN bc  ON bc.hadm_id = a.hadm_id
  JOIN cxr ON cxr.hadm_id = a.hadm_id
  JOIN icu ON icu.hadm_id = a.hadm_id
