-- scenario-05 renal trajectory — 3-way silver labels (YES / NO / ESCALATE) per the clinician
-- rubric in scenario.toml. Returns (subject_id, expected_label).
--
-- Per-admission baseline = in-admission creatinine nadir (itemid 50912). net_delta =
-- last - first admission baseline (chronological). The new rubric is conservative about NO
-- because stable creatinine can mask GFR decline as muscle mass falls (the confound), so:
--   YES      : net_delta >= 0.5 — a clear sustained rise, robust to the muscle confound.
--   NO       : flat (|net_delta| <= 0.15) AND modest (max baseline <= 1.4) AND confound
--              defused — no coded CKD/AKI and not elderly (anchor_age < 65).
--   ESCALATE : < 2 admissions with creatinine (sparse); OR flat/mild (net_delta < 0.3) with
--              coded CKD/AKI or an older patient (anchor_age >= 70) — the lab-vs-ICD
--              discordance / muscle-mass confound that needs a human read.
WITH cr AS (
  SELECT hadm_id, MIN(valuenum) AS base FROM labevents
  WHERE itemid = 50912 AND valuenum IS NOT NULL AND hadm_id IS NOT NULL GROUP BY hadm_id),
adm AS (SELECT a.subject_id, a.admittime, c.base FROM admissions a JOIN cr c USING (hadm_id)),
ranked AS (
  SELECT subject_id, base,
    ROW_NUMBER() OVER (PARTITION BY subject_id ORDER BY admittime) AS rn,
    COUNT(*) OVER (PARTITION BY subject_id) AS n_adm,
    FIRST_VALUE(base) OVER (PARTITION BY subject_id ORDER BY admittime) AS first_base,
    LAST_VALUE(base) OVER (PARTITION BY subject_id ORDER BY admittime
      ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_base,
    MAX(base) OVER (PARTITION BY subject_id) AS max_base
  FROM adm),
ckd AS (  -- any coded CKD / AKI (the codes that drive lab-vs-ICD discordance)
  SELECT DISTINCT subject_id FROM diagnoses_icd
  WHERE icd_code LIKE 'N18%' OR icd_code LIKE '585%' OR icd_code IN ('N179', '5849')),
subj AS (
  SELECT r.subject_id, r.n_adm, r.first_base, r.last_base, r.max_base, p.anchor_age,
         (r.subject_id IN (SELECT subject_id FROM ckd)) AS has_ckd
  FROM ranked r JOIN patients p USING (subject_id)
  WHERE r.rn = 1),
labeled AS (
  SELECT subject_id,
    CASE
      WHEN n_adm < 2 THEN 'ESCALATE'
      WHEN last_base - first_base >= 0.5 THEN 'YES'
      WHEN (last_base - first_base) < 0.3 AND (has_ckd OR anchor_age >= 70) THEN 'ESCALATE'
      WHEN abs(last_base - first_base) <= 0.15 AND max_base <= 1.4
           AND NOT has_ckd AND anchor_age < 65 THEN 'NO'
    END AS expected_label
  FROM subj)
SELECT subject_id, expected_label FROM labeled WHERE expected_label IS NOT NULL
