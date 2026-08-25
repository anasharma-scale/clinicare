-- scenario-11 HFrEF guideline-directed therapy at discharge — 3-way silver STRATIFIER
-- (YES / NO / ESCALATE). Not a clinical label: it only splits the eligible pool (reduced-EF
-- heart-failure admissions with a discharge summary) into three balanced strata from a cheap
-- structured signal; the real verdict is decided downstream. Returns (subject_id, hadm_id).
-- Signal = n_pillars, the count of the four GDMT drug-classes (beta-blocker, ACEi/ARB/ARNI,
-- MRA, SGLT2i) appearing in the admission's prescriptions.
--   ESCALATE : n_pillars = 0 — no GDMT drug class on the med list (documentation ambiguous /
--              HFrEF status unestablished from structured data).
--   YES      : n_pillars >= 3 — broad GDMT present.
--   NO       : 1-2 pillars — an incomplete regimen.
--
-- HFrEF confirmation (added): the systolic/combined-HF ICD codes alone admit patients whose
-- documented echo EF is actually preserved (HFpEF/HFrecEF) — the task premise ("with HFrEF")
-- and the rubric both require EF from the echo/note value, NOT the ICD code. `ef` below parses
-- every LVEF/EF percentage from the admission's discharge + radiology notes and keeps only
-- admissions with a documented reduced value (LVEF <= 40), dropping those whose only EF evidence
-- is preserved. Note-text regex is best-effort — re-check pool counts after select_cohort.py.
WITH ef AS (
  SELECT hadm_id
  FROM (
    SELECT hadm_id,
      UNNEST(list_transform(
        regexp_extract_all(lower(text),
          '(?:lvef|ejection fraction|\bef\b)[^0-9]{0,10}([0-9]{1,3})', 1),
        x -> TRY_CAST(x AS INTEGER))) AS ef
    FROM (SELECT hadm_id, text FROM discharge_notes
          UNION ALL SELECT hadm_id, text FROM radiology_notes)
    WHERE hadm_id IS NOT NULL)
  WHERE ef BETWEEN 5 AND 80          -- drop parse noise (grades, dates, out-of-range)
  GROUP BY hadm_id
  HAVING MIN(ef) <= 40),             -- a documented reduced LVEF exists → genuine HFrEF
hf AS (
  SELECT DISTINCT subject_id, hadm_id FROM diagnoses_icd
  WHERE (icd_version = 9  AND (icd_code LIKE '4282%' OR icd_code LIKE '4284%'))
     OR (icd_version = 10 AND (icd_code LIKE 'I502%' OR icd_code LIKE 'I504%'))),
pillars AS (
  SELECT hadm_id, COUNT(DISTINCT CASE
      WHEN drug ILIKE '%carvedilol%' OR drug ILIKE '%metoprolol%' OR drug ILIKE '%bisoprolol%' THEN 'bb'
      WHEN drug ILIKE '%pril%' OR drug ILIKE '%sartan%' OR drug ILIKE '%sacubitril%' THEN 'raas'
      WHEN drug ILIKE '%spironolact%' OR drug ILIKE '%eplerenone%' THEN 'mra'
      WHEN drug ILIKE '%gliflozin%' OR drug ILIKE '%jardiance%' OR drug ILIKE '%farxiga%' OR drug ILIKE '%invokana%' THEN 'sglt2'
    END) AS n_pillars
  FROM prescriptions WHERE hadm_id IS NOT NULL GROUP BY hadm_id)
SELECT hf.subject_id, hf.hadm_id,
  CASE
    WHEN COALESCE(p.n_pillars, 0) = 0  THEN 'ESCALATE'
    WHEN p.n_pillars >= 3              THEN 'YES'
    ELSE 'NO'
  END AS expected_label
FROM hf
LEFT JOIN pillars p ON p.hadm_id = hf.hadm_id
WHERE hf.hadm_id IN (SELECT hadm_id FROM discharge_notes)
  AND hf.hadm_id IN (SELECT hadm_id FROM ef)   -- documented reduced LVEF (echo/note, not ICD)
