-- scenario-25 altered-mental-status workup completeness — 3-way silver STRATIFIER (YES / NO /
-- ESCALATE). This label is only a cheap structured stratifier that splits the eligible pool; the
-- real Yes/No/Escalate is decided downstream. Returns (subject_id, hadm_id, expected_label).
--
-- Eligible = admission coded for altered mental status (altered consciousness, AMS, delirium,
-- metabolic/toxic/unspecified encephalopathy, stupor/coma) with a discharge summary available.
--
-- Do NOT escalate merely because TSH / ammonia / toxicology went undrawn: an indicated element
-- that was not performed is a NO ("≥1 INDICATED element was not performed"). The lack-of-data
-- criterion is about the workup streams being absent, not about tests going unordered. Proxying
-- it that way empties both indeterminate strata, and both need to be reachable.
--
-- Each indeterminate class is therefore proxied on its own criterion:
--   ESCALATE : no labevents at all for the admission — the workup streams are genuinely absent, so
--              completeness cannot be confirmed either way (lack of data). OR ammonia was not drawn
--              while the LFTs are abnormal but no liver disease is coded — per the clinician note,
--              ammonia is indicated only in known or suspected liver disease, so whether this
--              omission is a fault is genuinely ambiguous (medical ambiguity).
--   NO       : liver disease IS coded and ammonia was still not drawn — a clearly indicated element
--              clearly omitted.
--   YES      : TSH and toxicology both drawn, with no clearly-indicated omission — a broad battery.
WITH ams AS (
  SELECT DISTINCT hadm_id FROM diagnoses_icd
  WHERE hadm_id IS NOT NULL AND (
    (icd_version = 9  AND icd_code IN ('7800','78001','78002','78009','78097','34831','34982','2930','2931')) OR
    (icd_version = 10 AND icd_code IN ('R4182','R400','R401','R402','R4020','F05','G92','G928','G929','G934','G9340','G9341')))
),
tsh AS (SELECT DISTINCT hadm_id FROM labevents WHERE itemid = 50993 AND hadm_id IS NOT NULL),
amm AS (SELECT DISTINCT hadm_id FROM labevents WHERE itemid = 50866 AND hadm_id IS NOT NULL),
tox AS (SELECT DISTINCT hadm_id FROM labevents
        WHERE itemid IN (50922, 50856, 50981, 50879, 50880, 50999, 51071, 51074, 51075, 51079, 51083, 51090, 51092)
          AND hadm_id IS NOT NULL),
any_lab AS (SELECT DISTINCT hadm_id FROM labevents WHERE hadm_id IS NOT NULL),
-- ALT (50861) or AST (50878) above roughly twice the upper reference limit
abn_lft AS (
  SELECT DISTINCT hadm_id FROM labevents
  WHERE hadm_id IS NOT NULL AND itemid IN (50861, 50878) AND valuenum IS NOT NULL AND valuenum >= 80),
liver_icd AS (
  SELECT DISTINCT hadm_id FROM diagnoses_icd
  WHERE hadm_id IS NOT NULL AND (
    (icd_version = 9  AND (icd_code LIKE '571%' OR icd_code LIKE '572%' OR icd_code LIKE '5723%')) OR
    (icd_version = 10 AND (icd_code LIKE 'K70%' OR icd_code LIKE 'K71%' OR icd_code LIKE 'K72%'
        OR icd_code LIKE 'K73%' OR icd_code LIKE 'K74%' OR icd_code LIKE 'K76%')))),
elig AS (
  SELECT a.subject_id, a.hadm_id,
         (a.hadm_id IN (SELECT hadm_id FROM tsh))       AS has_tsh,
         (a.hadm_id IN (SELECT hadm_id FROM amm))       AS has_amm,
         (a.hadm_id IN (SELECT hadm_id FROM tox))       AS has_tox,
         (a.hadm_id IN (SELECT hadm_id FROM any_lab))   AS has_labs,
         (a.hadm_id IN (SELECT hadm_id FROM abn_lft))   AS abn_lft,
         (a.hadm_id IN (SELECT hadm_id FROM liver_icd)) AS liver
  FROM admissions a
  WHERE a.hadm_id IN (SELECT hadm_id FROM ams)
    AND a.hadm_id IN (SELECT hadm_id FROM discharge_notes))
SELECT subject_id, hadm_id,
  CASE
    WHEN NOT has_labs                                THEN 'ESCALATE'
    WHEN NOT has_amm AND abn_lft AND NOT liver       THEN 'ESCALATE'
    WHEN NOT has_amm AND liver                       THEN 'NO'
    WHEN has_tsh AND has_tox                         THEN 'YES'
    ELSE 'NO'
  END AS expected_label
FROM elig
