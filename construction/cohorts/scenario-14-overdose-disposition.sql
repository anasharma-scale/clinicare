-- scenario-14 opioid-overdose disposition & post-overdose care — 3-way silver STRATIFIER (YES / NO /
-- ESCALATE). This label is only a cheap structured stratifier that splits the eligible pool into
-- balanced thirds; the real Yes/No/Escalate is decided downstream by a 3-model majority vote, so
-- clinical precision is not required here. Returns (subject_id, stay_id, hadm_id, expected_label).
--
-- Eligible = ED presentation for suspected opioid overdose that was ADMITTED (ED naloxone given,
-- excluding buprenorphine-naloxone MOUD combos, OR an opioid-poisoning diagnosis on the
-- admission) with a discharge summary available. Structured signals: an inpatient MOUD
-- prescription (buprenorphine/naltrexone/methadone) and whether any consult (social work /
-- psych / addiction) was ordered via POE.
--   YES      : MOUD prescribed — a documented evidence-based post-overdose intervention.
--   ESCALATE : no MOUD AND no consult ordered — no structured post-overdose care signal at all,
--              so guideline concordance cannot be determined (lack of data).
--   NO       : a consult was ordered but no MOUD — intervention signal present yet incomplete
--              (catch-all).
WITH nlx AS (
  SELECT DISTINCT stay_id FROM ed_pyxis
  WHERE name ILIKE '%nalox%' AND name NOT ILIKE '%buprenorphine%'
),
opioid_icd AS (
  SELECT DISTINCT hadm_id FROM diagnoses_icd
  WHERE hadm_id IS NOT NULL AND (
    (icd_version = 9  AND icd_code IN ('96500','96501','96502','96509','E8500','E8501')) OR
    (icd_version = 10 AND (icd_code LIKE 'T400%' OR icd_code LIKE 'T401%' OR icd_code LIKE 'T402%'
        OR icd_code LIKE 'T403%' OR icd_code LIKE 'T404%')))
),
moud AS (
  SELECT DISTINCT hadm_id FROM prescriptions
  WHERE hadm_id IS NOT NULL AND (drug ILIKE '%buprenorphine%' OR drug ILIKE '%naltrexone%'
     OR drug ILIKE '%methadone%' OR drug ILIKE '%suboxone%')
),
consult AS (
  SELECT DISTINCT hadm_id FROM poe
  WHERE hadm_id IS NOT NULL AND (order_type ILIKE '%consult%' OR order_subtype ILIKE '%social%'
     OR order_subtype ILIKE '%psych%' OR order_subtype ILIKE '%addiction%')
),
-- Exclude in-hospital deaths: the disposition / post-overdose secondary-prevention question
-- (MOUD offer, take-home naloxone, addiction/social-work linkage) presupposes a patient who
-- survives to discharge — for a decedent those interventions are moot, not a care gap, and the
-- oracles (correctly) can't resolve Yes/No. Requiring survival keeps every case answerable.
elig AS (
  SELECT e.subject_id, e.stay_id, e.hadm_id,
         (e.hadm_id IN (SELECT hadm_id FROM moud))    AS has_moud,
         (e.hadm_id IN (SELECT hadm_id FROM consult)) AS has_consult
  FROM edstays e
  JOIN admissions a ON a.hadm_id = e.hadm_id
  WHERE e.hadm_id IS NOT NULL
    AND a.hospital_expire_flag = 0
    AND (e.stay_id IN (SELECT stay_id FROM nlx) OR e.hadm_id IN (SELECT hadm_id FROM opioid_icd))
    AND e.hadm_id IN (SELECT hadm_id FROM discharge_notes))
SELECT subject_id, stay_id, hadm_id,
  CASE
    WHEN has_moud     THEN 'YES'
    WHEN NOT has_consult THEN 'ESCALATE'
    ELSE 'NO'
  END AS expected_label
FROM elig
