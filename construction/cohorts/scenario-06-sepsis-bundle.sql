-- scenario-06 SEP-1 sepsis-bundle compliance — 3-way silver labels (YES / NO / ESCALATE). This is
-- only a STRATIFIER: it splits the eligible pool into three balanced strata from cheap structured
-- signals; the real label is decided downstream by a majority vote of models doing the task, so
-- clinical precision is not required here.
-- Returns (subject_id, hadm_id, expected_label); select_cohort.py balances + samples.
--
-- Eligible pool = MICU admissions that arrived through the ED (ED
-- triage = the bundle time-zero), had an infection work-up (blood culture and/or lactate), and
-- received an IV antibiotic (emar administration). Structured signals:
--   first_abx = first antibiotic ADMINISTRATION time (emar); timely = within 3 h of ED arrival.
--   lactate   = a lactate (50813) was drawn.
--   YES      : first antibiotic administered within 3 h of ED arrival (3-hour element met).
--   NO       : first antibiotic administered > 3 h after ED arrival (out-of-window).
--   ESCALATE : no lactate on record (a bundle investigation element is missing / unassessable).
WITH ed AS (
  SELECT hadm_id, MIN(CAST(intime AS TIMESTAMP)) AS ed_in
  FROM edstays WHERE hadm_id IS NOT NULL GROUP BY hadm_id),
micu AS (
  SELECT DISTINCT hadm_id FROM icustays
  WHERE first_careunit ILIKE '%MICU%' AND hadm_id IS NOT NULL),
abx AS (
  SELECT hadm_id, MIN(CAST(charttime AS TIMESTAMP)) AS first_abx
  FROM emar
  WHERE event_txt = 'Administered' AND hadm_id IS NOT NULL
    AND regexp_matches(medication,
      '(vancomycin|piperacillin|tazobactam|cefepime|ceftriaxone|ceftazidime|cefazolin|ciprofloxacin|levofloxacin|moxifloxacin|meropenem|imipenem|ertapenem|metronidazole|azithromycin|ampicillin|amoxicillin|gentamicin|tobramycin|amikacin|linezolid|aztreonam|daptomycin|clindamycin|doxycycline|tigecycline|nafcillin|oxacillin|penicillin|sulfamethoxazole|trimethoprim)', 'i')
  GROUP BY hadm_id),
lac AS (SELECT DISTINCT hadm_id FROM labevents WHERE itemid = 50813 AND hadm_id IS NOT NULL),
infx AS (
  SELECT DISTINCT hadm_id FROM microbiologyevents
    WHERE spec_type_desc ILIKE '%blood cult%' AND hadm_id IS NOT NULL
  UNION
  SELECT DISTINCT hadm_id FROM labevents WHERE itemid = 50813 AND hadm_id IS NOT NULL),
-- Require an actual sepsis / severe-sepsis / septic-shock diagnosis. A drawn lactate + any IV
-- antibiotic (the old eligibility) admitted many non-septic MICU patients (decompensated
-- cirrhosis, ALS with mucus plugging, elective endocarditis work-ups) — SEP-1 bundle grading
-- doesn't apply to them, and the oracles (correctly) can't render Yes/No, defaulting to
-- "medical ambiguity". This gates the pool to patients who met sepsis recognition.
sepsis_dx AS (
  SELECT DISTINCT hadm_id FROM diagnoses_icd WHERE hadm_id IS NOT NULL AND (
      (icd_version = 9  AND icd_code IN ('99591','99592','78552'))
   OR (icd_version = 10 AND (icd_code IN ('R6520','R6521') OR icd_code LIKE 'A40%' OR icd_code LIKE 'A41%'))))
SELECT a.subject_id, a.hadm_id,
  CASE
    WHEN a.hadm_id NOT IN (SELECT hadm_id FROM lac) THEN 'ESCALATE'
    WHEN abx.first_abx <= ed.ed_in + INTERVAL 3 HOUR THEN 'YES'
    ELSE 'NO'
  END AS expected_label
FROM admissions a
  JOIN ed        ON ed.hadm_id = a.hadm_id
  JOIN micu      ON micu.hadm_id = a.hadm_id
  JOIN abx       ON abx.hadm_id = a.hadm_id
  JOIN infx      ON infx.hadm_id = a.hadm_id
  JOIN sepsis_dx ON sepsis_dx.hadm_id = a.hadm_id
WHERE a.admission_type NOT ILIKE '%elective%'
  AND a.admission_type NOT ILIKE '%observation%'
