-- scenario-16 goals-of-care — 3-way silver STRATIFIER (YES / NO / ESCALATE; the two indeterminate
-- classes merge to ESCALATE). Returns (subject_id, hadm_id, expected_label). This label is only a
-- cheap structured splitter — the real Yes/No/Escalate is decided downstream; here we just carve
-- the eligible serious-illness pool into three balanced strata from structured signals only
-- (no notes, no LLM).
--
-- Eligible = an ICU stay, OR a serious-illness diagnosis (metastatic cancer / CHF / dementia), OR
-- death during the admission. si_present = the serious-illness qualification is anchorable from
-- structured data (a qualifying dx OR death). goc_signal = a cheap coded GOC/ACP footprint: a
-- non-full-code code-status entry, palliative-care care-plan charting, or a Z51.5/V66.7
-- palliative-encounter diagnosis.
--   ESCALATE : serious-illness status cannot be established from structured data (eligible only via
--              an ICU stay, no qualifying dx, no death) — indeterminate, lack of data.
--   YES      : a coded GOC/ACP footprint is present.
--   NO       : serious illness established but no coded GOC/ACP footprint.
WITH si_dx AS (
  SELECT DISTINCT hadm_id FROM diagnoses_icd
  WHERE (icd_version = 10 AND (icd_code LIKE 'C77%' OR icd_code LIKE 'C78%' OR icd_code LIKE 'C79%'
          OR icd_code LIKE 'C80%' OR icd_code LIKE 'I50%' OR icd_code LIKE 'F00%' OR icd_code LIKE 'F01%'
          OR icd_code LIKE 'F02%' OR icd_code LIKE 'F03%' OR icd_code LIKE 'G30%'))
     OR (icd_version = 9 AND (icd_code LIKE '196%' OR icd_code LIKE '197%' OR icd_code LIKE '198%'
          OR icd_code LIKE '199%' OR icd_code LIKE '428%' OR icd_code LIKE '290%' OR icd_code = '3310'
          OR icd_code LIKE '2941%'))
),
eligible AS (
  SELECT DISTINCT a.subject_id, a.hadm_id, a.hospital_expire_flag,
         (a.hadm_id IN (SELECT hadm_id FROM si_dx) OR a.hospital_expire_flag = 1) AS si_present
  FROM admissions a
  WHERE a.hadm_id IN (SELECT hadm_id FROM icustays)
     OR a.hadm_id IN (SELECT hadm_id FROM si_dx)
     OR a.hospital_expire_flag = 1
),
goc AS (
  SELECT DISTINCT hadm_id FROM chartevents
    WHERE hadm_id IS NOT NULL
      AND ((itemid = 223758 AND value IS NOT NULL AND value <> 'Full code')
        OR itemid IN (229150, 229152, 229154, 229155))
  UNION
  SELECT DISTINCT hadm_id FROM diagnoses_icd
    WHERE (icd_version = 10 AND icd_code = 'Z515') OR (icd_version = 9 AND icd_code = 'V667')
)
SELECT e.subject_id, e.hadm_id,
  CASE
    WHEN NOT e.si_present THEN 'ESCALATE'
    WHEN e.hadm_id IN (SELECT hadm_id FROM goc) THEN 'YES'
    ELSE 'NO'
  END AS expected_label
FROM eligible e
ORDER BY e.hadm_id
