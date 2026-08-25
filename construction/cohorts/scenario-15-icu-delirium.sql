-- scenario-15 ICU delirium screening & ABCDEF management — 3-way silver STRATIFIER (YES / NO /
-- ESCALATE). This label is only a cheap structured stratifier that splits the eligible pool into
-- balanced thirds; the real Yes/No/Escalate is decided downstream by a 3-model majority vote, so
-- clinical precision is not required here. Returns (subject_id, hadm_id, stay_id, expected_label).
--
-- Eligible = ICU stay with a deliriogenic-sedation risk factor (a continuous sedative/analgesic
-- infusion). Structured signals from chartevents keyed by the ICU stay_id: the count of CAM-ICU
-- feature charting events, and whether any RASS was charted (itemid 228096).
--   ESCALATE : no CAM-ICU AND no RASS charting — neither delirium-screening stream is present, so
--              whether screening occurred cannot be determined (lack of data).
--   YES      : >= 5 CAM-ICU charting events — screened at a meaningful frequency.
--   NO       : some screening present but sparse (< 5 CAM-ICU events, or RASS only) (catch-all).
WITH sed AS (
  SELECT DISTINCT stay_id FROM inputevents
  WHERE itemid IN (225150, 221623, 221744, 225942, 225972, 221833, 221385, 221668, 222168, 227210)
),
cam AS (
  SELECT stay_id, COUNT(*) AS n FROM chartevents
  WHERE itemid IN (228300, 228301, 228302, 228303, 228334, 228335, 228336, 228337, 229324, 229325, 229326)
  GROUP BY stay_id
),
rass AS (SELECT DISTINCT stay_id FROM chartevents WHERE itemid = 228096),
elig AS (
  SELECT i.subject_id, i.hadm_id, i.stay_id,
         COALESCE((SELECT n FROM cam WHERE cam.stay_id = i.stay_id), 0) AS cam_n,
         (i.stay_id IN (SELECT stay_id FROM rass)) AS has_rass
  FROM icustays i
  WHERE i.stay_id IN (SELECT stay_id FROM sed))
SELECT subject_id, hadm_id, stay_id,
  CASE
    WHEN cam_n = 0 AND NOT has_rass THEN 'ESCALATE'
    WHEN cam_n >= 5                 THEN 'YES'
    ELSE 'NO'
  END AS expected_label
FROM elig
