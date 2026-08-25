-- scenario-18 pneumonia severity–disposition concordance (CURB-65) — 3-way silver labels
-- (YES / NO / ESCALATE; the two indeterminate classes merge to ESCALATE) per the clinician
-- rubric in scenario.toml. Returns (subject_id, hadm_id, expected_label).
--
-- Cohort = pneumonia admissions (ICD-9 480–486 / ICD-10 J12–J18) that came through the ED, so
-- triage vitals give the admission values. Confusion — the 5th CURB-65 point — needs the note
-- and can't be computed here, so cscore is the 4 objective points (BUN > 19 [51006], RR ≥ 30,
-- SBP < 90 or DBP ≤ 60, age ≥ 65); true CURB-65 = cscore or cscore + 1. Disposition proxy =
-- ICU vs non-ICU (any icustays row for the hadm).
-- Banding per the clinician correction in scenario.toml: 0-1 low (community/OP or ward), 2 ward,
-- 3-5 ward, and only 4-5 warrants ICU. So a ward disposition is concordant for a true score of
-- 0-3 and non-concordant at 4-5; an ICU disposition is concordant at 4-5 and over-triage at 0-1.
-- The unscored confusion point can add at most 1, so it only changes the verdict at cscore = 3
-- (true 3 or 4 — ward either concordant or not). That, not cscore 1-2, is the ambiguous stratum:
-- at cscore 1-2 the true score is 1-3, which is ward-concordant either way.
--   YES      : ward & cscore ≤ 2, or ICU & cscore ≥ 4 (concordant however confusion falls).
--   NO       : ward & cscore ≥ 4 (undertriaged), or ICU & cscore ≤ 1 (overtriaged).
--   ESCALATE : cscore = 3 — the confusion point tips the ICU threshold, so the note is needed
--              (maps to the scenario's 'confusion component genuinely ambiguous' criterion); or no
--              triage vitals at all, so no component can be recovered. A missing BUN alone is NOT
--              escalated: the criteria allow it to be imputed from age when other components are
--              present, so the previous `bun IS NULL` escalation contradicted them.
WITH pna AS (
  SELECT DISTINCT hadm_id FROM diagnoses_icd
  WHERE regexp_matches(icd_code, '^(48[0-6]|J1[2-8])') AND hadm_id IS NOT NULL),
triage AS (
  SELECT e.hadm_id, t.resprate, t.sbp, t.dbp,
         ROW_NUMBER() OVER (PARTITION BY e.hadm_id ORDER BY CAST(e.intime AS TIMESTAMP)) AS rn
  FROM edstays e JOIN ed_triage t USING (stay_id)
  WHERE e.hadm_id IN (SELECT hadm_id FROM pna)),
bun AS (
  SELECT hadm_id, valuenum AS bun,
         ROW_NUMBER() OVER (PARTITION BY hadm_id ORDER BY CAST(charttime AS TIMESTAMP)) AS rn
  FROM labevents
  WHERE itemid = 51006 AND valuenum IS NOT NULL AND hadm_id IN (SELECT hadm_id FROM pna)),
base AS (
  SELECT a.subject_id, a.hadm_id, p.anchor_age,
         tv.resprate, tv.sbp, tv.dbp, b.bun,
         (a.hadm_id IN (SELECT hadm_id FROM icustays)) AS is_icu
  FROM admissions a
  JOIN patients p USING (subject_id)
  JOIN (SELECT * FROM triage WHERE rn = 1) tv USING (hadm_id)
  LEFT JOIN (SELECT * FROM bun WHERE rn = 1) b USING (hadm_id)
  WHERE a.hadm_id IN (SELECT hadm_id FROM pna)),
scored AS (
  SELECT *,
    (CASE WHEN bun > 19 THEN 1 ELSE 0 END
     + CASE WHEN resprate >= 30 THEN 1 ELSE 0 END
     + CASE WHEN sbp < 90 OR dbp <= 60 THEN 1 ELSE 0 END
     + CASE WHEN anchor_age >= 65 THEN 1 ELSE 0 END) AS cscore
  FROM base),
labeled AS (
  SELECT subject_id, hadm_id,
    CASE
      WHEN resprate IS NULL AND sbp IS NULL AND dbp IS NULL THEN 'ESCALATE'
      WHEN cscore = 3 THEN 'ESCALATE'
      WHEN is_icu     THEN CASE WHEN cscore >= 4 THEN 'YES' WHEN cscore <= 1 THEN 'NO' ELSE 'YES' END
      ELSE                 CASE WHEN cscore >= 4 THEN 'NO' ELSE 'YES' END
    END AS expected_label
  FROM scored)
SELECT subject_id, hadm_id, expected_label FROM labeled
