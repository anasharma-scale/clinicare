-- scenario-03 PE-workup adequacy — 3-way silver labels (YES / NO / ESCALATE). This is only a
-- STRATIFIER: it splits the eligible pool (chest-pain / dyspnea ED presentations) into three
-- balanced strata from cheap structured signals; the real label is decided downstream by a
-- majority vote of models doing the task, so clinical precision is not required here.
-- Returns (subject_id, hadm_id, expected_label); select_cohort.py balances + samples.
--
-- Eligible pool = chest-pain ED presentations. Structured signals:
--   ct  = a CT-scan radiology order was placed (poe order_subtype 'CT Scan') — proxy for CTPA.
--   dd  = a D-dimer was drawn (labevents 50915 / 51196 / 52551).
--   YES      : a CT scan was ordered (imaging workup performed).
--   NO       : a D-dimer was drawn but no CT scan (workup started, imaging not done).
--   ESCALATE : neither D-dimer nor CT scan on record (workup silent / unassessable).
WITH cp AS (
  SELECT DISTINCT e.subject_id, e.hadm_id
  FROM edstays e JOIN ed_triage t USING (stay_id)
  WHERE e.hadm_id IS NOT NULL
    AND (t.chiefcomplaint ILIKE '%chest pain%' OR t.chiefcomplaint ILIKE '%chest pressure%'
         OR regexp_matches(t.chiefcomplaint, '(^|[^A-Za-z])CP([^A-Za-z]|$)', 'i'))),
dd AS (SELECT DISTINCT hadm_id FROM labevents WHERE itemid IN (50915, 51196, 52551) AND hadm_id IS NOT NULL),
ct AS (SELECT DISTINCT hadm_id FROM poe WHERE order_subtype = 'CT Scan' AND hadm_id IS NOT NULL)
SELECT cp.subject_id, cp.hadm_id,
  CASE
    WHEN cp.hadm_id NOT IN (SELECT hadm_id FROM ct)
     AND cp.hadm_id NOT IN (SELECT hadm_id FROM dd) THEN 'ESCALATE'
    WHEN cp.hadm_id IN (SELECT hadm_id FROM ct) THEN 'YES'
    ELSE 'NO'
  END AS expected_label
FROM cp
