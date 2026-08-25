-- scenario-17 anticoagulation-reversal concordance — 3-way silver STRATIFIER (YES / NO / ESCALATE).
-- Not a clinical label: it only splits the eligible pool (anticoagulated patients carrying a
-- major-bleed diagnosis, with a discharge summary) into three balanced strata from cheap
-- structured signals; the real verdict is decided downstream. Returns (subject_id, hadm_id).
--   YES      : a reversal agent was given (vitamin K, PCC/Kcentra/FEIBA, idarucizumab,
--              andexanet, protamine, or FFP via inputevents) — a reversal decision was acted on.
--   ESCALATE : no reversal AND the patient is on a DOAC / LMWH — the INR-based anticoagulation
--              screen is uninformative for these agents, so concordance is unassessable
--              from structured data (lack of data).
--   NO       : the remaining eligible pool (warfarin-only bleed, no reversal given).
-- anticoag: the patient must have been ON a reversal-relevant oral anticoagulant AT PRESENTATION.
-- Two tightenings vs. the original "any anticoagulant prescribed this admission":
--   (1) drop enoxaparin/LMWH — usually VTE prophylaxis, not the therapeutic AC whose reversal the
--       rubric grades; keeping it admitted non-anticoagulated patients (aspirin-only etc.).
--   (2) require the drug to start within admittime + 1 day — a proxy for a HOME anticoagulant
--       continued on admission, excluding AC that was newly STARTED in-hospital (e.g. warfarin
--       begun to treat a new DVT), which is the opposite of a reversal scenario.
WITH anticoag AS (
  SELECT DISTINCT p.hadm_id FROM prescriptions p
  JOIN admissions a ON a.hadm_id = p.hadm_id
  WHERE p.hadm_id IS NOT NULL AND (
    p.drug ILIKE '%warfarin%' OR p.drug ILIKE '%coumadin%' OR p.drug ILIKE '%apixaban%' OR p.drug ILIKE '%eliquis%'
    OR p.drug ILIKE '%rivaroxab%' OR p.drug ILIKE '%xarelto%' OR p.drug ILIKE '%dabigat%' OR p.drug ILIKE '%pradaxa%'
    OR p.drug ILIKE '%edoxab%')
    AND CAST(p.starttime AS TIMESTAMP) <= CAST(a.admittime AS TIMESTAMP) + INTERVAL 1 DAY),
-- Thrombolysis exclusion: a post-tPA hemorrhagic transformation is a fibrinolytic complication,
-- not an anticoagulant-associated bleed — the anticoag-reversal guidelines don't apply.
tpa AS (
  SELECT DISTINCT hadm_id FROM diagnoses_icd
    WHERE (icd_version = 10 AND icd_code = 'Z9282')
       OR (icd_version = 9  AND icd_code = 'V4588')
  UNION
  SELECT DISTINCT hadm_id FROM prescriptions WHERE hadm_id IS NOT NULL AND (
    drug ILIKE '%alteplase%' OR drug ILIKE '%tenecteplase%' OR drug ILIKE '%reteplase%'
    OR drug ILIKE '%activase%' OR drug ILIKE '%cathflo%')),
bleed AS (
  SELECT DISTINCT hadm_id FROM diagnoses_icd WHERE
    (icd_version = 9  AND (icd_code IN ('430','431') OR icd_code LIKE '432%' OR icd_code IN ('5780','5781','5789','5693')))
 OR (icd_version = 10 AND (icd_code LIKE 'I60%' OR icd_code LIKE 'I61%' OR icd_code LIKE 'I62%' OR icd_code LIKE 'K92%'
        OR icd_code IN ('K250','K252','K254','K256','K260','K262','K264','K266','K625')))),
reversed AS (
  SELECT DISTINCT hadm_id FROM prescriptions WHERE hadm_id IS NOT NULL AND (
    drug ILIKE '%phytonadione%' OR drug ILIKE '%vitamin k%' OR drug ILIKE '%kcentra%' OR drug ILIKE '%prothrombin%'
    OR drug ILIKE '%profilnine%' OR drug ILIKE '%feiba%' OR drug ILIKE '%idaruc%' OR drug ILIKE '%andexan%'
    OR drug ILIKE '%protamine%')
  UNION SELECT DISTINCT hadm_id FROM inputevents WHERE itemid IN (220970, 226367, 227072)),
doac AS (SELECT DISTINCT hadm_id FROM prescriptions WHERE hadm_id IS NOT NULL AND (
    drug ILIKE '%apixaban%' OR drug ILIKE '%eliquis%' OR drug ILIKE '%rivaroxab%' OR drug ILIKE '%xarelto%'
    OR drug ILIKE '%dabigat%' OR drug ILIKE '%pradaxa%' OR drug ILIKE '%edoxab%' OR drug ILIKE '%enoxapar%'))
SELECT dx.subject_id, a.hadm_id,
  CASE
    WHEN a.hadm_id IN (SELECT hadm_id FROM reversed) THEN 'YES'
    WHEN a.hadm_id IN (SELECT hadm_id FROM doac)     THEN 'ESCALATE'
    ELSE 'NO'
  END AS expected_label
FROM anticoag a
JOIN bleed b ON b.hadm_id = a.hadm_id
JOIN (SELECT DISTINCT hadm_id, subject_id FROM diagnoses_icd) dx ON dx.hadm_id = a.hadm_id
WHERE a.hadm_id IN (SELECT hadm_id FROM discharge_notes)
  AND a.hadm_id NOT IN (SELECT hadm_id FROM tpa)   -- exclude post-thrombolytic bleeds
