-- scenario-20 postop-complications — 3-way silver STRATIFIER (YES / NO / ESCALATE; the two
-- indeterminate classes merge to ESCALATE). Returns (subject_id, hadm_id, procedure_time). This
-- label is only a cheap structured splitter — the real Yes/No/Escalate is decided downstream; here
-- we just carve the operative pool into three balanced strata from structured signals only
-- (no notes, no LLM).
--
-- Eligible = an admission on a surgical service that underwent a major OPERATIVE procedure.
-- procedure_time = the earliest operative procedure date on the admission (ICD-9 procedure codes
-- 01-86 = operations, or any ICD-10-PCS Medical & Surgical section-0 code), cast to a timestamp —
-- procedures_icd carries a date only, so this is midnight of the operative day (the best index
-- time the hosp module exposes). comp_signal = a cheap post-op complication footprint: a PRBC/
-- platelet transfusion, a (re)intubation / dialysis event, or an AKI creatinine rise, all after
-- the operative date. has_preop_cr = a pre-op creatinine baseline exists (needed to judge AKI).
--   ESCALATE : no pre-op creatinine baseline — AKI can't be assessed and the screen is
--              incomplete (indeterminate, lack of data).
--   YES      : a post-op complication footprint is present.
--   NO       : baseline present but no post-op complication footprint.
WITH op AS (
  SELECT p.subject_id, p.hadm_id, MIN(CAST(p.chartdate AS TIMESTAMP)) AS procedure_time
  FROM procedures_icd p
  WHERE (p.icd_version = 9 AND regexp_matches(p.icd_code, '^(0[1-9]|[1-7][0-9]|8[0-6])'))
     OR (p.icd_version = 10 AND p.icd_code LIKE '0%')
  GROUP BY p.subject_id, p.hadm_id
),
surg AS (
  SELECT DISTINCT hadm_id FROM services
  WHERE curr_service IN ('SURG', 'CSURG', 'VSURG', 'TSURG', 'PSURG', 'NSURG', 'ORTHO', 'GYN', 'GU', 'ENT')
),
elig AS (
  SELECT op.subject_id, op.hadm_id, op.procedure_time
  FROM op JOIN surg USING (hadm_id)
),
preop_cr AS (
  SELECT DISTINCT e.hadm_id
    FROM elig e JOIN labevents l ON l.hadm_id = e.hadm_id
    WHERE l.itemid IN (50912, 52546) AND l.valuenum IS NOT NULL
      AND CAST(l.charttime AS TIMESTAMP) < e.procedure_time
),
preop_base AS (
  SELECT e.hadm_id, MIN(l.valuenum) AS cr_base
    FROM elig e JOIN labevents l ON l.hadm_id = e.hadm_id
    WHERE l.itemid IN (50912, 52546) AND l.valuenum IS NOT NULL
      AND CAST(l.charttime AS TIMESTAMP) < e.procedure_time
    GROUP BY e.hadm_id
),
postop_cr AS (
  SELECT e.hadm_id, MAX(l.valuenum) AS cr_peak
    FROM elig e JOIN labevents l ON l.hadm_id = e.hadm_id
    WHERE l.itemid IN (50912, 52546) AND l.valuenum IS NOT NULL
      AND CAST(l.charttime AS TIMESTAMP) >= e.procedure_time
    GROUP BY e.hadm_id
),
aki AS (
  SELECT b.hadm_id FROM preop_base b JOIN postop_cr p USING (hadm_id)
    WHERE p.cr_peak >= 1.5 * b.cr_base
),
comp AS (
  SELECT DISTINCT ie.hadm_id
    FROM inputevents ie JOIN elig e ON e.hadm_id = ie.hadm_id
    WHERE ie.itemid IN (225168, 220996) AND ie.starttime > e.procedure_time
  UNION
  SELECT DISTINCT pe.hadm_id
    FROM procedureevents pe JOIN elig e ON e.hadm_id = pe.hadm_id
    WHERE pe.itemid IN (224385, 225802, 225803, 225809, 225955, 225441) AND pe.starttime > e.procedure_time
  UNION
  SELECT hadm_id FROM aki
)
SELECT e.subject_id, e.hadm_id, e.procedure_time,
  CASE
    WHEN e.hadm_id NOT IN (SELECT hadm_id FROM preop_cr) THEN 'ESCALATE'
    WHEN e.hadm_id IN (SELECT hadm_id FROM comp) THEN 'YES'
    ELSE 'NO'
  END AS expected_label
FROM elig e
ORDER BY e.hadm_id
