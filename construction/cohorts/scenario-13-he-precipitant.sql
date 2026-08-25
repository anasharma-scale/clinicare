-- scenario-13 hepatic-encephalopathy precipitant workup — 3-way silver STRATIFIER (YES / NO /
-- ESCALATE). This label is only a cheap structured stratifier that splits the eligible pool into
-- balanced thirds; the real Yes/No/Escalate is decided downstream by a 3-model majority vote, so
-- clinical precision is not required here. Returns (subject_id, hadm_id, expected_label).
--
-- Eligible = cirrhotic admission (a cirrhosis code PLUS a hepatic-failure / hepatic- or
-- metabolic-encephalopathy code on the same admission) with a discharge summary available.
-- Structured signals: whether any microbiology specimen was sent (workup breadth) and whether
-- serum ammonia (itemid 50866) was drawn.
--   ESCALATE : no cultures sent — the SBP/infection precipitant was never worked up, so the
--              precipitant cannot be determined from structured data (lack of data).
--   YES      : cultures sent AND ammonia drawn — the major candidates were evaluated.
--   NO       : cultures sent but no ammonia — worked up but battery incomplete (catch-all).
WITH cirr AS (
  SELECT DISTINCT hadm_id FROM diagnoses_icd
  WHERE hadm_id IS NOT NULL AND (
    (icd_version = 9  AND icd_code IN ('5712','5715','5716','07044','07022')) OR
    (icd_version = 10 AND (icd_code LIKE 'K703%' OR icd_code = 'K717'
        OR icd_code LIKE 'K74%' OR icd_code LIKE 'K704%')))
),
he AS (
  SELECT DISTINCT hadm_id FROM diagnoses_icd
  WHERE hadm_id IS NOT NULL AND (
    (icd_version = 9  AND icd_code IN ('5722','34831')) OR
    (icd_version = 10 AND (icd_code LIKE 'K72%' OR icd_code = 'K7041' OR icd_code = 'G9341')))
),
cult AS (SELECT DISTINCT hadm_id FROM microbiologyevents WHERE hadm_id IS NOT NULL),
amm  AS (SELECT DISTINCT hadm_id FROM labevents WHERE itemid = 50866 AND hadm_id IS NOT NULL),
elig AS (
  SELECT a.subject_id, a.hadm_id,
         (a.hadm_id IN (SELECT hadm_id FROM cult)) AS has_cult,
         (a.hadm_id IN (SELECT hadm_id FROM amm))  AS has_amm
  FROM admissions a
  WHERE a.hadm_id IN (SELECT hadm_id FROM cirr)
    AND a.hadm_id IN (SELECT hadm_id FROM he)
    AND a.hadm_id IN (SELECT hadm_id FROM discharge_notes))
SELECT subject_id, hadm_id,
  CASE
    WHEN NOT has_cult          THEN 'ESCALATE'
    WHEN has_cult AND has_amm  THEN 'YES'
    ELSE 'NO'
  END AS expected_label
FROM elig
