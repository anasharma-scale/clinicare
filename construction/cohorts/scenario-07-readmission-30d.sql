-- scenario-07 30-day readmission — 3-way silver labels (YES / NO / ESCALATE; the two indeterminate
-- classes merge to ESCALATE) per the clinician rubric in scenario.toml. Returns
-- (subject_id, hadm_id, expected_label); select_cohort.py balances + samples.
--
-- Index = an ICU admission that also had imaging (a Radiology POE order). next = the FIRST
-- admission strictly after the index dischtime for the same subject. Unplanned admit types are
-- the emergent ones (EW EMER. / DIRECT EMER. / URGENT); observation/elective/surgical are the
-- ambiguous planned-vs-transfer types.
--   YES      : next admit is unplanned AND within 30 d of index discharge.
--   NO       : the first admit after discharge is > 30 d out (no readmit in-window, and the
--              later admission itself proves ≥ 30 d of observable follow-up).
--   ESCALATE : index ended in death (no readmission possible); OR no later admission at all
--              (follow-up censored — a true negative can't be confirmed); OR a within-30 d
--              readmit whose type is observation/elective/surgical (planned-vs-transfer
--              ambiguous).
WITH idx AS (
  SELECT a.subject_id, a.hadm_id,
         CAST(a.dischtime AS TIMESTAMP) AS dischtime, a.hospital_expire_flag
  FROM admissions a
  WHERE a.dischtime IS NOT NULL
    AND a.hadm_id IN (SELECT hadm_id FROM icustays)
    AND a.hadm_id IN (SELECT hadm_id FROM poe WHERE order_type = 'Radiology' AND hadm_id IS NOT NULL)),
nxt AS (
  SELECT i.hadm_id, a2.admission_type AS next_type,
         CAST(a2.admittime AS TIMESTAMP) AS next_admit,
         ROW_NUMBER() OVER (PARTITION BY i.hadm_id
                            ORDER BY CAST(a2.admittime AS TIMESTAMP)) AS rn
  FROM idx i JOIN admissions a2
    ON a2.subject_id = i.subject_id
   AND CAST(a2.admittime AS TIMESTAMP) > i.dischtime),
first_next AS (SELECT hadm_id, next_type, next_admit FROM nxt WHERE rn = 1),
labeled AS (
  SELECT i.subject_id, i.hadm_id,
    CASE
      WHEN i.hospital_expire_flag = 1 THEN 'ESCALATE'
      WHEN fn.next_admit IS NULL THEN 'ESCALATE'
      WHEN fn.next_admit <= i.dischtime + INTERVAL 30 DAY THEN
        CASE WHEN fn.next_type IN ('EW EMER.', 'DIRECT EMER.', 'URGENT') THEN 'YES'
             ELSE 'ESCALATE' END
      ELSE 'NO'
    END AS expected_label
  FROM idx i LEFT JOIN first_next fn USING (hadm_id))
SELECT subject_id, hadm_id, expected_label FROM labeled WHERE expected_label IS NOT NULL
