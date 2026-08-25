-- scenario-12 hyperacute stroke time-target audit — 3-way silver STRATIFIER (YES / NO / ESCALATE).
-- Not a clinical label: it only splits the eligible pool (ischemic-stroke admissions that
-- arrived through the ED, so edstays gives an arrival clock) into three balanced strata from
-- cheap structured signals; the real verdict is decided downstream. Returns
-- (subject_id, hadm_id, stay_id); stay_id is the earliest ED stay of the admission.
--   YES      : a systemic thrombolytic was administered (emar alteplase/tenecteplase, or
--              inputevents 221319) — the treated-in-window path.
--   ESCALATE : no lytic AND the ED triage acuity is missing (or no triage row) — arrival
--              severity / thrombolysis eligibility cannot be established from structured data.
--   NO       : the remaining eligible pool (arrived, triaged, no lytic given).
WITH stroke AS (
  SELECT DISTINCT subject_id, hadm_id FROM diagnoses_icd
  WHERE (icd_version = 10 AND icd_code LIKE 'I63%')
     OR (icd_version = 9  AND icd_code IN ('43301','43311','43321','43331','43381','43391','43401','43411','43491'))),
ed AS (SELECT hadm_id, arg_min(stay_id, intime) AS stay_id FROM edstays WHERE hadm_id IS NOT NULL GROUP BY hadm_id),
lysed AS (
  SELECT DISTINCT hadm_id FROM emar
    WHERE (medication ILIKE '%altepl%' OR medication ILIKE '%tenectep%')
      AND medication NOT ILIKE '%clearance%' AND medication NOT ILIKE '%cathet%'
      AND medication NOT ILIKE '%flush%' AND medication NOT ILIKE '%dialysis%' AND medication NOT ILIKE '%port%'
  UNION SELECT DISTINCT hadm_id FROM inputevents WHERE itemid = 221319),
acuity_ok AS (SELECT DISTINCT stay_id FROM ed_triage WHERE acuity IS NOT NULL)
SELECT s.subject_id, s.hadm_id, ed.stay_id,
  CASE
    WHEN s.hadm_id IN (SELECT hadm_id FROM lysed)         THEN 'YES'
    WHEN ed.stay_id NOT IN (SELECT stay_id FROM acuity_ok) THEN 'ESCALATE'
    ELSE 'NO'
  END AS expected_label
FROM stroke s
JOIN ed ON ed.hadm_id = s.hadm_id
