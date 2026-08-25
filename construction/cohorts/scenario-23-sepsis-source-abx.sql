-- scenario-23 sepsis source identification & antibiotic evolution — 3-way silver labels
-- (YES / NO / ESCALATE). This is only a STRATIFIER: it splits the eligible pool into three
-- balanced strata from cheap structured signals; the real label is decided downstream by a
-- majority vote of models doing the task, so clinical precision is not required here.
-- Returns (subject_id, hadm_id, expected_label); select_cohort.py balances + samples.
--
-- Eligible pool = admissions coded with severe sepsis / septic shock
-- that received an IV antibiotic (emar administration) and had cultures drawn. Structured signals
-- over microbiologyevents:
--   any_growth = any culture grew an organism.
--   n_org      = number of distinct organisms grown.
--   YES      : exactly one organism grown (a single source identified, therapy tailorable).
--   NO       : no growth on any culture (source not microbiologically identified).
--   ESCALATE : >= 2 distinct organisms grown (multiple candidate sources — ambiguous).
WITH sep AS (
  SELECT DISTINCT hadm_id FROM diagnoses_icd
  WHERE hadm_id IS NOT NULL
    AND ((icd_version = 9  AND icd_code IN ('78552','99592'))
      OR (icd_version = 10 AND (icd_code LIKE 'R652%' OR icd_code LIKE 'T8112%')))),
abx AS (
  SELECT DISTINCT hadm_id FROM emar
  WHERE event_txt = 'Administered' AND hadm_id IS NOT NULL
    AND regexp_matches(medication,
      '(vancomycin|piperacillin|tazobactam|cefepime|ceftriaxone|ceftazidime|cefazolin|ciprofloxacin|levofloxacin|moxifloxacin|meropenem|imipenem|ertapenem|metronidazole|azithromycin|ampicillin|amoxicillin|gentamicin|tobramycin|amikacin|linezolid|aztreonam|daptomycin|clindamycin|doxycycline|tigecycline|nafcillin|oxacillin|penicillin|sulfamethoxazole|trimethoprim)', 'i')),
cx AS (
  SELECT hadm_id,
         MAX(CASE WHEN org_name IS NOT NULL THEN 1 ELSE 0 END) AS any_growth,
         COUNT(DISTINCT CASE WHEN org_name IS NOT NULL THEN org_name END) AS n_org
  FROM microbiologyevents WHERE hadm_id IS NOT NULL GROUP BY hadm_id)
SELECT a.subject_id, a.hadm_id,
  CASE
    WHEN cx.n_org >= 2 THEN 'ESCALATE'
    WHEN cx.any_growth = 1 THEN 'YES'
    ELSE 'NO'
  END AS expected_label
FROM admissions a
  JOIN sep ON sep.hadm_id = a.hadm_id
  JOIN abx ON abx.hadm_id = a.hadm_id
  JOIN cx  ON cx.hadm_id = a.hadm_id
