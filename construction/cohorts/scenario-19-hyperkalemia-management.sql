-- scenario-19 acute hyperkalemia management sequence — 3-way silver labels (YES / NO / ESCALATE;
-- the two indeterminate classes merge to ESCALATE) per the clinician rubric in scenario.toml.
-- Returns (subject_id, hadm_id, k_anchor_time, expected_label); k_anchor_time is the task
-- param (first K ≥ 5.5). select_cohort.py balances + samples.
--
-- Anchor = first potassium ≥ 5.5 (itemid 50971 / 50822) falling inside an ICU stay window (so
-- interventions are captured in inputevents). severe = anchor ≥ 6.5. Within 4 h of the anchor:
--   calcium  221456 / 229618 / 229640 / 228317 (membrane stabilization)
--   shift    insulin 223258, dextrose 220952, bicarbonate 220995 / 221211 / 227533
--   eliminate furosemide 221794 / 228340
-- responded = a K in (anchor, anchor + 6 h] drops ≥ 0.4 below the anchor or below 5.5.
--   YES      : responded AND the expected agents were given — severe: calcium + a shift/elim
--              agent; moderate: any of calcium/shift/elim.
--   NO       : severe with NO calcium in 4 h (missed membrane stabilization); OR an agent was
--              given but K did not respond (ineffective / deviation).
--   ESCALATE : no follow-up K in 6 h (response unassessable); or mild/untreated-but-resolving
--              and other ambiguous middle cases.
WITH k_ev AS (
  SELECT s.subject_id, s.hadm_id, s.stay_id, CAST(l.charttime AS TIMESTAMP) AS t, l.valuenum
  FROM icustays s JOIN labevents l
    ON l.subject_id = s.subject_id AND l.itemid IN (50971, 50822) AND l.valuenum >= 5.5
   AND CAST(l.charttime AS TIMESTAMP) BETWEEN s.intime AND s.outtime
   -- Drop hemolyzed specimens: a "HEMOLYSIS FALSELY ELEVATES K" comment means pseudo-
   -- hyperkalemia — not a real event to grade management against.
   AND (l.comments IS NULL OR l.comments NOT ILIKE '%hemol%')),
anchor AS (
  SELECT subject_id, hadm_id, stay_id, t AS k_anchor_time, valuenum AS k0,
         ROW_NUMBER() OVER (PARTITION BY hadm_id ORDER BY t) AS rn
  FROM k_ev),
a AS (SELECT subject_id, hadm_id, stay_id, k_anchor_time, k0 FROM anchor WHERE rn = 1),
ca AS (SELECT DISTINCT a.hadm_id FROM a JOIN inputevents ie ON ie.stay_id = a.stay_id
       AND ie.itemid IN (221456, 229618, 229640, 228317)
       AND CAST(ie.starttime AS TIMESTAMP) BETWEEN a.k_anchor_time AND a.k_anchor_time + INTERVAL 4 HOUR),
shift AS (SELECT DISTINCT a.hadm_id FROM a JOIN inputevents ie ON ie.stay_id = a.stay_id
       AND ie.itemid IN (223258, 220952, 220995, 221211, 227533)
       AND CAST(ie.starttime AS TIMESTAMP) BETWEEN a.k_anchor_time AND a.k_anchor_time + INTERVAL 4 HOUR),
elim AS (SELECT DISTINCT a.hadm_id FROM a JOIN inputevents ie ON ie.stay_id = a.stay_id
       AND ie.itemid IN (221794, 228340)
       AND CAST(ie.starttime AS TIMESTAMP) BETWEEN a.k_anchor_time AND a.k_anchor_time + INTERVAL 4 HOUR),
follow AS (SELECT a.hadm_id, MIN(l.valuenum) AS kmin FROM a JOIN labevents l
       ON l.subject_id = a.subject_id AND l.itemid IN (50971, 50822) AND l.valuenum IS NOT NULL
      AND CAST(l.charttime AS TIMESTAMP) > a.k_anchor_time
      AND CAST(l.charttime AS TIMESTAMP) <= a.k_anchor_time + INTERVAL 6 HOUR GROUP BY 1),
flags AS (
  SELECT a.subject_id, a.hadm_id, a.k_anchor_time, a.k0,
         (a.k0 >= 6.5) AS severe,
         (a.hadm_id IN (SELECT hadm_id FROM ca)) AS has_ca,
         (a.hadm_id IN (SELECT hadm_id FROM shift)) AS has_shift,
         (a.hadm_id IN (SELECT hadm_id FROM elim)) AS has_elim,
         f.kmin
  FROM a LEFT JOIN follow f USING (hadm_id)),
labeled AS (
  SELECT subject_id, hadm_id, k_anchor_time,
    CASE
      WHEN kmin IS NULL THEN 'ESCALATE'
      WHEN severe AND NOT has_ca THEN 'NO'
      WHEN (kmin < k0 - 0.4 OR kmin < 5.5)
           AND (CASE WHEN severe THEN has_ca AND (has_shift OR has_elim)
                     ELSE has_ca OR has_shift OR has_elim END) THEN 'YES'
      WHEN (has_ca OR has_shift OR has_elim) AND NOT (kmin < k0 - 0.4 OR kmin < 5.5) THEN 'NO'
      ELSE 'ESCALATE'
    END AS expected_label
  FROM flags
  -- Exclude the ungradeable "dead zone": a moderate anchor (< 6.5) that received NO hyperkalemia-
  -- directed therapy. The rubric's Yes/No branches are both gated on SEVERE hyperkalemia, so a
  -- moderate, untreated (often self-resolving) case fits neither and the oracles fall back to
  -- "medical ambiguity". Keep every severe case and every case that actually received treatment.
  -- (Fuller fix would be to expand the rubric to grade moderate hyperkalemia explicitly.)
  WHERE severe OR has_ca OR has_shift OR has_elim)
SELECT subject_id, hadm_id, k_anchor_time, expected_label FROM labeled
