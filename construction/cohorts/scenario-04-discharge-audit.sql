-- scenario-04 discharge-summary factual audit — 3-way silver STRATIFIER (YES / NO / ESCALATE).
-- Not a clinical label: it only splits the eligible pool into three strata from cheap structured
-- signals; the real verdict is decided downstream. Returns (note_id, hadm_id).
--
-- The stratum has to correlate with the criterion, which grades CHECKABLE claims only — ones whose
-- subject has a corresponding structured stream. Selecting on the chart alone cannot work here:
-- the verdict depends on what the NOTE asserts, so eligibility must pair a claim in the note text
-- with the stream that checks it. (Keying on "a fever was charted at some point", say, is
-- near-universal in ICU and says nothing about what the summary claims.)
--
-- Claim used: the temperature family, checked against charted temperature. It is the one claim type
-- that is both reliably phrased in discharge summaries and cheaply checkable in chartevents.
--   YES      : the summary claims afebrile / no fevers AND a temperature >= 38.0 C (223762) or
--              100.4 F (223761) is charted — a contradicted checkable claim.
--   NO       : the summary makes a temperature claim and no such temperature is charted — supported.
--   ESCALATE : the summary makes a temperature claim but the admission has NO charted temperature at
--              all, so the claim cannot be adjudicated either way (lack of data).
WITH notes AS (
  SELECT d.note_id, d.hadm_id, d.text
  FROM discharge_notes d
  WHERE d.hadm_id IN (SELECT hadm_id FROM icustays)
    -- eligibility: the summary must make a detectable, checkable temperature claim
    AND (d.text ILIKE '%afebrile%' OR d.text ILIKE '%no fever%' OR d.text ILIKE '%remained febrile%')),
temps AS (
  SELECT hadm_id,
         COUNT(*) AS n_temp,
         MAX(CASE WHEN (itemid = 223762 AND valuenum >= 38.0)
                    OR (itemid = 223761 AND valuenum >= 100.4) THEN 1 ELSE 0 END) AS any_fever
  FROM chartevents
  WHERE hadm_id IS NOT NULL AND itemid IN (223761, 223762) AND valuenum IS NOT NULL
  GROUP BY hadm_id)
SELECT n.note_id, n.hadm_id,
  CASE
    WHEN t.hadm_id IS NULL OR t.n_temp = 0 THEN 'ESCALATE'
    WHEN (n.text ILIKE '%afebrile%' OR n.text ILIKE '%no fever%')
         AND t.any_fever = 1               THEN 'YES'
    ELSE 'NO'
  END AS expected_label
FROM notes n
LEFT JOIN temps t ON t.hadm_id = n.hadm_id
