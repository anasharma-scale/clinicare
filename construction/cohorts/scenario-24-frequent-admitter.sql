-- scenario-24 frequent-admitter — 3-way silver STRATIFIER (YES / NO / ESCALATE; the two indeterminate
-- classes merge to ESCALATE). Returns one row per subject (subject_id, window_start, window_end).
-- This label is only a cheap structured splitter — the real Yes/No/Escalate is decided downstream;
-- here we just carve the frequent-admitter pool into three balanced strata from structured signals
-- only (no notes, no LLM).
--
-- Eligible = subjects with >= 3 hospital admissions. window_start = first admittime, window_end =
-- last discharge (dischtime, or deathtime if the final stay ended in death). The recurring-theme
-- test uses only coded diagnoses:
--   principal_theme  = a 3-char ICD prefix of the PRINCIPAL dx (seq_num = 1) repeats across >= 2
--                      admissions — a strong recurring theme.
--   secondary_theme  = a 3-char ICD prefix among the top-3 dx (seq_num <= 3) repeats across >= 2
--                      admissions but the principal dx does not — a weaker, ambiguous theme.
--   YES      : strong recurring principal-diagnosis theme.
--   ESCALATE : only a weaker secondary-diagnosis theme — the recurring relationship is indefinite
--              (indeterminate, medical ambiguity).
--   NO       : no recurring diagnosis theme at all.
WITH freq AS (
  SELECT subject_id,
         count(*) AS n_adm,
         MIN(admittime) AS window_start,
         MAX(COALESCE(dischtime, deathtime)) AS window_end
  FROM admissions
  GROUP BY subject_id
  HAVING count(*) >= 3
),
principal AS (
  SELECT subject_id, MAX(cnt) AS maxcnt FROM (
    SELECT d.subject_id, LEFT(d.icd_code, 3) AS pfx, count(DISTINCT d.hadm_id) AS cnt
    FROM diagnoses_icd d JOIN freq f ON f.subject_id = d.subject_id
    WHERE d.seq_num = 1
    GROUP BY d.subject_id, LEFT(d.icd_code, 3)
  ) GROUP BY subject_id
),
secondary AS (
  SELECT subject_id, MAX(cnt) AS maxcnt FROM (
    SELECT d.subject_id, LEFT(d.icd_code, 3) AS pfx, count(DISTINCT d.hadm_id) AS cnt
    FROM diagnoses_icd d JOIN freq f ON f.subject_id = d.subject_id
    WHERE d.seq_num <= 3
    GROUP BY d.subject_id, LEFT(d.icd_code, 3)
  ) GROUP BY subject_id
)
SELECT f.subject_id, f.window_start, f.window_end,
  CASE
    WHEN COALESCE(p.maxcnt, 0) >= 2 THEN 'YES'
    WHEN COALESCE(s.maxcnt, 0) >= 2 THEN 'ESCALATE'
    ELSE 'NO'
  END AS expected_label
FROM freq f
  LEFT JOIN principal p ON p.subject_id = f.subject_id
  LEFT JOIN secondary s ON s.subject_id = f.subject_id
ORDER BY f.subject_id
