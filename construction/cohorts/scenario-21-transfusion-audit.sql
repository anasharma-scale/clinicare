-- scenario-21 packed-RBC transfusion indication audit — 3-way silver STRATIFIER
-- (YES / NO / ESCALATE). Not a clinical label: it only splits the eligible pool (admissions
-- that received a PRBC transfusion) into three balanced strata from a cheap structured signal;
-- the real verdict is decided downstream. Returns (subject_id, hadm_id). Signal = the
-- pre-transfusion hemoglobin (51222 / 50811) — the last Hgb before the FIRST PRBC unit —
-- against the 7 g/dL restrictive threshold.
--   ESCALATE : no Hgb recorded before the first transfusion — pre-Hgb unavailable (lack of data).
--   YES      : pre-transfusion Hgb < 7 — below the restrictive threshold, clearly indicated.
--   NO       : pre-transfusion Hgb >= 7 — above threshold, potentially unindicated.
WITH tx AS (
  SELECT subject_id, hadm_id, MIN(CAST(starttime AS TIMESTAMP)) AS first_tx
  FROM inputevents
  WHERE itemid IN (225168, 220996, 226368, 227070) AND hadm_id IS NOT NULL
  GROUP BY subject_id, hadm_id),
pre AS (
  SELECT t.hadm_id, arg_max(l.valuenum, CAST(l.charttime AS TIMESTAMP)) AS pre_hgb
  FROM tx t JOIN labevents l
    ON l.hadm_id = t.hadm_id AND l.itemid IN (51222, 50811)
   AND l.valuenum IS NOT NULL AND l.valuenum > 0
   AND CAST(l.charttime AS TIMESTAMP) <= t.first_tx
  GROUP BY t.hadm_id)
SELECT t.subject_id, t.hadm_id,
  CASE
    WHEN p.pre_hgb IS NULL THEN 'ESCALATE'
    WHEN p.pre_hgb < 7      THEN 'YES'
    ELSE 'NO'
  END AS expected_label
FROM tx t
LEFT JOIN pre p ON p.hadm_id = t.hadm_id
