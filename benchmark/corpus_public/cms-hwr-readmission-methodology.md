---
source: "https://www.cms.gov/medicare/quality-initiatives-patient-assessment-instruments/mms/downloads/mmshospital-wideall-conditionreadmissionrate.pdf"
type: pdf
title: "Hospital-Wide (All-Condition) 30-Day Risk-Standardized Readmission Measure: Methodology Report"
---

# Hospital-Wide (All-Condition) 30-Day Risk-Standardized Readmission Measure

## DRAFT Measure Methodology Report

**Submitted By Yale New Haven Health Services Corporation/Center for Outcomes Research & Evaluation (YNHHSC/CORE):**

Leora Horwitz, MD, MHS
Chohreh Partovian, MD, PhD
Zhenqiu Lin, PhD
Jeph Herrin, PhD
Jacqueline Grady, MS
Mitchell Conover, BA
Julia Montague, MPH
Chloe Dillaway, BA
Kathleen Bartczak, BA
Joseph Ross, MD
Susannah Bernheim, MD, MHS
Elizabeth Drye, MD, SM
Harlan M. Krumholz, MD, SM

Contract number: HHSM-500-2008-0025I/HHSM-500-T0001, Modification No. 000005

**Prepared For:**

Centers for Medicare & Medicaid Services (CMS)

**Last updated August 10, 2011**

## TABLE OF CONTENTS

LIST OF TABLES......................................................................................................................4

LIST OF FIGURES ....................................................................................................................5

GLOSSARY OF TERMS...........................................................................................................6

1. INTRODUCTION ...................................................................................................................7

&nbsp;&nbsp;&nbsp;&nbsp;1.1&nbsp;&nbsp;&nbsp;&nbsp;Overview of Measure.................................................................................................7

&nbsp;&nbsp;&nbsp;&nbsp;1.2&nbsp;&nbsp;&nbsp;&nbsp;Hospital-wide Readmission as a Quality Indicator ....................................................7

&nbsp;&nbsp;&nbsp;&nbsp;1.3&nbsp;&nbsp;&nbsp;&nbsp;Approach to Measure Development ...........................................................................8

2. METHODS.............................................................................................................................9

&nbsp;&nbsp;&nbsp;&nbsp;2.1&nbsp;&nbsp;&nbsp;&nbsp;Overview....................................................................................................................9

&nbsp;&nbsp;&nbsp;&nbsp;2.2&nbsp;&nbsp;&nbsp;&nbsp;Outcome Definition ..................................................................................................10

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.2.1&nbsp;&nbsp;&nbsp;&nbsp;Planned readmissions .........................................................................................10

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.2.2&nbsp;&nbsp;&nbsp;&nbsp;Thirty-day timeframe ...........................................................................................14

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.2.3&nbsp;&nbsp;&nbsp;&nbsp;All-cause readmission .........................................................................................17

&nbsp;&nbsp;&nbsp;&nbsp;2.3&nbsp;&nbsp;&nbsp;&nbsp;Definition of Eligible Population ...............................................................................17

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.3.1&nbsp;&nbsp;&nbsp;&nbsp;Grouping patients into clinically coherent discharge condition categories by using AHRQ Clinical Classification System (AHRQ-CCS) .................................................17

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.3.2&nbsp;&nbsp;&nbsp;&nbsp;Inclusion / exclusion criteria ................................................................................18

&nbsp;&nbsp;&nbsp;&nbsp;2.4&nbsp;&nbsp;&nbsp;&nbsp;Administrative Model Development .........................................................................20

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.4.1&nbsp;&nbsp;&nbsp;&nbsp;Data sources .....................................................................................................20

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.4.2&nbsp;&nbsp;&nbsp;&nbsp;Multiple models .................................................................................................22

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.4.3&nbsp;&nbsp;&nbsp;&nbsp;Models are defined by care team (service line) or clinical coherence .................22

&nbsp;&nbsp;&nbsp;&nbsp;2.5&nbsp;&nbsp;&nbsp;&nbsp;Risk Adjustment.......................................................................................................24

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.5.1&nbsp;&nbsp;&nbsp;&nbsp;Complications of hospitalization .........................................................................24

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.5.2&nbsp;&nbsp;&nbsp;&nbsp;Case mix adjustment: risk variables ...................................................................25

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.5.3&nbsp;&nbsp;&nbsp;&nbsp;Service mix adjustment ......................................................................................26

&nbsp;&nbsp;&nbsp;&nbsp;2.6&nbsp;&nbsp;&nbsp;&nbsp;Statistical Approach to Model Development ............................................................26

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.6.1&nbsp;&nbsp;&nbsp;&nbsp;Models for each cohort of conditions .................................................................26

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.6.2&nbsp;&nbsp;&nbsp;&nbsp;Hospital performance reporting ..........................................................................28

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.6.3&nbsp;&nbsp;&nbsp;&nbsp;Creating interval estimates.................................................................................28

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.6.4&nbsp;&nbsp;&nbsp;&nbsp;Algorithm ...........................................................................................................28

3. RESULTS ............................................................................................................................30

4. SUMMARY ..........................................................................................................................32

5. REFERENCES ....................................................................................................................33
6. APPENDIX – TABLES........................................................................................................36
   - Appendix A – Top 10 primary discharge diagnoses for planned procedures ......................36
   - Appendix B – List of AHRQ procedure CCs defining the surgical/gynecological cohort......45
   - Appendix C – Condition categories assigned to the medical cohorts..................................48
   - Appendix D – Conditions that are treated as complications if occurring during index admission...................................................................................................................................54
   - Appendix E –Candidate risk variables ................................................................................56
   - Appendix F – Final risk-adjustment variables ......................................................................57

**LIST OF TABLES**

Table 1 – Planned procedure list ....................................................................................................12

Table 2 – Discharge condition categories considered acute or complications of care................13

Table 3 – Admissions, readmissions and mortality for the seven cohorts (2008).......................24

Table 4 – Frequency of hospitals in each cohort (Number of hospitals = 4919).........................31

Table 5 – Number of hospitals based on number of models to which they contribute................31

Table 6 – C-statistic for each model .............................................................................................31

**LIST OF FIGURES**

Figure 1 – Graphical representation of time to readmission .......................................................15

Figure 2 – Inclusion and exclusion criteria* ...............................................................................21

Figure 3 – Distribution of 30-day hospital-wide readmission rates .............................................30

&nbsp;&nbsp;&nbsp;&nbsp;Figure 3a –Unadjusted rate ....................................................................................................30

&nbsp;&nbsp;&nbsp;&nbsp;Figure 3b –Risk-standardized rate .........................................................................................30

## GLOSSARY OF TERMS

| Term | Definition |
|------|------------|
| Index admission | Any eligible admission to an acute care hospital assessed in the measure for the outcome (readmitted or not within 30 days). (See **Section 2.3.2**) |
| Readmission | An admission to an acute care hospital within 30 days of discharge from an acute care hospital. (See **Section 2.2**). A readmission may in turn serve as an index admission. |
| Planned readmission | An intentional readmission within 30 days of discharge from an acute care hospital that is a scheduled part of the patient's plan of care. Planned readmissions are not counted as outcomes in this measure (see **Section 2.2.1**). |
| Discharge diagnosis | ICD-9 level code of the principal reason for hospitalization. |
| Discharge condition category | A group of related discharge diagnosis ICD-9 codes, as grouped by the Agency for Healthcare Research and Quality (AHRQ) Clinical Classification Software (CCS). (See **Section 2.3.1**). |
| Cohort | A group of admissions for patients with related condition categories or procedure categories; this measure includes seven cohorts, each with its own risk model (see **Section 2.4.3**). |
| Measure population | The full set of admissions eligible for inclusion in the measure. |
| Procedure category | A group of related procedure codes, as grouped by the Agency for Healthcare Research and Quality Clinical Classification Software (CCS) (see **Section 2.4.3**). |
| Risk variable | A variable in the risk-adjustment model intended to account for patient comorbid conditions or age. A risk variable may include multiple conditions. Each condition is a group of ICD-9 diagnosis codes, as defined by the Centers for Medicare and Medicaid Services Condition Category groups (CCs) (see **Section 2.5.2**). |
| Case mix | The variation among hospitals in illness severity and age of their patients. |
| Service mix | The variation among hospitals in the types of conditions they care for and procedures they provide. |

# 1. INTRODUCTION

## 1.1 Overview of Measure

Readmission following hospitalization is a costly and often preventable event. During 2003 and 2004, almost one-fifth of Medicare beneficiaries – over 2.3 million patients – were rehospitalized within 30 days of discharge.<sup>1</sup> Jencks estimated that readmissions within 30 days of discharge cost Medicare more than $17 billion dollars annually.<sup>1</sup> A 2006 Commonwealth Fund report estimated that if national readmission rates were lowered to the levels achieved by the top-performing regions, Medicare would save $1.9 billion annually. <sup>2</sup>

Currently, the Centers for Medicare and Medicaid Services (CMS) publicly reports risk-standardized readmission rates for heart failure, pneumonia and acute myocardial infarction. <sup>3-9</sup> CMS has also developed hospital readmission measures for stroke and for hip and knee replacement, and is developing them for chronic obstructive pulmonary disease and vascular procedures. While it is helpful to assess readmission rates for specific groups of patients, these conditions account for only a small minority of total readmissions.<sup>10</sup> By contrast, a hospital-wide, all-condition readmission measure could provide a broader assessment of the quality of care at hospitals. Therefore, CMS has contracted with Yale New Haven Health Services Corporation/Center for Outcomes Research and Evaluation (YNHHSC/CORE) to develop a claims-based, risk adjusted hospital-wide readmission (HWR) measure for public reporting that reflects the quality of care for hospitalized patients in the United States.

In this technical report we provide detailed information on the development of the HWR measure. Briefly, we developed the measure as an all-condition measure designed to capture unplanned readmissions within 30 days of discharge. The HWR measure complies with accepted standards for outcomes measure development, including appropriate risk adjustment and transparency of specifications. The measure includes all admissions except those for which a subsequent readmission would not be considered a quality signal. The measure does not count planned readmissions in the measure outcome, since they do not represent a quality signal. The overall risk-standardized readmission rate is derived from a composite of seven statistical models built for groups of admissions that are clinically related. The seven risk adjustment models will be tested for reliability in a split sample dataset combining two calendar years (2007 and 2008), and the stability of the measure over time will be tested using data from 2009. Although we developed the measure using Medicare data, the measure will also be tested in and adapted for all-payer datasets.

## 1.2 Hospital-wide Readmission as a Quality Indicator

Hospital readmission, for any reason, is disruptive to patients and caregivers, costly to the healthcare system, and puts patients at additional risk of hospital-acquired infections and complications. Readmissions are also a major source of patient and family stress and may

contribute substantially to loss of functional ability, particularly in older patients. Some readmissions are unavoidable and result from inevitable progression of disease or worsening of chronic conditions. However, readmissions may also result from poor quality of care or inadequate transitional care. Transitional care includes effective discharge planning, transfer of information at the time of discharge, patient assessment and education, and coordination of care and monitoring in the post-discharge period. Numerous studies have found an association between quality of inpatient or transitional care and early (typically 30-day) readmission rates for a wide range of conditions. <sup>11-18</sup> Therefore, while readmission rates would never be expected to be zero, *variation* in readmission rates for a broad spectrum of conditions is related to quality of care. Furthermore, randomized controlled trials have shown that improvement in the following areas can directly reduce readmission rates: quality of care during the initial admission; improvement in communication with patients, their caregivers and their clinicians; patient education; predischarge assessment; and coordination of care after discharge.<sup>20-35</sup> Evidence that hospitals have been able to reduce readmission rates through these quality-of-care initiatives illustrates the degree to which hospital practices can affect readmission rates. Successful randomized trials have reduced 30-day readmission rates by 20-40%.

Widespread application of these clinical trial interventions to general practice has also been encouraging. Since 2008, 14 Medicare Quality Improvement Organizations have been funded to focus on care transitions, applying lessons learned from clinical trials. Several have been notably successful in reducing readmissions within 30 days.<sup>36</sup>

Given that studies have shown readmissions within 30-days to be related to quality of care, and that interventions have been able to reduce 30-day readmission rates, it is reasonable to consider an all-condition 30-day readmission rate as a quality measure.

## 1.3 Approach to Measure Development

We developed this measure in consultation with national guidelines for publicly reported outcomes measures, consistent with the technical approach to outcomes measurement set forth in National Quality Forum (NQF) guidance for outcomes measures,<sup>37</sup> CMS Measure Management System guidance, and the guidance articulated in the American Heart Association scientific statement, "Standards for Statistical Models Used for Public Reporting of Health Outcomes."<sup>3</sup> These standards include adequate risk adjustment and transparency. We are obtaining expert input during measure development, both through CMS and consultation with clinical and statistical experts. We are now soliciting comments from the general public via a public comment period.

## 2. METHODS

### 2.1 Overview

We developed a hospital-wide 30-day readmission measure. This measure reports the hospital-level, risk-standardized rate of unplanned all-cause readmission after admission for any condition within 30 days of hospital discharge. The measure comprises a single summary score, derived from the results of seven different models, one for each of the following cohorts (groups of discharge condition categories or procedure categories): general medicine, surgery/gynecology, cardiorespiratory, cardiovascular, neurology, oncology, and psychiatry, each of which will be described in greater detail below. The measure uses one year of data.

We developed the measure in the Medicare fee-for-service (FFS) population age 65 and older discharged from any non-Federal short-stay acute care hospital or critical access hospital in the United States, excluding PPS-exempt cancer hospitals. The measure covers 95% of hospitalizations occurring in 2008 in this population, and includes 88% of readmissions following those hospitalizations. Hospitalizations were eligible for inclusion if the patient was enrolled in FFS Medicare Part A for 12 months prior and one month after the admission, if the discharge disposition was not to another acute care hospital, and if the patient was alive upon discharge. We excluded admissions for which we considered readmission not to be a signal of quality of care (patients who leave against medical advice, or have a discharge condition category with very high post-discharge mortality). To compare readmission performance across hospitals, we accounted for differences in patient characteristics (patient case mix) as well as differences in mixes of services and procedures offered by hospitals (hospital service mix).

To develop the measure, we analyzed admissions among Medicare FFS beneficiaries 65 and older who were discharged during 2008. The datasets were restricted to inpatient data, and included data on each patient for the 12 months prior to the index admission and the 30 days following discharge. We used the Agency for Healthcare Research and Quality (AHRQ) Condition Classification System (CCS) to group hospitalizations into clinically-coherent, mutually-exclusive condition categories according to their principal diagnosis.

We collapsed these discharge condition categories into seven major cohorts according to care teams (hospital service lines) and built a separate model for each one of these cohorts. We used hierarchical generalized linear models (HGLMs) to adjust for differences in hospital case mix and to account for the clustering of patients within a hospital. We adjusted for case mix differences among hospitals by risk-adjusting for patients' comorbid conditions identified in inpatient episodes of care for the 12 months prior to the index admission as well as those present at admission. We did not risk-adjust for diagnoses that may have been a complication of care during the index admission. We used CMS Condition Category groups (CCs) to define the comorbid risk adjusters and used a fixed set of comorbid risk variables across models. We risk-adjusted for service mix differences

among hospitals by including indicators for discharge condition categories (as defined by AHRQ CCS) in each model.

Finally, we used each of the seven models to calculate predicted and expected numbers of readmissions (as defined below in **2.6.1**) for each hospital in each cohort. We then derived a single summary score from the results of the seven models by calculating the volume-weighted log average of the predicted over expected ratios from each model and multiplying the result by the average national readmission rate. This approach allowed us to take into account the variation in service mix across hospitals.

We evaluated the performance of the measure for various types of hospitals and groups of patients. We will test the reliability of the measure by randomly splitting combined 2007 and 2008 data and comparing the performance in each split sample. We will also test the measure's stability over time by comparing 2008 and 2009 performance.

## 2.2 Outcome Definition

The outcome for this measure is unplanned all-cause 30-day readmission after an admission for any condition. We define a readmission as a subsequent inpatient admission to any acute care facility which occurs within 30 days of the discharge date of an eligible index admission. Any readmission is eligible to be counted as an outcome except those that are considered planned.

### 2.2.1 Planned readmissions

Readmissions may be either unplanned or planned. Unplanned readmissions are acute clinical events experienced by a patient that require urgent hospital management. Higher than expected unplanned readmission rates suggest lower quality of care and are the focus of quality measurement as part of quality improvement efforts. Because planned readmissions are not a signal of quality of care, we chose to exclude planned readmissions from the numerator. In order to do this, we developed an algorithm for identifying "planned readmissions" in claims data that will not count as readmissions in the measure. The algorithm was based on two main principles:

1. We define "planned" readmissions as those in which one of a pre-specified list of procedures took place (which will be described in detail below), or those for maintenance chemotherapy. Although other readmissions may be planned for medical reasons, these are rare and there is no reliable means of identifying them in administrative claims data. Maintenance chemotherapy is a common planned medical readmission that is reliably distinguishable in the data.

2. Admissions for acute illness or for complications of care are not "planned." Even a typically planned procedure performed during an admission for an acute illness would not likely have been planned. We can identify readmissions as acute or non-acute by considering the principal discharge condition.

We therefore developed an algorithm that uses procedure codes and discharge diagnosis categories for each readmission to identify planned readmissions. Readmissions that occur for planned procedures (listed below) and which are not for acute diagnoses or complications of care (listed below) are identified as planned.

The following examples illustrate this point:

Example 1:
- A readmission with a discharge condition category of biliary tract disease that included a cholecystectomy would be considered **planned**
- A readmission with a discharge condition category of septicemia that included a cholecystectomy would be considered **unplanned**
- A readmission with a discharge condition category of "complications of surgical procedures or medical care" would be considered **unplanned**

Example 2:
- A readmission with a discharge condition category of coronary atherosclerosis that included a percutaneous coronary intervention (PCI) would be considered **planned**
- A readmission with a discharge condition category of acute myocardial infarction that included PCI would be considered **unplanned**

Therefore, the HWR measure defines planned readmissions as any readmission that was either:

1. A **non-acute** readmission in which one of 32 typically planned procedures occurs

**or**

2. A readmission for maintenance chemotherapy

All other readmissions are considered unplanned and are counted as readmissions in the measure.

*List of planned procedures*

In order to develop a list of planned procedures, we reviewed the full AHRQ Clinical Classification System (CCS) procedure category list and identified 32 procedures that are typically planned and require an inpatient stay (**Table 1**). Readmissions in which any of these procedures are performed are considered planned if the discharge condition category is not acute or a complication of care.

Table 1 – Planned procedure list

| AHRQ Procedure CC | Procedure | Readmissions without an acute diagnosis or a complication of care | | All readmissions | |
|---|---|---|---|---|---|
| | | **Number** | **Percent** | **Number** | **Percent** |
| 45 | Percutaneous transluminal coronary angioplasty (PTCA) | 23,085 | 12.74 | 37,115 | 12.84 |
| 84 | Cholecystectomy and common duct exploration | 15,405 | 8.5 | 17,868 | 6.18 |
| Condition CCS 45 | Maintenance chemotherapy | 14,329 | 7.91 | 14,329 | 4.96 |
| 157 | Amputation of lower extremity | 13,131 | 7.25 | 19,085 | 6.60 |
| 51 | Endarterectomy; vessel of head and neck | 11,569 | 6.38 | 12,411 | 4.29 |
| 78 | Colorectal resection | 11,522 | 6.36 | 20,004 | 6.92 |
| 44 | Coronary artery bypass graft (CABG) | 11,119 | 6.14 | 13,311 | 4.61 |
| 152 | Arthroplasty knee | 10,475 | 5.78 | 13,959 | 4.83 |
| 113 | Transurethral resection of prostate (TURP) | 7,909 | 4.36 | 9,150 | 3.17 |
| 153 | Hip replacement; total and partial | 5,694 | 3.14 | 22,803 | 7.89 |
| 211 | Therapeutic radiology for cancer treatment | 5,422 | 2.99 | 7,479 | 2.59 |
| 158 | Spinal fusion | 5,383 | 2.97 | 7,176 | 2.48 |
| 48 | Insertion; revision; replacement; removal of cardiac pacemaker or cardioverter/defibrillator | 5,313 | 2.93 | 43,432 | 15.03 |
| 3 | Laminectomy; excision intervertebral disc | 5,172 | 2.85 | 6,541 | 2.26 |
| 36 | Lobectomy or pneumonectomy | 4,567 | 2.52 | 5,347 | 1.85 |
| 55 | Peripheral vascular bypass | 4,346 | 2.40 | 5,739 | 1.99 |
| 43 | Heart valve procedures | 4,133 | 2.28 | 4,863 | 1.68 |
| 52 | Aortic resection; replacement or anastomosis | 3,964 | 2.19 | 4,235 | 1.47 |
| 104 | Nephrectomy; partial or complete | 3,104 | 1.71 | 3,332 | 1.15 |
| 60 | Embolectomy and endarterectomy of lower limbs | 2,918 | 1.61 | 5,206 | 1.80 |
| 85 | Inguinal and femoral hernia repair | 2,387 | 1.32 | 2,785 | 0.96 |
| 124 | Hysterectomy; abdominal and vaginal | 2,143 | 1.18 | 2,223 | 0.77 |
| 167 | Mastectomy | 1,419 | 0.78 | 1,475 | 0.51 |
| 154 | Arthroplasty other than hip or knee | 1,189 | 0.66 | 2,570 | 0.89 |
| 74 | Gastrectomy; partial and total | 1,174 | 0.65 | 1,541 | 0.53 |
| 114 | Open prostatectomy | 1,035 | 0.57 | 1,069 | 0.37 |
| 119 | Oophorectomy; unilateral and bilateral | 1,005 | 0.55 | 1,275 | 0.44 |
| 10 | Thyroidectomy; partial or complete | 986 | 0.54 | 1,069 | 0.37 |
| 64 | Bone marrow transplant | 458 | 0.25 | 468 | 0.16 |
| 166 | Lumpectomy; quadrantectomy of breast | 322 | 0.18 | 471 | 0.16 |
| 105 | Kidney transplant | 240 | 0.13 | 245 | 0.08 |
| 176 | Other organ transplantation | 171 | 0.09 | 263 | 0.09 |
| ICD-9 94.26, 94.27 | Electroshock therapy | 114 | 0.06 | 139 | 0.05 |
| | **Total** | **181,203** | | | |

Data from 2008 MedPAR file, incorporating all final inclusion and exclusion criteria for the measure

*List of discharge condition categories that are acute or complications of care*

According to our algorithm, admissions in which a planned procedure was performed are only considered "planned" if the patient was not admitted for an acute illness or complication of care. To develop a list of these acute and complication discharge condition categories, we reviewed the 10 most frequent discharge condition categories associated with each of our final set of 32 potentially planned procedures (**Appendix A**). From this set of 320 condition categories, we identified those which could be categorized as acute illnesses or complications of medical care. When a discharge condition category contained a mix of acute and chronic diagnoses, it was categorized as acute. Based on these criteria, we categorized 26 discharge condition categories as acute or complications of care, all listed within **Table 2**.

Table 2 – Discharge condition categories considered acute or complications of care

| **AHRQ CC** | **Discharge condition categories that are acute or complications of care and are associated with planned procedures** | **Number of 30-day readmissions with this condition and a planned procedure** |
|---|---|---|
| 100 | Acute myocardial infarction | 18328 |
| 237 | Complication of device; implant or graft | 11624 |
| 106 | Cardiac dysrhythmias | 10915 |
| 108 | Congestive heart failure; nonhypertensive | 5922 |
| 105 | Conduction disorders | 3663 |
| 146 | Diverticulosis and diverticulitis | 2322 |
| 2 | Septicemia (except in labor) | 2227 |
| 238 | Complications of surgical procedures or medical care | 1580 |
| 116 | Aortic and peripheral arterial embolism or thrombosis | 1427 |
| | Fracture (207, 225, 226, 227, 229, 230, 231, 232) | 1320 |
| 145 | Intestinal obstruction without hernia | 1134 |
| 201 | Infective arthritis and osteomyelitis (except that caused by TB or sexually transmitted disease) | 630 |
| 109 | Acute cerebrovascular disease | 595 |
| 97 | Peri-; endo-; and myocarditis; cardiomyopathy | 550 |
| 122 | Pneumonia (except that caused by TB or sexually transmitted disease) | 431 |
| 245 | Syncope | 287 |
| 127 | Chronic obstructive pulmonary disease and bronchiectasis | 248 |
| 131 | Respiratory failure; insufficiency; arrest (adult) | 232 |
| 55 | Fluid and electrolyte disorders | 229 |
| 159 | Urinary tract infections | 161 |
| 130 | Pleurisy; pneumothorax; pulmonary collapse | 154 |
| 157 | Acute and unspecified renal failure | 115 |
| 139 | Gastroduodenal ulcer (except hemorrhage) | 91 |
| 153 | Gastrointestinal hemorrhage | 89 |
| 160 | Calculus of urinary tract | 74 |
| 112 | Transient cerebral ischemia | 30 |

| | All condition categories | 64,378 |
|---|---|---|

We quantified the impact of our decisions regarding the definition of planned readmissions on readmission rates. In 2008, there were 181,203 planned readmissions, accounting for 12% of all readmissions.

### 2.2.2 Thirty-day timeframe

We considered 30 days as a clinically reasonable timeframe for multiple reasons:

1. Within a 30-day time frame, readmissions are more likely attributable to care received during the index hospitalization and during the transition to the outpatient setting. A number of studies have demonstrated that improvements in care at the time of patient discharge can reduce 30-day readmission rates.<sup>20,21,23,28-35,38</sup> Hospitals, in collaboration with their medical communities, can take a number of actions to reduce readmissions: ensure patients are clinically ready at discharge; reduce risk of infection; reconcile medications; improve communications among providers involved in transition of care; encourage strategies that promote disease management principles; and educate patients about symptoms to monitor, whom to contact with questions, and where and when to seek follow-up care.<sup>20,21,23,28-35,38</sup>

2. The 30-day timeframe is consistent with the other readmission measures approved by the National Quality Forum (NQF) and publicly reported by CMS.

3. In addition to clinical judgment, we reviewed "time to event" curves of readmission over time to decide whether 30-day readmission is a quality signal. The readmission "time-to-event curves" showed a very similar pattern for all these discharge condition categories: a rapid early accrual of readmissions, with a stable and consistent readmission rate thereafter. Curves typically stabilized within 30 days of discharge, indicating that a 30-day cutoff is clinically reasonable. Time-to-event curves for the most common conditions are shown in **Figure 1**.

Figure 1 – Graphical representation of time to readmission

Two survival curve charts showing "Percent Not Readmitted" (y-axis) vs. "Days after discharge" (x-axis, 0–90 days).

**Chart 1 Legend:**

- Osteoarthritis
- Spondylosis; intervertebral disc disorders; other back problems
- Skin and subcutaneous tissue infections
- Other fractures
- Complications of surgical procedures or medical care
- Complication of device; implant or graft

**Chart 2 Legend:**

- Aspiration pneumonitis; food/vomitus
- Chronic obstructive pulmonary disease and bronchiectasis
- Pneumonia (except that caused by tuberculosis or sexually transmitted disease)
- Respiratory failure; insufficiency; arrest (adult)
- Asthma

### 2.2.3 All-cause readmission

We defined the outcome as "all-cause" unplanned readmissions rather than readmissions related to the previous hospitalization for multiple reasons. First, from the patient perspective, readmission for any reason is likely to be an undesirable outcome of care. Furthermore, readmission for any reason exposes the patient to risks associated with hospitalization, such as iatrogenic errors. Second, there is no reliable way to determine whether a readmission is related to the previous hospitalization based on the documented cause of readmission. For example, a stroke patient who develops aspiration pneumonia may ultimately be readmitted for respiratory distress. It would be inappropriate to treat this readmission as unrelated to the care the patient received for stroke. Third, the range of potentially avoidable readmissions also includes those not directly related to the index condition category, such as those resulting from medication reconciliation errors, poor communication at discharge, or inadequate follow-up post-discharge. Creating a comprehensive list of potentially avoidable readmissions related to the previous hospitalization's condition category would be arbitrary and, ultimately, challenging to implement. Fourth, all existing CMS readmission measures report all-cause readmission, making this approach consistent with existing measures. Fifth, research shows that readmission reduction interventions can reduce all-cause readmission, not only condition-specific readmission. Finally, defining the outcome as all-cause readmissions may encourage hospitals to implement broader initiatives aimed at improving the overall care within the hospital and transitions from the hospital setting instead of limiting the focus to a narrow set of condition-specific approaches. The goal of this measure is not to reduce readmissions to zero, but to assess hospital performance relative to what is expected given the performance of other hospitals with similar case mixes.

## 2.3 Definition of Eligible Population

Our guiding principle for defining the eligible population was that the measure should capture as many unplanned readmissions as possible across a maximum number of acute care hospitals. Therefore we included in the measure all admissions except those for which full data was not available or for which 30-day readmission cannot reasonably be considered a signal of quality of care.

### 2.3.1 Grouping patients into clinically coherent discharge condition categories by using AHRQ Clinical Classification System (AHRQ-CCS)

For our previous claims-based condition- and procedure-specific outcomes measures we have used individual ICD-9 codes or CPT codes of the index admission to define the cohort. For the HWR measure, using ICD-9 codes would have been very impractical because there are potentially thousands of ICD-9 codes that would have to be included. Therefore, we aggregated ICD-9 codes into clinically coherent conditions.

To aggregate these codes, we chose the Agency for Healthcare Research and Quality's Clinical Classifications Software (CCS). We selected CCS because 1) it is well-known and widely used, 2) it is based on the principal diagnosis and not on complications or events that occur during hospitalization (unlike the Medicare Severity Diagnosis Related Groups [MS-DRGs]), and 3) because the groups of ICD-9 codes within each category are more clinically homogenous than other available groupers (MS-DRGs and CMS Condition Categories) and have relatively similar readmission rates. AHRQ CCS has been used by managed care plans, insurers and researchers for a variety of functions, such as assessing resource use, predicting future expenses, comparing procedure or condition rates among payers or hospitals, or profiling patients. There are a total of 285 mutually exclusive AHRQ condition categories, most of which are single, homogenous diseases such as pneumonia or acute myocardial infarction. Some are aggregates of conditions, such as "other bacterial infections." Mental health and substance abuse categories are included. In addition, AHRQ provides 231 mutually exclusive procedure categories to group procedures a patient might have had during hospitalization.

2.3.2 Inclusion / exclusion criteria

Admissions are eligible for inclusion in the measure if:

i. Patient is alive upon discharge
**Rationale:** Patients who die during the initial hospitalization cannot be readmitted.

ii. Patient is not transferred to another acute care hospital upon discharge
**Rationale:** In an episode of care in which patient is transferred among hospitals, responsibility for the readmission is assigned to the final discharging hospital. Therefore these intermediate admissions within a single episode of care are not eligible for inclusion.

iii. Patient is 65 or older
**Rationale:** Younger Medicare patients represent a distinct population with dissimilar characteristics and outcomes.

iv. Patient has at least 30 days of post-discharge enrollment in FFS Medicare or died within the 30-day post-discharge period
**Rationale:** This is necessary in order to identify the outcome (readmission) in the dataset.

v. The admission is not to a PPS-exempt cancer hospital
**Rationale:** These hospitals care for a unique population of patients that is challenging to compare to other hospitals.

These inclusion criteria are consistent with existing CMS publicly reported measures for readmission except for the final one, which is unique to the HWR measure.

We then applied several exclusion criteria to the measure population. The first two are consistent with existing measures; the remainder are unique to the HWR measure.

a. Patients not continuously enrolled in FFS Medicare for the 12 months prior to the index admission are excluded
**Rationale:** This is necessary to capture historical data for risk adjustment

b. Patients discharged against medical advice (AMA) are excluded
**Rationale:** Hospital had limited opportunity to implement high quality care

c. Admissions for "rehabilitation care; fitting of prostheses and adjustment devices" (CCS 254) are excluded
**Rationale:** These admissions are not for acute care or to acute care hospitals

d. Patients admitted for a condition category with high competing mortality risk in the post-discharge period are excluded. A "high competing mortality risk condition category" is one for which there were more patients who died post-discharge without being readmitted than there were patients who were readmitted.
   i) One condition category met this criteria for all cohorts:
      - Malignant neoplasm without specification of site (CCS 43)
   ii) Several condition categories met this criteria only for the cancer and medicine cohorts (that is, admissions in the surgical cohort with these conditions were not excluded):
      - Melanomas of skin (CCS 22)
      - Cancer of breast (CCS 24)
      - Cancer of colon (CCS 14)
      - Cancer of liver and intrahepatic bile duct (CCS 16)
      - Cancer of pancreas (CCS 17)
      - Secondary malignancies (CCS 42)
      - Cancer of bronchus, lung (CCS 19)
      - Cancer of other male genital organs (CCS 31)
      - Cancer; other and unspecified primary (CCS 41)
      - Fracture of neck of femur (hip) (CCS 226)
      - Cancer of ovary (CCS 27)

**Rationale**: A high ratio of post-discharge deaths per readmissions reduces the opportunity for readmissions and interferes with the readmission quality signal. In addition the quality signal may be dwarfed by the unavoidable severity of illness.

## 2.4 Administrative Model Development

### 2.4.1 Data sources

To develop the measure, we constructed a dataset that contains administrative hospitalization data for fee-for-service (FFS) Medicare beneficiaries, 65 and older on admission, hospitalized in 2008. The dataset also includes data on each patient for the 12 months prior to the index admission and the 30 days following discharge. We obtained index admission, readmission, and in-hospital comorbidity data from the Medicare Provider Analysis and Review (MEDPAR) file. Enrollment and post-discharge mortality status were obtained from the Medicare Denominator file, which contains beneficiary demographic, benefit, coverage, and vital status information.

Comorbidities were assessed using data from the index admission and any admission in past year. The Medicare outpatient (Part B) data were not included because 1) this was technically cumbersome, and 2) it would make expanding the measure later to an all-payer population very difficult (all-payer data typically includes only data for hospitalized patients).

The final measure population is shown in **Figure 2**.

Figure 2 – Inclusion and exclusion criteria*

**Hospital Wide All Condition 30-Day All-Cause Readmission Measure**

**Medicare FFS Hospitalizations in Short Stay Acute Care Hospitals (N= 11,462,596)**

Exclusions*:
- Hospitalizations age <65 (N=2,351,081 20.5%)
- Hospitalizations with an in-hospital death (N=408,758 3.6%)
- Hospitalizations transferred to another acute care facility (N=262,785 2.3%)
- Hospitalizations with less than 30 days follow-up from discharge date (N=44,848 0.4%)
- Hospitalizations in a PPS-Exempt Cancer Hospital (N=25,987 0.2%)

**Starting Cohort (N=8,500,604)**

Exclusions*:
- Hospitalizations with incomplete administrative data in 12 months prior to or during the index hospitalization (N=302,481 3.6%)
- Hospitalizations discharged against medical advice (N=29,228 0.3%)
- Hospitalizations with high competing mortality (N=113,161 1.3%)
- Hospitalizations with rehabilitation CCS 254 (N=9,243 0.1%)

**Final Study Cohort (N=8,053,354 94.7%)**

\* Not mutually exclusive

*Based on 2008 MedPAR data

### 2.4.2 Multiple models

Because the risk of readmission varies with patient factors, including age and comorbidities, hospital comparisons using readmission rates need to account for differences in these factors. To adjust for such "case mix" differences we used regression analysis. Rather than assume that effect of risk factors would be homogeneous across all discharge condition categories, we assessed the performance of a single model versus multiple models. Our analyses showed consistently that a single model did not perform as well as multiple models, independently of how we defined the multiple models. The multiple models approach showed better discrimination and predictive ability for readmission risk.

The risk of readmission also varies according to the mix of conditions and procedures at a hospital (service mix). A multiple models approach better captures these variations. Finally, dividing the measure into several models may increase the practical utility of the measure by providing actionable information to hospitals.

### 2.4.3 Models are defined by care team (service line) or clinical coherence

In this step we organized admissions into seven mutually exclusive cohorts: general medicine, surgery/gynecology, cardiorespiratory, cardiovascular, neurology, oncology, and psychiatry. We built a separate model for each cohort.

a) **Rationale:** We expect the hospital component of readmission risk to be in part related to the care provided by a team of doctors, nurses, care coordinators, pharmacists, etc. Conditions typically cared for by the same team of clinicians would therefore be expected to experience similar added (or reduced) levels of readmission risk. Therefore, we grouped discharge condition categories typically cared for by the same group of clinicians into six cohorts: medicine, surgery, cardiovascular, neurology, oncology and psychiatry. Organizing results by care team (service line) in this way will allow hospitals to identify areas of strength and weakness if the results of each component model are reported separately.

b) Approach to individual cohorts:
   i. Surgical/gynecology. This cohort includes admissions likely cared for by surgical or gynecologic teams. We used AHRQ *procedure* categories (rather than AHRQ condition categories) to identify these patients. We reviewed the list of AHRQ CCS procedures and identified those which could typically result in surgical or gynecological teams caring for the patient. Minor procedures that would not have required a patient to be on the surgical service were not included in the list (for example: breast biopsy). Procedures that would generally accompany other, more major, procedures were also not included in the list on the assumption that patients undergoing these procedures would also undergo another procedure on the list (for example, intraoperative cholangiogram). The full

list of procedures assigned to the surgical/gynecology cohort is summarized in **Appendix B**. We will consult surgeons from various specialties to confirm our list of surgical procedures. Any admission during which a procedure from the final list was performed was assigned to the surgical/gynecology cohort.

ii. Cardiorespiratory. This cohort includes several conditions with very high readmission rates – pneumonia, chronic obstructive pulmonary disease, and heart failure – as well as admissions for other condition categories related to these three (asthma, acute bronchitis, pulmonary heart disease, and respiratory failure). We combined these patients into a single cohort because patients with these diseases are often clinically indistinguishable, are typically treated by the same care teams, and are often simultaneously treated for several of these diagnoses.

iii. Cardiovascular. This cohort includes cardiovascular condition categories such as acute myocardial infarction that in large hospitals might be cared for by a separate cardiac or cardiovascular team.

iv. Neurology. This cohort includes neurologic condition categories such as stroke that in large hospitals might be cared for by a separate neurologic team.

v. Oncology. This cohort includes medical admissions for cancer treatment. Patients with cancer diagnoses who undergo eligible surgical procedures (for example, a patient with a colon cancer diagnosis who undergoes a colectomy during hospitalization) are assigned to the surgical cohort.

vi. Psychiatry. This cohort includes admissions with primary psychiatric condition categories.

c) Assignment of admissions to cohorts

i. Admissions are first screened for the presence of an eligible surgical procedure category. Admissions with any of these procedures are assigned to the surgical cohort, regardless of the diagnosis code of the admission.

ii. All remaining admissions are assigned to cohorts on the basis of the discharge condition category. The AHRQ procedure categories for the surgical cohort are shown in **Appendix B**. The AHRQ discharge condition categories for the medical groups are shown in **Appendix C**.

Summary results for the seven cohorts are shown in **Table 3**.

Table 3 – Admissions, readmissions and mortality for the seven cohorts (2008)

| Model Group | Admits | Unplanned Readmits | Unadjusted Unplanned 30-Day Readmit Rate | Deaths Without Readmit | 30-Day Death Rate Without Readmit | Planned Readmits | Unadj. Planned 30-Day Readmit Rate | % Readmits that are Planned |
|---|---|---|---|---|---|---|---|---|
| Cardio-vascular | 843,373 | 129,896 | 15.4% | 22,118 | 2.6% | 25,731 | 3.1% | 17% |
| Cancer | 82,394 | 20,616 | 25.0% | 11,009 | 13.4% | 14,587 | 17.7% | 41% |
| Cardio-respiratory | 1,405,271 | 299,275 | 21.3% | 74,619 | 5.3% | 16,867 | 1.2% | 5% |
| Medicine | 3,009,835 | 549,935 | 18.3% | 150,082 | 5.0% | 59,209 | 2.0% | 10% |
| Neurology | 459,189 | 68,000 | 14.8% | 30,276 | 6.6% | 8,176 | 1.8% | 11% |
| Psychiatry | 89,859 | 14,225 | 15.8% | 3,942 | 4.4% | 829 | 0.9% | 6% |
| Surgical | 2,163,433 | 275,329 | 12.7% | 37,685 | 1.7% | 55,804 | 2.6% | 17% |
| Total | 8,053,354 | 1,357,276 | 16.9% | 329,731 | 4.1% | 181,203 | 2.3% | 12% |

## 2.5 Risk Adjustment

The goal of risk adjustment is to account for differences across hospitals in patient demographic and clinical characteristics that might be related to the outcome but are unrelated to quality of care. Risk adjustment for this measure is complicated by the fact that it includes many different discharge condition categories. We must therefore adjust both for case mix differences (clinical status of the patient, accounted for by adjusting for comorbidities) and service mix differences (the types of conditions/procedures cared for by the hospital, accounted for by adjusting for the discharge condition category). Consistent with NQF guidelines, we did not adjust for socioeconomic status, gender, race, or ethnicity because hospitals should not be held to different standards of care based on the demographics of their patients. We did not adjust for patients' admission source or discharge disposition (e.g. skilled nursing facility) because these factors are associated with structure of the health care system, and may reflect the quality of care delivered by the system.

### 2.5.1 Complications of hospitalization

Complications occurring during hospitalization are not comorbid illnesses, may reflect hospital quality of care, and therefore should **not** be used for risk adjustment. Although adverse events during hospitalization may increase the risk of readmission, including them as covariates in a risk-adjusted model could attenuate the measure's ability to characterize the quality of care delivered by hospitals. CORE has previously reviewed every CMS Condition Category (CMS-CC) and identified those which, if they occur during the index hospitalization, would be considered potential complications rather than comorbidities. For example: fluid, electrolyte or base disorders; sepsis; and acute liver failure are all examples of CCs that could potentially be complications of care (see **Appendix D** for the complete list). For the HWR measure, we applied this pre-established list to all

potential risk variables. CCs on this list were not counted as a risk factor in our analyses if they appeared only on the index admission.

2.5.2 Case mix adjustment: risk variables

We used CMS-CCs, the grouper used in previous CMS risk-standardized outcomes measures, to group ICD-9-CM codes into risk adjustment variables, since four CMS condition-specific claims-based readmission models that use this grouper to define variables for risk adjustment have been validated against models that use chart-abstracted data for risk adjustment. <sup>5,7,8</sup> We decided to use a fixed, common set of variables in all our models for simplicity and ease of data collection and analysis. We describe below the steps for variable selection:

a. We developed a "starter" set of 30 variables drawn from previous readmission measures (AMI, heart failure, pneumonia, hip and knee arthroplasty, and stroke). In many cases, these variables included multiple CMS-CCs each

b. Next we reviewed all the remaining CMS-CCs and determined on a clinical basis whether they were likely to be relevant to an all-condition measure. We selected 11 additional variables to consider. (See **Appendix E** for complete set of starter variables).

c. Using data from the index admission and any admission in the prior 12 months, we ran a standard logistic regression model for every discharge condition category with the full set of candidate risk adjustment variables. We compared odds ratios for different variables across different condition categories (excluding condition categories with fewer than 700 events in order to be able to fit the models). We selected the final set of risk variables based on the following principles:

   i. We excluded risk factors that were statistically significant for very few condition categories, given that they would not contribute much to the overall models.

   ii. We excluded risk factors that behaved in clinically incoherent ways. For example, we dropped risk factors that sometimes increased risk and sometimes decreased risk, when we could not identify a clinical rationale for the differences.

   iii. We excluded risk factors that were predominantly protective when we felt this protective effect was not clinically reasonable but more likely reflected coding factors. For example, hypertension (CC 91), drug/alcohol abuse without dependence (CC 53) and delirium and encephalopathy (CC 48) were all protective for readmission risk although clinically they should increase patients' severity of illness. It is possible these factors appeared falsely protective because they were coded more often in healthier patients

who had few other comorbidities than in sicker patients who had more competing comorbidities to include in the billing form.

iv. Where possible, we grouped together risk factors that were clinically coherent and carried similar risks across condition categories. For example, we combined coronary artery disease (CCs 83-84) with cerebrovascular disease (CCs 98, 99, and 103).

v. We examined risk factors that had been combined in previous CMS publicly reported measures, and in one instance separated them: for cancers, the previous measures generally pool 5 categories of cancers (CCs 8 to12), together. In our analysis, lung cancer (CC 8) and other severe cancers (CC 9) carried higher risks, so we separated them into a distinct risk factor and grouped other major cancers (CC 10), benign cancers (CC 11), and cancers of the urinary and GI tracts (CC 12) together. Consistent with other publicly-reported measures, we also left metastatic cancer/leukemia (CC 7) as a separate risk factor.

The final list containing 74 CMS CCs, grouped into 31 risk variables, is shown in **Appendix F**.

### 2.5.3 Service mix adjustment

For all condition categories with sufficient volume (defined as those with more than 1,000 admissions nationally each year), we include a condition-specific indicator in the model.

**Rationale:** Condition categories differ in their baseline readmission risks and hospitals will differ in their relative distribution of these condition categories within each cohort (service mix). When comparing hospitals it is thus best to compare hospitals with similar service mix. Where this is not feasible, comparison is made more accurate by using an indicator variable for the discharge condition category in addition to risk variables for comorbid conditions.

## 2.6 Statistical Approach to Model Development

We used a full year of admission data from 2008, with 12 months history data (i.e., 2007), to create the condition cohorts and select risk variables. To assess reliability of the model performance, we combined 2007 and 2008 data, randomly split this dataset and ran the model on each split sample. To assess the stability of the model over time we compared estimates based on 2008 data to estimates based on 2009 data.

### 2.6.1 Models for each cohort of conditions

Due to the natural clustering of observations within hospitals, we used hierarchical generalized linear models (HGLMs) to model the log-odds of readmission for each

of the 7 cohorts.<sup>39</sup> Readmission within 30 days was modeled as a function of patient-level demographic and clinical characteristics and a random hospital-level intercept. This model specification accounts for within-hospital correlation of the observed outcomes and models the assumption that underlying differences in quality among the health care facilities being evaluated lead to systematic differences in outcomes. We estimated a separate logistic HGLM model for each cohort of condition categories.

We used the results of each HGLM to calculate the predicted number of readmissions and the expected number of readmissions at each hospital. The predicted number of readmissions in each cohort was calculated, using the corresponding HGLM, as the sum of the predicted probability of readmission for each patient, including the hospital-specific (random) effect. The expected number of readmissions in each cohort for each hospital was similarly calculated as the sum of the predicted probability of readmission for each patient, ignoring the hospital specific (random) effect.

Specifically, for a given cohort, we estimate a hierarchical generalized linear model as follows. Let *Y*<sub>ij</sub> denote the outcome (equal to 1 if patient *i* is readmitted within 30 days, zero otherwise) for a patient in cohort C ⊆ {1.,,.,.7} at hospital *j*; **Z**<sub>ij</sub> denotes a set of risk factors. Let *M* denote the total number of hospitals and *m*<sub>j</sub> the number of index patient stays in hospital *j*. We assume the outcome is related linearly to the covariates via a logit function:

$$\text{logit}(\text{Prob}(Y_i = 1)) = \alpha_j + \boldsymbol{\beta}^* \mathbf{Z}_{ij} \tag{1}$$

$$\alpha_j = \mu + \omega_j \ ; \ \omega_j \sim N(0, \tau^2)$$

where **Z**<sub>ij</sub> = (Z<sub>1</sub>, Z<sub>2</sub>, ... Z<sub>k</sub>) is a set of *k* patient-level covariates. α<sub>j</sub> represents the hospital specific intercept; μ is the adjusted average outcome over all hospitals; and τ<sup>2</sup> is the between hospital variance component. The HGLM for each cohort was estimated using the SAS software system (GLIMMIX procedure).

Then, to calculate the predicted number of admissions pred<sub>Aj</sub> for index admissions in cohort C=1,...,7 at hospital *j*, we used

$$\text{pred}_{Cj} = \sum \text{logit}^{-1}(\alpha_j + \boldsymbol{\beta}^* \mathbf{Z}_{ij}) \tag{2}$$

where the sum is over all *m*<sub>Cj</sub> index admissions in cohort C with index admissions at hospital *j*. To calculate the expected number exp<sub>Aj</sub> we used

$$\exp_{Cj} = \sum \text{logit}^{-1}(\mu + \boldsymbol{\beta}^* \mathbf{Z}_{ij}) \tag{3}$$

Then, as a measure of excess or reduced readmissions among index admissions in cohort C at hospital *j*, we calculated the risk-adjusted readmission ratio R<sub>Cj</sub> as

$$R_{Cj} = \text{pred}_{Cj}/\text{exp}_{Cj} \tag{4}$$

## 2.6.2 Hospital performance reporting

The previous section describes how the risk-standardized readmission ratio for each hospital and each cohort is estimated using a separate HGLM for that cohort. To report a single readmission score, the separate risk-standardized readmission ratios were combined into a single value. We created a single score as follows.

For a given hospital, j, which has patients in some subset of cohorts C ⊆ {1,...,7}, calculate the risk-standardized readmission ratio as described above for each condition cohort for which the hospital discharged patients. If the hospital does not have index admissions in a given cohort c, then m_cj = 0 and we take R_cj = 1. Then, calculate the volume-weighted logarithmic mean:

R_j = exp( (∑ m_cj log(R_cj)) / ∑m_cj ) &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp

a. β<sup>(b)</sup>, the vector of coefficients, and the corresponding variance covariance matrix **V**.

b. μ<sup>(b)</sup>, the average hospital rate; τ<sup>2(b)</sup>, the between hospital variance, and

c. the set of hospital-specific intercepts and corresponding variances; {α<sub>j</sub><sup>(b)</sup> , var[α<sub>j</sub><sup>(b)</sup>] : *j* = 1,2,…,*M*}

3. We generate a hospital random effect by sampling from the distribution of the hospital-specific distribution obtained in Step 2c. We approximate the distribution for each random effect by a normal distribution. Thus, we draw α<sub>j</sub><sup>(b\*)</sup> ~ N(α<sub>j</sub><sup>(b)</sup> , var[α<sub>j</sub><sup>(b)</sup>]) for the unique set of hospitals sampled in Step 1.

4. Within each unique hospital *j* sampled in Step 1, and using index admissions *i*=1,...,m<sub>j</sub> in that hospital, we calculate R\*<sub>j</sub> and then RSRR\*<sub>j</sub> as in equations (5) and (6).

Ninety-five percent interval estimates (or alternative interval estimates) for the hospital-standardized outcome can be computed by identifying the 2.5<sup>th</sup> and 97.5<sup>th</sup> percentiles of randomly half of the B estimates (or the percentiles corresponding to the alternative desired intervals).

## 3. RESULTS

Figure 3 – Distribution of 30-day hospital-wide readmission rates

Figure 3a –Unadjusted rate

![Figure 3a – Histogram showing the distribution of 30-day unadjusted readmission rates (%) on the x-axis (0 to 40) and Number of Hospitals on the y-axis (0 to 800). The distribution is roughly bell-shaped, peaking around 15-16% with approximately 600 hospitals.]

Figure 3b –Risk-standardized rate

![Figure 3b – Histogram showing the distribution of 30-day risk-standardized readmission rates (%) on the x-axis (0 to 40) and Number of Hospitals on the y-axis (0 to 800). The distribution is much narrower and taller than Figure 3a, with a sharp peak around 15-16% reaching approximately 700 hospitals, indicating much less variation after risk standardization.]

Table 4 – Frequency of hospitals in each cohort (Number of hospitals = 4919)

| **Cohort** | **Frequency** | **Percent** |
|---|---|---|
| Medicine | 4860 | 98.8 |
| Surgical | 4272 | 86.85 |
| Cancer | 3784 | 76.93 |
| Cardiovascular | 4633 | 94.19 |
| Cardiorespiratory | 4746 | 96.48 |
| Psychiatry | 4306 | 87.54 |
| Neurology | 4639 | 94.31 |

Table 5 – Number of hospitals based on number of models to which they contribute

| **Total Cohorts** | **Frequency** | **Percent** | **Cumulative Frequency** | **Cumulative Percent** |
|---|---|---|---|---|
| 1 | 64 | 1.3 | 64 | 1.3 |
| 2 | 122 | 2.48 | 186 | 3.78 |
| 3 | 102 | 2.07 | 288 | 5.85 |
| 4 | 157 | 3.19 | 445 | 9.05 |
| 5 | 337 | 6.85 | 782 | 15.9 |
| 6 | 646 | 13.13 | 1428 | 29.03 |
| 7 | 3491 | 70.97 | 4919 | 100 |

Table 6 – C-statistic for each model

| **Cohort** | **C-statistic** |
|---|---|
| Medicine | 0.640 |
| Surgical | 0.676 |
| Cancer | 0.604 |
| Cardiovascular | 0.654 |
| Cardiorespiratory | 0.629 |
| Psych | 0.605 |
| Neurology | 0.614 |

## 4. SUMMARY

In this draft measure methodology report, we present a measure for 30-day readmission following hospitalization for any condition that is based on administrative claims data for FFS Medicare beneficiaries 65 years and older. The measure is comprised of seven hierarchical logistic regression models, each of which includes a clinically coherent group of admissions. The measure includes adjustment for case mix (patient comorbidity) and service mix (types of conditions and procedures cared for by the hospital). The measure excludes planned readmissions. Our approach to model development and risk adjustment is consistent with quality measure methods recommendations for publicly-reported outcomes measures from NQF, CMS, and the American Heart Association scientific statement.

Results to date show that this measure captures 95% of eligible Medicare admissions and 88% of readmissions following those admissions, that most hospitals (71%) have admissions in every cohort, and that c-statistics for performance of each model are consistent with other public report measures. Reliability testing is under way. The measure will also be tested with all-payer data and modified as necessary to apply to the full spectrum of adult hospitalized patients. The measure will be completed in September, at which time we will provide full data on model performance and the final measure methodology.

We now seek public comment on the proposed methods, including inclusion/exclusion criteria, cohort definitions and definition of planned readmissions.

## 5. REFERENCES

1. Jencks SF, Williams MV, Coleman EA. Rehospitalizations among patients in the Medicare fee-for-service program. *N Engl J Med.* Apr 2 2009;360(14):1418-1428.
2. *Why Not the Best? Results from a National Scorecard on U.S. Health System Performance.* Harrisburg, PA: The Commonwealth Fund;2006.
3. Krumholz HM, Brindis RG, Brush JE, et al. Standards for statistical models used for public reporting of health outcomes - An American Heart Association scientific statement from the quality of care and outcomes research interdisciplinary writing group - Cosponsored by the Council on Epidemiology and Prevention and the Stroke Council - Endorsed by the American College of Cardiology Foundation. *Circulation.* Jan 24 2006;113(3):456-462.
4. Krumholz HM, Wang Y, Mattera JA, et al. An administrative claims model suitable for profiling hospital performance based on 30-day mortality rates among patients with an acute myocardial infarction. *Circulation.* Apr 4 2006;113(13):1683-1692.
5. Keenan PS, Normand SL, Lin Z, et al. An administrative claims measure suitable for profiling hospital performance on the basis of 30-day all-cause readmission rates among patients with heart failure. *Circulation.* Sep 2008;1(1):29-37.
6. Bratzler DW, Normand SL, Wang Y, et al. An administrative claims model for profiling hospital 30-day mortality rates for pneumonia patients. *PLoS One.* 2011;6(4):e17401.
7. Krumholz HM, Lin Z, Drye EE, et al. An administrative claims measure suitable for profiling hospital performance based on 30-day all-cause readmission rates among patients with acute myocardial infarction. *Circulation.* Mar 1 2011;4(2):243-252.
8. Lindenauer PK, Normand SL, Drye EE, et al. Development, validation, and results of a measure of 30-day readmission following hospitalization for pneumonia. *Journal of Hospital Medicine.* Mar 2011;6(3):142-150.
9. National Quality Measures Clearinghouse. 2011; http://www.qualitymeasures.ahrq.gov/. Accessed Feb 21, 2011.
10. Jenks SA, Sanz I. Altered B cell receptor signaling in human systemic lupus erythematosus. *Autoimmun Rev.* Jan 2009;8(3):209-213.
11. Frankl SE, Breeling JL, Goldman L. Preventability of emergent hospital readmission. *American Journal of Medicine.* Jun 1991;90(6):667-674.
12. Corrigan JM, Martin JB. Identification of factors associated with hospital readmission and development of a predictive model. *Health Services Research.* Apr 1992;27(1):81-101.
13. Oddone EZ, Weinberger M, Horner M, et al. Classifying general medicine readmissions. Are they preventable? Veterans Affairs Cooperative Studies in Health Services Group on Primary Care and Hospital Readmissions. *Journal of General Internal Medicine.* Oct 1996;11(10):597-607.
14. Ashton CM, Del Junco DJ, Souchek J, Wray NP, Mansyur CL. The association between the quality of inpatient care and early readmission: a meta-analysis of the evidence. *Med Care.* Oct 1997;35(10):1044-1059.
15. Benbassat J, Taragin M. Hospital readmissions as a measure of quality of health care: advantages and limitations. *Archives of Internal Medicine.* Apr 24 2000;160(8):1074-1081.
16. Courtney EDJ, Ankrett S, McCollum PT. 28-Day emergency surgical re-admission rates as a clinical indicator of performance. *Annals of the Royal College of Surgeons of England.* Mar 2003;85(2):75-78.

17. Halfon P, Eggli Y, Pr, et al. Validation of the potentially avoidable hospital readmission rate as a routine indicator of the quality of hospital care. *Medical Care.* Nov 2006;44(11):972-981.
18. Hernandez AF, Greiner MA, Fonarow GC, et al. Relationship between early physician follow-up and 30-day readmission among Medicare beneficiaries hospitalized for heart failure. *JAMA.* May 5 2010;303(17):1716-1722.
19. Medicare Payment Advisory Commission (MedPAC). 2007; http://www.medpac.gov/chapters/Jun07_Ch05.pdf. Accessed Sep 22, 2009.
20. Naylor M, Brooten D, Jones R, Lavizzo-Mourey R, Mezey M, Pauly M. Comprehensive discharge planning for the hospitalized elderly. A randomized clinical trial. *Ann Intern Med.* Jun 15 1994;120(12):999-1006.
21. Naylor MD, Brooten D, Campbell R, et al. Comprehensive discharge planning and home follow-up of hospitalized elders: a randomized clinical trial. *Jama.* Feb 17 1999;281(7):613-620.
22. Krumholz HM, Amatruda J, Smith GL, et al. Randomized trial of an education and support intervention to prevent readmission of patients with heart failure. *Journal of the American College of Cardiology.* Jan 2 2002;39(1):83-89.
23. van Walraven C, Seth R, Austin PC, Laupacis A. Effect of discharge summary availability during post-discharge visits on hospital readmission. *Journal of General Internal Medicine.* Mar 2002;17(3):186-192.
24. Conley RR, Kelly DL, Love RC, McMahon RP. Rehospitalization risk with second-generation and depot antipsychotics. *Annals of Clinical Psychiatry.* Mar 2003;15(1):23-31.
25. Coleman EA, Smith JD, Frank JC, Min S-J, Parry C, Kramer AM. Preparing patients and caregivers to participate in care delivered across settings: the Care Transitions Intervention. *Journal of the American Geriatrics Society.* Nov 2004;52(11):1817-1825.
26. Phillips CO, Wright SM, Kern DE, Singa RM, Shepperd S, Rubin HR. Comprehensive discharge planning with postdischarge support for older patients with congestive heart failure: a meta-analysis. *JAMA.* Mar 17 2004;291(11):1358-1367.
27. Jovicic A, Holroyd-Leduc JM, Straus SE. Effects of self-management intervention on health outcomes of patients with heart failure: a systematic review of randomized controlled trials. *BMC Cardiovasc Disord.* 2006;6:43.
28. Garasen H, Windspoll R, Johnsen R. Intermediate care at a community hospital as an alternative to prolonged general hospital care for elderly patients: a randomised controlled trial. *BMC Public Health.* 2007;7:68.
29. Mistiaen P, Francke AL, Poot E. Interventions aimed at reducing problems in adult patients discharged from hospital to home: a systematic meta-review. *BMC Health Services Research.* 2007;7:47.
30. Courtney M, Edwards H, Chang A, Parker A, Finlayson K, Hamilton K. Fewer emergency readmissions and better quality of life for older adults at risk of hospital readmission: a randomized controlled trial to determine the effectiveness of a 24-week exercise and telephone follow-up program. *Journal of the American Geriatrics Society.* Mar 2009;57(3):395-402.
31. Jack BW, Chetty VK, Anthony D, et al. A reengineered hospital discharge program to decrease rehospitalization: a randomized trial. *Ann Intern Med.* Feb 3 2009;150(3):178-187.
32. Koehler BE, Richter KM, Youngblood L, et al. Reduction of 30-day postdischarge hospital readmission or emergency department (ED) visit rates in high-risk elderly medical patients through delivery of a targeted care bundle. *Journal of Hospital Medicine.* Apr 2009;4(4):211-218.

33. Weiss M, Yakusheva O, Bobay K. Nurse and patient perceptions of discharge readiness in relation to postdischarge utilization. *Medical Care.* May 2010;48(5):482-486.
34. Stauffer BD, Fullerton C, Fleming N, et al. Effectiveness and cost of a transitional care program for heart failure: a prospective study with concurrent controls. *Archives of Internal Medicine.* Jul 25 2011;171(14):1238-1243.
35. Voss R, Gardner R, Baier R, Butterfield K, Lehrman S, Gravenstein S. The care transitions intervention: translating from efficacy to effectiveness. *Archives of Internal Medicine.* Jul 25 2011;171(14):1232-1237.
36. (CFMC) CFfMC. Care Transitions QIOSC. 2010; http://www.cfmc.org/caretransitions/, 2011.
37. National Quality Forum. National voluntary consensus standards for patient outcomes, first report for phases 1 and 2: A consensus report http://www.nysna.org/images/pdfs/practice/nqf_ana_outcomes_draft10.pdf. Accessed August 19, 2010.
38. Coleman EA, Smith JD, Frank JC, Min SJ, Parry C, Kramer AM. Preparing patients and caregivers to participate in care delivered across settings: the Care Transitions Intervention. *J Am Geriatr Soc.* Nov 2004;52(11):1817-1825.
39. Normand S-L, Glickman ME, Gatsonis CA. Statistical Methods for Profiling Providers of Medical Care: Issues and Applications. *Journal of the American Statistical Association.* September 1997;92(439):11.

## 6. APPENDIX – TABLES

### Appendix A – Top 10 primary discharge diagnoses for planned procedures

| Proc CCS | Procedure CCS | CCS Diag | CCS- Diagnosis Description | 30-Day Readmits | Total Admits | Obs 30-Day Rate |
|----------|---------------|----------|----------------------------|-----------------|--------------|-----------------|
| **2** | **Insertion; replacement; or removal of extracranial ventricular shunt** | | **Total** | **1,203** | **6,697** | **18.0%** |
| | | 81 | Other hereditary and degenerative nervous system conditions | 629 | 4,205 | 15.0% |
| | | 237 | Complication of device; implant or graft | 198 | 984 | 20.1% |
| | | 109 | Acute cerebrovascular disease | 173 | 734 | 23.6% |
| | | 233 | Intracranial injury | 45 | 167 | 26.9% |
| | | 42 | Secondary malignancies | 25 | 75 | 33.3% |
| | | 47 | Other and unspecified benign neoplasm | 21 | 71 | 29.6% |
| | | 238 | Complications of surgical procedures or medical care | 18 | 59 | 30.5% |
| | | 95 | Other nervous system disorders | 12 | 77 | 15.6% |
| | | 35 | Cancer of brain and nervous system | 9 | 43 | 20.9% |
| | | 2 | Septicemia (except in labor) | 8 | 24 | 33.3% |
| **3** | **Laminectomy; excision intervertebral disc** | | **Total** | **8,904** | **103,340** | **8.6%** |
| | | 205 | Spondylosis; intervertebral disc disorders; other back problems | 6,535 | 85,978 | 7.6% |
| | | 209 | Other acquired deformities | 462 | 5,354 | 8.6% |
| | | 217 | Other congenital anomalies | 130 | 1,524 | 8.5% |
| | | 237 | Complication of device; implant or graft | 186 | 1,308 | 14.2% |
| | | 238 | Complications of surgical procedures or medical care | 228 | 1,157 | 19.7% |
| | | 231 | Other fractures | 129 | 768 | 16.8% |
| | | 212 | Other bone disease and musculoskeletal deformities | 109 | 766 | 14.2% |
| | | 207 | Pathological fracture | 125 | 647 | 19.3% |
| | | 81 | Other hereditary and degenerative nervous system conditions | 149 | 634 | 23.5% |
| | | 42 | Secondary malignancies | 131 | 463 | 28.3% |
| **10** | **Thyroidectomy; partial or complete** | | **Total** | **802** | **11,084** | **7.2%** |
| | | 48 | Thyroid disorders | 241 | 5,121 | 4.7% |
| | | 36 | Cancer of thyroid | 292 | 2,848 | 10.3% |
| | | 47 | Other and unspecified benign neoplasm | 74 | 1,739 | 4.3% |
| | | 51 | Other endocrine disorders | 31 | 354 | 8.8% |
| | | 11 | Cancer of head and neck | 25 | 123 | 20.3% |
| | | 42 | Secondary malignancies | 15 | 82 | 18.3% |
| | | 38 | Non-Hodgkin's lymphoma | 14 | 66 | 21.2% |
| | | 131 | Respiratory failure; insufficiency; arrest (adult) | 10 | 56 | 17.9% |
| | | 2 | Septicemia (except in labor) | 7 | 43 | 16.3% |
| | | 101 | Coronary atherosclerosis and other heart disease | 8 | 32 | 25.0% |
| **36** | **Lobectomy or pneumonectomy** | | **Total** | **3,883** | **28,904** | **13.4%** |
| | | 19 | Cancer of bronchus; lung | 2,679 | 19,827 | 13.5% |
| | | 133 | Other lower respiratory disease | 274 | 2,793 | 9.8% |
| | | 42 | Secondary malignancies | 216 | 2,075 | 10.4% |
| | | 130 | Pleurisy; pneumothorax; pulmonary collapse | 154 | 1,019 | 15.1% |
| | | 122 | Pneumonia (except that caused by tuberculosis or sexually transmitted disease) | 94 | 545 | 17.2% |
| | | 127 | Chronic obstructive pulmonary disease and bronchiectasis | 64 | 362 | 17.7% |
| | | 101 | Coronary atherosclerosis and other heart disease | 36 | 172 | 20.9% |

| Proc CCS | Procedure CCS | CCS Diag | CCS- Diagnosis Description | 30-Day Readmits | Total Admits | Obs 30-Day Rate |
|----------|---------------|----------|----------------------------|-----------------|--------------|----------------|
| | | 238 | Complications of surgical procedures or medical care | 30 | 172 | 17.4% |
| | | 38 | Non-Hodgkin`s lymphoma | 21 | 148 | 14.2% |
| | | 4 | Mycoses | 20 | 131 | 15.3% |
| **43** | **Heart valve procedures** | | **Total** | **9,348** | **41,913** | **22.3%** |
| | | 96 | Heart valve disorders | 6,610 | 30,925 | 21.4% |
| | | 101 | Coronary atherosclerosis and other heart disease | 1,018 | 4,257 | 23.9% |
| | | 100 | Acute myocardial infarction | 449 | 1,672 | 26.9% |
| | | 108 | Congestive heart failure; nonhypertensive | 375 | 1,313 | 28.6% |
| | | 237 | Complication of device; implant or graft | 305 | 1,260 | 24.2% |
| | | 115 | Aortic; peripheral; and visceral artery aneurysms | 197 | 813 | 24.2% |
| | | 97 | Peri-; endo-; and myocarditis; cardiomyopathy (except that caused by tuberculosis or sexually transm | 120 | 460 | 26.1% |
| | | 213 | Cardiac and circulatory congenital anomalies | 60 | 394 | 15.2% |
| | | 106 | Cardiac dysrhythmias | 66 | 246 | 26.8% |
| | | 99 | Hypertension with complications and secondary hypertension | 22 | 64 | 34.4% |
| **44** | **Coronary artery bypass graft (CABG)** | | **Total** | **17,449** | **93,852** | **18.6%** |
| | | 101 | Coronary atherosclerosis and other heart disease | 9,754 | 58,416 | 16.7% |
| | | 100 | Acute myocardial infarction | 3,639 | 17,656 | 20.6% |
| | | 96 | Heart valve disorders | 2,655 | 11,993 | 22.1% |
| | | 237 | Complication of device; implant or graft | 334 | 1,717 | 19.5% |
| | | 108 | Congestive heart failure; nonhypertensive | 379 | 1,247 | 30.4% |
| | | 106 | Cardiac dysrhythmias | 126 | 505 | 25.0% |
| | | 115 | Aortic; peripheral; and visceral artery aneurysms | 121 | 469 | 25.8% |
| | | 97 | Peri-; endo-; and myocarditis; cardiomyopathy (except that caused by tuberculosis or sexually transm | 49 | 176 | 27.8% |
| | | 238 | Complications of surgical procedures or medical care | 32 | 131 | 24.4% |
| | | 114 | Peripheral and visceral atherosclerosis | 27 | 80 | 33.8% |
| **45** | **Percutaneous transluminal coronary angioplasty (PTCA)** | | **Total** | **36,600** | **239,412** | **15.3%** |
| | | 101 | Coronary atherosclerosis and other heart disease | 17,349 | 133,645 | 13.0% |
| | | 100 | Acute myocardial infarction | 12,841 | 72,027 | 17.8% |
| | | 237 | Complication of device; implant or graft | 2,382 | 17,465 | 13.6% |
| | | 108 | Congestive heart failure; nonhypertensive | 1,138 | 4,091 | 27.8% |
| | | 106 | Cardiac dysrhythmias | 568 | 2,775 | 20.5% |
| | | 131 | Respiratory failure; insufficiency; arrest (adult) | 216 | 764 | 28.3% |
| | | 2 | Septicemia (except in labor) | 140 | 528 | 26.5% |
| | | 127 | Chronic obstructive pulmonary disease and bronchiectasis | 148 | 469 | 31.6% |
| | | 122 | Pneumonia (except that caused by tuberculosis or sexually transmitted disease) | 131 | 468 | 28.0% |
| | | 99 | Hypertension with complications and secondary hypertension | 110 | 468 | 23.5% |
| **48** | **Insertion; revision; replacement; removal of cardiac pacemaker or cardioverter/** | | **Total** | **27,971** | **185,737** | **15.1%** |
| | | 106 | Cardiac dysrhythmias | 10,102 | 74,614 | 13.5% |
| | | 105 | Conduction disorders | 3,663 | 31,993 | 11.4% |
| | | 108 | Congestive heart failure; nonhypertensive | 3,957 | 21,542 | 18.4% |
| | | 237 | Complication of device; implant or graft | 2,012 | 14,114 | 14.3% |
| | | 101 | Coronary atherosclerosis and other heart disease | 1,585 | 11,237 | 14.1% |
| | | 100 | Acute myocardial infarction | 1,270 | 5,389 | 23.6% |

| Proc CCS | Procedure CCS | CCS Diag | CCS- Diagnosis Description | 30-Day Readmits | Total Admits | Obs 30-Day Rate |
|----------|---------------|----------|----------------------------|-----------------|--------------|----------------|
| | defibrillator | 97 | Peri-; endo-; and myocarditis; cardiomyopathy (except that caused by tuberculosis or sexually transm | 381 | 2,954 | 12.9% |
| | | 96 | Heart valve disorders | 609 | 2,624 | 23.2% |
| | | 245 | Syncope | 287 | 2,174 | 13.2% |
| | | 109 | Acute cerebrovascular disease | 265 | 1,466 | 18.1% |
| **51** | **Endarterectomy; vessel of head and neck** | | **Total** | **6,017** | **59,461** | **10.1%** |
| | | 110 | Occlusion or stenosis of precerebral arteries | 4,940 | 53,549 | 9.2% |
| | | 109 | Acute cerebrovascular disease | 326 | 2,471 | 13.2% |
| | | 101 | Coronary atherosclerosis and other heart disease | 257 | 1,212 | 21.2% |
| | | 100 | Acute myocardial infarction | 65 | 276 | 23.6% |
| | | 112 | Transient cerebral ischemia | 30 | 201 | 14.9% |
| | | 96 | Heart valve disorders | 54 | 185 | 29.2% |
| | | 106 | Cardiac dysrhythmias | 32 | 148 | 21.6% |
| | | 114 | Peripheral and visceral atherosclerosis | 25 | 111 | 22.5% |
| | | 237 | Complication of device; implant or graft | 15 | 109 | 13.8% |
| | | 108 | Congestive heart failure; nonhypertensive | 38 | 90 | 42.2% |
| **52** | **Aortic resection; replacement or anastomosis** | | **Total** | **3,705** | **27,182** | **13.6%** |
| | | 115 | Aortic; peripheral; and visceral artery aneurysms | 3,345 | 25,354 | 13.2% |
| | | 237 | Complication of device; implant or graft | 137 | 893 | 15.3% |
| | | 96 | Heart valve disorders | 36 | 154 | 23.4% |
| | | 114 | Peripheral and visceral atherosclerosis | 20 | 103 | 19.4% |
| | | 101 | Coronary atherosclerosis and other heart disease | 23 | 88 | 26.1% |
| | | 238 | Complications of surgical procedures or medical care | 15 | 44 | 34.1% |
| | | 100 | Acute myocardial infarction | 10 | 39 | 25.6% |
| | | 108 | Congestive heart failure; nonhypertensive | 10 | 32 | 31.3% |
| | | 106 | Cardiac dysrhythmias | 6 | 25 | 24.0% |
| | | 2 | Septicemia (except in labor) | 6 | 23 | 26.1% |
| **55** | **Peripheral vascular bypass** | | **Total** | **6,468** | **29,739** | **21.7%** |
| | | 114 | Peripheral and visceral atherosclerosis | 2,735 | 15,179 | 18.0% |
| | | 115 | Aortic; peripheral; and visceral artery aneurysms | 556 | 3,117 | 17.8% |
| | | 248 | Gangrene | 1,042 | 3,017 | 34.5% |
| | | 237 | Complication of device; implant or graft | 631 | 2,647 | 23.8% |
| | | 116 | Aortic and peripheral arterial embolism or thrombosis | 415 | 2,144 | 19.4% |
| | | 50 | Diabetes mellitus with complications | 510 | 1,614 | 31.6% |
| | | 117 | Other circulatory disease | 95 | 425 | 22.4% |
| | | 238 | Complications of surgical procedures or medical care | 81 | 314 | 25.8% |
| | | 2 | Septicemia (except in labor) | 42 | 125 | 33.6% |
| | | 201 | Infective arthritis and osteomyelitis (except that caused by tuberculosis or sexually transmitted di | 28 | 86 | 32.6% |
| **60** | **Embolectomy and endarterectomy of lower limbs** | | **Total** | **4,229** | **18,918** | **22.4%** |
| | | 114 | Peripheral and visceral atherosclerosis | 1,447 | 7,997 | 18.1% |
| | | 116 | Aortic and peripheral arterial embolism or thrombosis | 796 | 3,349 | 23.8% |
| | | 237 | Complication of device; implant or graft | 448 | 1,854 | 24.2% |
| | | 115 | Aortic; peripheral; and visceral artery aneurysms | 333 | 1,848 | 18.0% |
| | | 248 | Gangrene | 422 | 1,182 | 35.7% |
| | | 50 | Diabetes mellitus with complications | 167 | 522 | 32.0% |
| | | 238 | Complications of surgical procedures or medical care | 82 | 405 | 20.2% |
| | | 117 | Other circulatory disease | 42 | 200 | 21.0% |
| | | 101 | Coronary atherosclerosis and other heart disease | 53 | 198 | 26.8% |

| Proc CCS | Procedure CCS | CCS Diag | CCS- Diagnosis Description | 30-Day Readmits | Total Admits | Obs 30-Day Rate |
|----------|---------------|----------|----------------------------|-----------------|--------------|----------------|
| | | 100 | Acute myocardial infarction | 54 | 182 | 29.7% |
| **64** | **Bone marrow transplant** | | **Total** | **268** | **1,102** | **24.3%** |
| | | 40 | Multiple myeloma | 83 | 466 | 17.8% |
| | | 38 | Non-Hodgkin`s lymphoma | 85 | 316 | 26.9% |
| | | 39 | Leukemias | 58 | 168 | 34.5% |
| | | 45 | Maintenance chemotherapy; radiotherapy | 12 | 37 | 32.4% |
| | | 37 | Hodgkin`s disease | 4 | 28 | 14.3% |
| | | 44 | Neoplasms of unspecified nature or uncertain behavior | 13 | 25 | 52.0% |
| | | 58 | Other nutritional; endocrine; and metabolic disorders | 4 | 18 | 22.2% |
| | | 237 | Complication of device; implant or graft | 2 | 7 | 28.6% |
| | | 250 | Nausea and vomiting | 2 | 2 | 100.0% |
| | | 106 | Cardiac dysrhythmias | 1 | 2 | 50.0% |
| **74** | **Gastrectomy; partial and total** | | **Total** | **1,294** | **6,355** | **20.4%** |
| | | 13 | Cancer of stomach | 590 | 2,925 | 20.2% |
| | | 12 | Cancer of esophagus | 93 | 430 | 21.6% |
| | | 139 | Gastroduodenal ulcer (except hemorrhage) | 91 | 413 | 22.0% |
| | | 153 | Gastrointestinal hemorrhage | 89 | 338 | 26.3% |
| | | 44 | Neoplasms of unspecified nature or uncertain behavior | 25 | 337 | 7.4% |
| | | 141 | Other disorders of stomach and duodenum | 62 | 296 | 20.9% |
| | | 47 | Other and unspecified benign neoplasm | 42 | 280 | 15.0% |
| | | 238 | Complications of surgical procedures or medical care | 37 | 142 | 26.1% |
| | | 17 | Cancer of pancreas | 34 | 135 | 25.2% |
| | | 143 | Abdominal hernia | 24 | 112 | 21.4% |
| **75** | **Small bowel resection** | | **Total** | **4,697** | **24,425** | **19.2%** |
| | | 145 | Intestinal obstruction without hernia | 1,212 | 6,861 | 17.7% |
| | | 143 | Abdominal hernia | 635 | 3,722 | 17.1% |
| | | 155 | Other gastrointestinal disorders | 404 | 2,074 | 19.5% |
| | | 114 | Peripheral and visceral atherosclerosis | 327 | 1,459 | 22.4% |
| | | 14 | Cancer of colon | 228 | 1,195 | 19.1% |
| | | 42 | Secondary malignancies | 256 | 1,040 | 24.6% |
| | | 146 | Diverticulosis and diverticulitis | 161 | 1,038 | 15.5% |
| | | 238 | Complications of surgical procedures or medical care | 187 | 829 | 22.6% |
| | | 2 | Septicemia (except in labor) | 178 | 635 | 28.0% |
| | | 237 | Complication of device; implant or graft | 141 | 603 | 23.4% |
| **78** | **Colorectal resection** | | **Total** | **16,436** | **102,473** | **16.0%** |
| | | 14 | Cancer of colon | 5,035 | 36,222 | 13.9% |
| | | 146 | Diverticulosis and diverticulitis | 2,230 | 15,600 | 14.3% |
| | | 47 | Other and unspecified benign neoplasm | 1,075 | 10,139 | 10.6% |
| | | 15 | Cancer of rectum and anus | 1,691 | 9,298 | 18.2% |
| | | 145 | Intestinal obstruction without hernia | 943 | 4,634 | 20.4% |
| | | 155 | Other gastrointestinal disorders | 862 | 4,629 | 18.6% |
| | | 147 | Anal and rectal conditions | 313 | 2,374 | 13.2% |
| | | 114 | Peripheral and visceral atherosclerosis | 570 | 2,249 | 25.3% |
| | | 2 | Septicemia (except in labor) | 500 | 1,912 | 26.2% |
| | | 238 | Complications of surgical procedures or medical care | 326 | 1,677 | 19.4% |
| **80** | **Appendectomy** | | **Total** | **2,894** | **24,117** | **12.0%** |
| | | 142 | Appendicitis and other appendiceal conditions | 1,285 | 14,041 | 9.2% |
| | | 145 | Intestinal obstruction without hernia | 155 | 1,145 | 13.5% |

| Proc CCS | Procedure CCS | CCS Diag | CCS- Diagnosis Description | 30-Day Readmits | Total Admits | Obs 30-Day Rate |
|---|---|---|---|---|---|---|
| | | 14 | Cancer of colon | 159 | 1,113 | 14.3% |
| | | 146 | Diverticulosis and diverticulitis | 133 | 1,016 | 13.1% |
| | | 27 | Cancer of ovary | 122 | 694 | 17.6% |
| | | 47 | Other and unspecified benign neoplasm | 69 | 667 | 10.3% |
| | | 155 | Other gastrointestinal disorders | 96 | 592 | 16.2% |
| | | 2 | Septicemia (except in labor) | 104 | 520 | 20.0% |
| | | 32 | Cancer of bladder | 136 | 511 | 26.6% |
| | | 15 | Cancer of rectum and anus | 83 | 484 | 17.1% |
| **84** | **Cholecystectomy and common duct exploration** | | **Total** | **12,476** | **95,087** | **13.1%** |
| | | 149 | Biliary tract disease | 7,825 | 67,494 | 11.6% |
| | | 152 | Pancreatic disorders (not diabetes) | 861 | 7,090 | 12.1% |
| | | 2 | Septicemia (except in labor) | 633 | 3,590 | 17.6% |
| | | 14 | Cancer of colon | 259 | 1,876 | 13.8% |
| | | 17 | Cancer of pancreas | 326 | 1,436 | 22.7% |
| | | 18 | Cancer of other GI organs; peritoneum | 252 | 1,124 | 22.4% |
| | | 42 | Secondary malignancies | 140 | 915 | 15.3% |
| | | 145 | Intestinal obstruction without hernia | 134 | 843 | 15.9% |
| | | 143 | Abdominal hernia | 122 | 762 | 16.0% |
| | | 47 | Other and unspecified benign neoplasm | 133 | 722 | 18.4% |
| **85** | **Inguinal and femoral hernia repair** | | **Total** | **2,193** | **17,933** | **12.2%** |
| | | 143 | Abdominal hernia | 1,588 | 13,922 | 11.4% |
| | | 238 | Complications of surgical procedures or medical care | 53 | 399 | 13.3% |
| | | 29 | Cancer of prostate | 21 | 388 | 5.4% |
| | | 145 | Intestinal obstruction without hernia | 57 | 290 | 19.7% |
| | | 14 | Cancer of colon | 23 | 183 | 12.6% |
| | | 149 | Biliary tract disease | 22 | 174 | 12.6% |
| | | 2 | Septicemia (except in labor) | 31 | 124 | 25.0% |
| | | 237 | Complication of device; implant or graft | 20 | 100 | 20.0% |
| | | 114 | Peripheral and visceral atherosclerosis | 21 | 91 | 23.1% |
| | | 32 | Cancer of bladder | 26 | 84 | 31.0% |
| **103** | **Nephrotomy and nephrostomy** | | **Total** | **3,089** | **11,493** | **26.9%** |
| | | 160 | Calculus of urinary tract | 491 | 2,989 | 16.4% |
| | | 2 | Septicemia (except in labor) | 421 | 1,474 | 28.6% |
| | | 157 | Acute and unspecified renal failure | 438 | 1,363 | 32.1% |
| | | 161 | Other diseases of kidney and ureters | 270 | 1,068 | 25.3% |
| | | 32 | Cancer of bladder | 301 | 900 | 33.4% |
| | | 159 | Urinary tract infections | 168 | 545 | 30.8% |
| | | 237 | Complication of device; implant or graft | 127 | 412 | 30.8% |
| | | 42 | Secondary malignancies | 118 | 404 | 29.2% |
| | | 238 | Complications of surgical procedures or medical care | 108 | 380 | 28.4% |
| | | 29 | Cancer of prostate | 60 | 216 | 27.8% |
| **104** | **Nephrectomy; partial or complete** | | **Total** | **1,766** | **16,132** | **10.9%** |
| | | 33 | Cancer of kidney and renal pelvis | 1,130 | 11,079 | 10.2% |
| | | 161 | Other diseases of kidney and ureters | 98 | 1,097 | 8.9% |
| | | 47 | Other and unspecified benign neoplasm | 77 | 1,060 | 7.3% |
| | | 34 | Cancer of other urinary organs | 91 | 826 | 11.0% |
| | | 32 | Cancer of bladder | 45 | 208 | 21.6% |
| | | 159 | Urinary tract infections | 34 | 179 | 19.0% |
| | | 42 | Secondary malignancies | 22 | 158 | 13.9% |
| | | 215 | Genitourinary congenital anomalies | 19 | 136 | 14.0% |
| | | 99 | Hypertension with complications and secondary hypertension | 24 | 127 | 18.9% |
| | | 237 | Complication of device; implant or graft | 26 | 88 | 29.5% |
| **105** | **Kidney** | | **Total** | **551** | **1,811** | **30.4%** |

| Proc CCS | Procedure CCS | CCS Diag | CCS- Diagnosis Description | 30-Day Readmits | Total Admits | Obs 30-Day Rate |
|----------|---------------|----------|----------------------------|-----------------|--------------|----------------|
| | transplant | 99 | Hypertension with complications and secondary hypertension | 316 | 1,038 | 30.4% |
| | | 50 | Diabetes mellitus with complications | 144 | 445 | 32.4% |
| | | 158 | Chronic renal failure | 58 | 200 | 29.0% |
| | | 237 | Complication of device; implant or graft | 14 | 49 | 28.6% |
| | | 215 | Genitourinary congenital anomalies | 7 | 23 | 30.4% |
| | | 156 | Nephritis; nephrosis; renal sclerosis | 6 | 19 | 31.6% |
| | | 151 | Other liver diseases | 2 | 8 | 25.0% |
| | | 115 | Aortic; peripheral; and visceral artery aneurysms | 1 | 6 | 16.7% |
| | | 117 | Other circulatory disease | 1 | 4 | 25.0% |
| | | 157 | Acute and unspecified renal failure | 1 | 3 | 33.3% |
| **113** | **Transurethral resection of prostate (TURP)** | | **Total** | **4,237** | **41,835** | **10.1%** |
| | | 164 | Hyperplasia of prostate | 2,319 | 28,747 | 8.1% |
| | | 29 | Cancer of prostate | 440 | 4,073 | 10.8% |
| | | 32 | Cancer of bladder | 175 | 1,362 | 12.8% |
| | | 162 | Other diseases of bladder and urethra | 93 | 1,065 | 8.7% |
| | | 160 | Calculus of urinary tract | 69 | 846 | 8.2% |
| | | 163 | Genitourinary symptoms and ill-defined conditions | 131 | 797 | 16.4% |
| | | 159 | Urinary tract infections | 127 | 583 | 21.8% |
| | | 238 | Complications of surgical procedures or medical care | 72 | 548 | 13.1% |
| | | 157 | Acute and unspecified renal failure | 110 | 507 | 21.7% |
| | | 2 | Septicemia (except in labor) | 95 | 362 | 26.2% |
| **114** | **Open prostatectomy** | | **Total** | **1,010** | **20,783** | **4.9%** |
| | | 29 | Cancer of prostate | 771 | 18,482 | 4.2% |
| | | 164 | Hyperplasia of prostate | 137 | 1,763 | 7.8% |
| | | 32 | Cancer of bladder | 35 | 165 | 21.2% |
| | | 162 | Other diseases of bladder and urethra | 4 | 36 | 11.1% |
| | | 238 | Complications of surgical procedures or medical care | 5 | 31 | 16.1% |
| | | 160 | Calculus of urinary tract | 5 | 29 | 17.2% |
| | | 165 | Inflammatory conditions of male genital organs | 6 | 23 | 26.1% |
| | | 163 | Genitourinary symptoms and ill-defined conditions | 4 | 18 | 22.2% |
| | | 166 | Other male genital disorders | 4 | 18 | 22.2% |
| | | 15 | Cancer of rectum and anus | 4 | 15 | 26.7% |
| **119** | **Oophorectomy; unilateral and bilateral** | | **Total** | **3,530** | **35,902** | **9.8%** |
| | | 25 | Cancer of uterus | 940 | 9,228 | 10.2% |
| | | 170 | Prolapse of female genital organs | 218 | 5,648 | 3.9% |
| | | 47 | Other and unspecified benign neoplasm | 302 | 4,165 | 7.3% |
| | | 27 | Cancer of ovary | 697 | 3,766 | 18.5% |
| | | 175 | Other female genital disorders | 117 | 2,009 | 5.8% |
| | | 172 | Ovarian cyst | 99 | 1,574 | 6.3% |
| | | 14 | Cancer of colon | 131 | 976 | 13.4% |
| | | 146 | Diverticulosis and diverticulitis | 92 | 659 | 14.0% |
| | | 18 | Cancer of other GI organs; peritoneum | 106 | 495 | 21.4% |
| | | 42 | Secondary malignancies | 102 | 491 | 20.8% |
| **124** | **Hysterectomy; abdominal and vaginal** | | **Total** | **2,732** | **35,432** | **7.7%** |
| | | 170 | Prolapse of female genital organs | 430 | 12,633 | 3.4% |
| | | 25 | Cancer of uterus | 965 | 9,479 | 10.2% |
| | | 27 | Cancer of ovary | 427 | 2,429 | 17.6% |
| | | 47 | Other and unspecified benign neoplasm | 137 | 2,008 | 6.8% |
| | | 175 | Other female genital disorders | 97 | 1,960 | 4.9% |
| | | 46 | Benign neoplasm of uterus | 86 | 1,660 | 5.2% |
| | | 26 | Cancer of cervix | 61 | 699 | 8.7% |
| | | 18 | Cancer of other GI organs; peritoneum | 67 | 319 | 21.0% |

| Proc CCS | Procedure CCS | CCS Diag | CCS- Diagnosis Description | 30-Day Readmits | Total Admits | Obs 30-Day Rate |
|----------|---------------|-----------|----------------------------|-----------------|--------------|----------------|
| | | 42 | Secondary malignancies | 52 | 274 | 19.0% |
| | | 32 | Cancer of bladder | 56 | 195 | 28.7% |
| **145** | **Treatment; fracture or dislocation of radius and ulna** | | **Total** | **2,048** | **18,197** | **11.3%** |
| | | 229 | Fracture of upper limb | 1,146 | 12,208 | 9.4% |
| | | 226 | Fracture of neck of femur (hip) | 369 | 2,325 | 15.9% |
| | | 230 | Fracture of lower limb | 51 | 435 | 11.7% |
| | | 231 | Other fractures | 49 | 373 | 13.1% |
| | | 233 | Intracranial injury | 68 | 367 | 18.5% |
| | | 237 | Complication of device; implant or graft | 43 | 326 | 13.2% |
| | | 212 | Other bone disease and musculoskeletal deformities | 19 | 206 | 9.2% |
| | | 245 | Syncope | 29 | 191 | 15.2% |
| | | 106 | Cardiac dysrhythmias | 22 | 119 | 18.5% |
| | | 238 | Complications of surgical procedures or medical care | 19 | 98 | 19.4% |
| **147** | **Treatment; fracture or dislocation of lower extremity (other than hip or femur)** | | **Total** | **4,361** | **34,131** | **12.8%** |
| | | 230 | Fracture of lower limb | 3,223 | 26,133 | 12.3% |
| | | 237 | Complication of device; implant or graft | 345 | 2,302 | 15.0% |
| | | 67 | Osteoarthritis | 67 | 953 | 7.0% |
| | | 212 | Other bone disease and musculoskeletal deformities | 76 | 766 | 9.9% |
| | | 238 | Complications of surgical procedures or medical care | 70 | 426 | 16.4% |
| | | 225 | Joint disorders and dislocations; trauma-related | 41 | 351 | 11.7% |
| | | 229 | Fracture of upper limb | 32 | 279 | 11.5% |
| | | 207 | Pathological fracture | 50 | 277 | 18.1% |
| | | 226 | Fracture of neck of femur (hip) | 30 | 231 | 13.0% |
| | | 233 | Intracranial injury | 26 | 136 | 19.1% |
| **148** | **Other fracture and dislocation procedure** | | **Total** | **4,064** | **31,991** | **12.7%** |
| | | 229 | Fracture of upper limb | 1,421 | 12,285 | 11.6% |
| | | 205 | Spondylosis; intervertebral disc disorders; other back problems | 448 | 4,687 | 9.6% |
| | | 237 | Complication of device; implant or graft | 503 | 3,957 | 12.7% |
| | | 231 | Other fractures | 194 | 1,252 | 15.5% |
| | | 225 | Joint disorders and dislocations; trauma-related | 152 | 1,237 | 12.3% |
| | | 212 | Other bone disease and musculoskeletal deformities | 127 | 1,222 | 10.4% |
| | | 226 | Fracture of neck of femur (hip) | 207 | 1,154 | 17.9% |
| | | 207 | Pathological fracture | 166 | 809 | 20.5% |
| | | 230 | Fracture of lower limb | 91 | 470 | 19.4% |
| | | 238 | Complications of surgical procedures or medical care | 77 | 450 | 17.1% |
| **152** | **Arthroplasty knee** | | **Total** | **15,063** | **250,228** | **6.0%** |
| | | 203 | Osteoarthritis | 12,785 | 226,600 | 5.6% |
| | | 237 | Complication of device; implant or graft | 1,588 | 16,662 | 9.5% |
| | | 204 | Other non-traumatic joint disorders | 94 | 1,749 | 5.4% |
| | | 209 | Other acquired deformities | 141 | 1,171 | 12.0% |
| | | 202 | Rheumatoid arthritis and related disease | 71 | 982 | 7.2% |
| | | 225 | Joint disorders and dislocations; trauma-related | 54 | 666 | 8.1% |
| | | 212 | Other bone disease and musculoskeletal deformities | 42 | 603 | 7.0% |
| | | 230 | Fracture of lower limb | 91 | 534 | 17.0% |
| | | 238 | Complications of surgical procedures or medical care | 37 | 230 | 16.1% |

| Proc CCS | Procedure CCS | CCS Diag | CCS- Diagnosis Description | 30-Day Readmits | Total Admits | Obs 30-Day Rate |
|----------|---------------|----------|----------------------------|-----------------|--------------|----------------|
| | | 201 | Infective arthritis and osteomyelitis (except that caused by tuberculosis or sexually transmitted di | 31 | 180 | 17.2% |
| **153** | **Hip replacement; total and partial** | | **Total** | **20,643** | **184,630** | **11.2%** |
| | | 203 | Osteoarthritis | 5,349 | 86,059 | 6.2% |
| | | 226 | Fracture of neck of femur (hip) | 10,996 | 68,890 | 16.0% |
| | | 237 | Complication of device; implant or graft | 2,601 | 18,074 | 14.4% |
| | | 212 | Other bone disease and musculoskeletal deformities | 568 | 5,086 | 11.2% |
| | | 207 | Pathological fracture | 308 | 1,838 | 16.8% |
| | | 204 | Other non-traumatic joint disorders | 57 | 607 | 9.4% |
| | | 209 | Other acquired deformities | 62 | 440 | 14.1% |
| | | 230 | Fracture of lower limb | 50 | 285 | 17.5% |
| | | 229 | Fracture of upper limb | 39 | 255 | 15.3% |
| | | 231 | Other fractures | 51 | 217 | 23.5% |
| **154** | **Arthroplasty other than hip or knee** | | **Total** | **1,669** | **30,007** | **5.6%** |
| | | 203 | Osteoarthritis | 622 | 15,818 | 3.9% |
| | | 229 | Fracture of upper limb | 406 | 4,817 | 8.4% |
| | | 211 | Other connective tissue disease | 103 | 2,093 | 4.9% |
| | | 237 | Complication of device; implant or graft | 153 | 1,983 | 7.7% |
| | | 204 | Other non-traumatic joint disorders | 75 | 1,491 | 5.0% |
| | | 212 | Other bone disease and musculoskeletal deformities | 79 | 914 | 8.6% |
| | | 232 | Sprains and strains | 35 | 792 | 4.4% |
| | | 225 | Joint disorders and dislocations; trauma-related | 34 | 541 | 6.3% |
| | | 202 | Rheumatoid arthritis and related disease | 16 | 381 | 4.2% |
| | | 230 | Fracture of lower limb | 29 | 232 | 12.5% |
| **157** | **Amputation of lower extremity** | | **Total** | **10,822** | **39,698** | **27.3%** |
| | | 50 | Diabetes mellitus with complications | 3,243 | 12,591 | 25.8% |
| | | 248 | Gangrene | 3,065 | 10,053 | 30.5% |
| | | 201 | Infective arthritis and osteomyelitis (except that caused by tuberculosis or sexually transmitted di | 515 | 2,938 | 17.5% |
| | | 114 | Peripheral and visceral atherosclerosis | 810 | 2,937 | 27.6% |
| | | 2 | Septicemia (except in labor) | 621 | 2,056 | 30.2% |
| | | 238 | Complications of surgical procedures or medical care | 554 | 2,052 | 27.0% |
| | | 237 | Complication of device; implant or graft | 462 | 1,581 | 29.2% |
| | | 199 | Chronic ulcer of skin | 177 | 749 | 23.6% |
| | | 116 | Aortic and peripheral arterial embolism or thrombosis | 216 | 642 | 33.6% |
| | | 117 | Other circulatory disease | 132 | 387 | 34.1% |
| **158** | **Spinal fusion** | | **Total** | **7,495** | **74,484** | **10.1%** |
| | | 205 | Spondylosis; intervertebral disc disorders; other back problems | 4,782 | 52,912 | 9.0% |
| | | 209 | Other acquired deformities | 853 | 8,999 | 9.5% |
| | | 217 | Other congenital anomalies | 224 | 2,710 | 8.3% |
| | | 237 | Complication of device; implant or graft | 303 | 2,413 | 12.6% |
| | | 231 | Other fractures | 344 | 2,086 | 16.5% |
| | | 212 | Other bone disease and musculoskeletal deformities | 206 | 1,573 | 13.1% |
| | | 207 | Pathological fracture | 201 | 919 | 21.9% |
| | | 227 | Spinal cord injury | 128 | 660 | 19.4% |
| | | 42 | Secondary malignancies | 136 | 536 | 25.4% |
| | | 201 | Infective arthritis and osteomyelitis (except that caused by tuberculosis or sexually transmitted diseases) | 56 | 252 | 22.2% |

| Proc CCS | Procedure CCS | CCS Diag | CCS- Diagnosis Description | 30-Day Readmits | Total Admits | Obs 30-Day Rate |
|----------|---------------|----------|----------------------------|-----------------|--------------|----------------|
| 166 | Lumpectomy; quadrantectomy of breast | | **Total** | **483** | **4,422** | **10.9%** |
| | | 24 | Cancer of breast | 278 | 3,199 | 8.7% |
| | | 167 | Nonmalignant breast conditions | 31 | 207 | 15.0% |
| | | 238 | Complications of surgical procedures or medical care | 18 | 181 | 9.9% |
| | | 42 | Secondary malignancies | 12 | 61 | 19.7% |
| | | 106 | Cardiac dysrhythmias | 10 | 38 | 26.3% |
| | | 108 | Congestive heart failure; nonhypertensive | 7 | 26 | 26.9% |
| | | 2 | Septicemia (except in labor) | 9 | 18 | 50.0% |
| | | 122 | Pneumonia (except that caused by tuberculosis or sexually transmitted disease) | 6 | 17 | 35.3% |
| | | 127 | Chronic obstructive pulmonary disease and bronchiectasis | 5 | 17 | 29.4% |
| | | 131 | Respiratory failure; insufficiency; arrest (adult) | 6 | 11 | 54.5% |
| 167 | Mastectomy | | **Total** | **1,265** | **19,789** | **6.4%** |
| | | 24 | Cancer of breast | 1,154 | 18,854 | 6.1% |
| | | 167 | Nonmalignant breast conditions | 10 | 178 | 5.6% |
| | | 259 | Residual codes; unclassified | 6 | 113 | 5.3% |
| | | 238 | Complications of surgical procedures or medical care | 10 | 97 | 10.3% |
| | | 42 | Secondary malignancies | 11 | 73 | 15.1% |
| | | 106 | Cardiac dysrhythmias | 4 | 20 | 20.0% |
| | | 55 | Fluid and electrolyte disorders | 4 | 18 | 22.2% |
| | | 157 | Acute and unspecified renal failure | 4 | 7 | 57.1% |
| | | 109 | Acute cerebrovascular disease | 4 | 6 | 66.7% |
| | | 103 | Pulmonary heart disease | 3 | 5 | 60.0% |
| 176 | Other organ transplantation | | **Total** | **232** | **677** | **34.3%** |
| | | 151 | Other liver diseases | 62 | 184 | 33.7% |
| | | 133 | Other lower respiratory disease | 35 | 101 | 34.7% |
| | | 108 | Congestive heart failure; nonhypertensive | 18 | 76 | 23.7% |
| | | 16 | Cancer of liver and intrahepatic bile duct | 16 | 64 | 25.0% |
| | | 127 | Chronic obstructive pulmonary disease and bronchiectasis | 31 | 56 | 55.4% |
| | | 663 | Screening and history of mental health and substance abuse codes | 19 | 48 | 39.6% |
| | | 6 | Hepatitis | 9 | 28 | 32.1% |
| | | 101 | Coronary atherosclerosis and other heart disease | 8 | 28 | 28.6% |
| | | 237 | Complication of device; implant or graft | 5 | 17 | 29.4% |
| | | 149 | Biliary tract disease | 7 | 9 | 77.8% |
| 211 | Therapeutic radiology for cancer treatment | | **Total** | **7,089** | **22,957** | **30.9%** |
| | | 42 | Secondary malignancies | 1,572 | 5,271 | 29.8% |
| | | 19 | Cancer of bronchus; lung | 798 | 2,662 | 30.0% |
| | | 45 | Maintenance chemotherapy; radiotherapy | 743 | 1,456 | 51.0% |
| | | 29 | Cancer of prostate | 171 | 877 | 19.5% |
| | | 55 | Fluid and electrolyte disorders | 225 | 631 | 35.7% |
| | | 122 | Pneumonia (except that caused by tuberculosis or sexually transmitted disease) | 200 | 598 | 33.4% |
| | | 38 | Non-Hodgkin`s lymphoma | 175 | 496 | 35.3% |
| | | 95 | Other nervous system disorders | 145 | 453 | 32.0% |
| | | 40 | Multiple myeloma | 144 | 407 | 35.4% |
| | | 2 | Septicemia (except in labor) | 143 | 387 | 37.0% |

## Appendix B – List of AHRQ procedure CCs defining the surgical/gynecological cohort

| CC | Procedure | Maximum Admissions* | Maximum Readmissions* | Readmission Rate |
|----|-----------|--------------------|-----------------------|-----------------|
| 1 | Incision and excision of CNS | 28,261 | 5,753 | 20.40% |
| 2 | Insertion; replacement; or removal of extracranial ventricular shunt | 7,270 | 1,304 | 17.90% |
| 3 | Laminectomy; excision intervertebral disc | 79,631 | 6,619 | 8.30% |
| 9 | Other OR therapeutic nervous system procedures | 16,275 | 2,817 | 17.30% |
| 10 | Thyroidectomy; partial or complete | 12,989 | 862 | 6.60% |
| 12 | Other therapeutic endocrine procedures | 10,415 | 1,340 | 12.90% |
| 13 | Corneal transplant | 157 | 16 | 10.20% |
| 14 | Glaucoma procedures | 130 | 18 | 13.80% |
| 15 | Lens and cataract procedures | 633 | 97 | 15.30% |
| 16 | Repair of retinal tear; detachment | 292 | 33 | 11.30% |
| 17 | Destruction of lesion of retina and choroid | 127 | 9 | 7.10% |
| 20 | Other intraocular therapeutic procedures | 1,107 | 138 | 12.50% |
| 21 | Other extraocular muscle and orbit therapeutic procedures | 1,163 | 150 | 12.90% |
| 22 | Tympanoplasty | 140 | 14 | 10.00% |
| 23 | Myringotomy | 450 | 99 | 22.00% |
| 24 | Mastoidectomy | 273 | 29 | 10.60% |
| 26 | Other therapeutic ear procedures | 2,002 | 263 | 13.10% |
| 28 | Plastic procedures on nose | 1,790 | 213 | 11.90% |
| 30 | Tonsillectomy and/or adenoidectomy | 333 | 43 | 12.90% |
| 33 | Other OR therapeutic procedures on nose; mouth and pharynx | 8,040 | 913 | 11.40% |
| 36 | Lobectomy or pneumonectomy | 32,065 | 4,350 | 13.60% |
| 42 | Other OR Rx procedures on respiratory system and mediastinum | 16,452 | 3,453 | 21.00% |
| 43 | Heart valve procedures | 45,477 | 10,398 | 22.90% |
| 44 | Coronary artery bypass graft (CABG) | 82,527 | 14,548 | 17.60% |
| 49 | Other OR heart procedures | 41,585 | 8,125 | 19.50% |
| 51 | Endarterectomy; vessel of head and neck | 63,024 | 6,288 | 10.00% |
| 52 | Aortic resection; replacement or anastomosis | 27,967 | 3,765 | 13.50% |
| 53 | 'Varicose vein stripping; lower limb | 245 | 33 | 13.50% |
| 55 | Peripheral vascular bypass | 28,972 | 6,163 | 21.30% |
| 56 | Other vascular bypass and shunt; not heart | 2,387 | 763 | 32.00% |
| 59 | Other OR procedures on vessels of head and neck | 14,335 | 1,771 | 12.40% |
| 60 | Embolectomy and endarterectomy of lower limbs | 9,770 | 2,292 | 23.50% |
| 61 | Other OR procedures on vessels other than head and neck | 178,209 | 37,411 | 21.00% |
| 66 | Procedures on spleen | 2,903 | 548 | 18.90% |
| 67 | Other therapeutic procedures; hemic and lymphatic | 42,288 | 5,557 | 13.10% |

| CC | Procedure | Maximum Admissions* | Maximum Readmissions* | Readmission Rate |
|----|-----------|--------------------|-----------------------|------------------|
| | system | | | |
| 72 | Colostomy; temporary and permanent | 10,365 | 1,970 | 19.00% |
| 73 | Ileostomy and other enterostomy | 5,592 | 1,805 | 32.3% |
| 74 | Gastrectomy; partial and total | 6,507 | 1,305 | 20.10% |
| 75 | Small bowel resection | 21,833 | 4,255 | 19.50% |
| 78 | Colorectal resection | 105,467 | 16,702 | 15.80% |
| 79 | Local excision of large intestine lesion (not endoscopic) | 368 | 50 | 13.60% |
| 80 | Appendectomy | 19,326 | 1,851 | 9.60% |
| 84 | Cholecystectomy and common duct exploration | 102,698 | 13,143 | 12.80% |
| 85 | Inguinal and femoral hernia repair | 14,656 | 1,683 | 11.50% |
| 86 | Other hernia repair | 33,253 | 3,887 | 11.70% |
| 89 | Exploratory laparotomy | 2,981 | 611 | 20.50% |
| 90 | Excision; lysis peritoneal adhesions | 36,415 | 6,278 | 17.20% |
| 94 | Other OR upper GI therapeutic procedures | 31,731 | 4,334 | 13.70% |
| 96 | Other OR lower GI therapeutic procedures | 33,387 | 5,846 | 17.50% |
| 99 | Other OR gastrointestinal therapeutic procedures | 29,873 | 6,478 | 21.70% |
| 101 | Transurethral excision; drainage; or removal urinary obstruction | 33225 | 6075 | 18.28% |
| 103 | Nephrotomy and nephrostomy | 13,530 | 3,649 | 27.00% |
| 104 | Nephrectomy; partial or complete | 19,504 | 2,338 | 12.00% |
| 105 | Kidney transplant | 10,873 | 3,175 | 29.20% |
| 106 | Genitourinary incontinence procedures | 8,819 | 351 | 4.00% |
| 112 | Other OR therapeutic procedures of urinary tract | 17,650 | 3,688 | 20.90% |
| 113 | Transurethral resection of prostate (TURP) | 42,523 | 4,259 | 10.00% |
| 114 | Open prostatectomy | 23,965 | 1,158 | 4.80% |
| 118 | Other OR therapeutic procedures; male genital | 6,005 | 835 | 13.90% |
| 142 | Partial excision bone | 37,930 | 5,070 | 13.40% |
| 143 | Bunionectomy or repair of toe deformities | 931 | 84 | 9.00% |
| 144 | Treatment; facial fracture or dislocation | 1,968 | 204 | 10.40% |
| 145 | Treatment; fracture or dislocation of radius and ulna | 14,471 | 1,466 | 10.10% |
| 146 | Treatment; fracture or dislocation of hip and femur | 149,336 | 22,795 | 15.30% |
| 147 | Treatment; fracture or dislocation of lower extremity (other than hip or femur) | 39,901 | 5,000 | 12.50% |
| 148 | Other fracture and dislocation procedure | 23,019 | 2,900 | 12.60% |
| 150 | Division of joint capsule; ligament or cartilage | 3,002 | 230 | 7.70% |
| 151 | Excision of semilunar cartilage of knee | 1,381 | 181 | 13.10% |
| 152 | Arthroplasty knee | 292,149 | 17,995 | 6.20% |
| 153 | Hip replacement; total and partial | 207,011 | 23,096 | 11.20% |
| 154 | Arthroplasty other than hip or knee | 32,597 | 1,772 | 5.40% |
| 157 | Amputation of lower extremity | 51,213 | 13,548 | 26.50% |

| CC | Procedure | Maximum Admissions* | Maximum Readmissions* | Readmission Rate |
|----|-----------|--------------------|-----------------------|------------------|
| 158 | Spinal fusion | 106,703 | 10,307 | 9.70% |
| 160 | Other therapeutic procedures on muscles and tendons | 32,254 | 4,998 | 15.50% |
| 161 | Other OR therapeutic procedures on bone | 29,314 | 5,611 | 19.10% |
| 162 | Other OR therapeutic procedures on joints | 25,661 | 4,125 | 16.10% |
| 164 | Other OR therapeutic procedures on musculoskeletal system | 5,963 | 1,346 | 22.60% |
| 166 | Lumpectomy; quadrantectomy of breast | 2,994 | 311 | 10.40% |
| 167 | Mastectomy | 16,333 | 1,102 | 6.70% |
| 172 | Skin graft | 13,987 | 2,508 | 17.90% |
| 175 | Other OR therapeutic procedures on skin and breast | 6,626 | 879 | 13.30% |
| 176 | Other organ transplantation | 2,483 | 855 | 34.40% |
| 119 | Oophorectomy; unilateral and bilateral | 33,667 | 2,856 | 8.50% |
| 120 | Other operations on ovary | 906 | 111 | 12.30% |
| 121 | Ligation or occlusion of fallopian tubes | 228 | 13 | 5.70% |
| 122 | Removal of ectopic pregnancy | 143 | 6 | 4.20% |
| 123 | Other operations on fallopian tubes | 937 | 82 | 8.80% |
| 124 | Hysterectomy; abdominal and vaginal | 48,236 | 3,515 | 7.30% |
| 125 | Other excision of cervix and uterus | 1,062 | 131 | 12.30% |
| 126 | Abortion (termination of pregnancy) | 39 | 10 | 25.60% |
| 127 | Dilatation and curettage (D&C); aspiration after delivery or abortion | 298 | 26 | 8.70% |
| 129 | Repair of cystocele and rectocele; obliteration of vaginal vault | 14,446 | 476 | 3.30% |
| 131 | Other non-OR therapeutic procedures; female organs | 509 | 115 | 22.60% |
| 132 | Other OR therapeutic procedures; female organs | 13,796 | 996 | 7.20% |
| 133 | Episiotomy | 372 | 7 | 1.90% |
| 134 | Cesarean section | 6,226 | 280 | 4.50% |
| 135 | Forceps; vacuum; and breech delivery | 535 | 15 | 2.80% |
| 136 | Artificial rupture of membranes to assist delivery | 1,510 | 37 | 2.50% |
| 137 | Other procedures to assist delivery | 5,131 | 162 | 3.20% |
| 139 | Fetal monitoring | 1,488 | 179 | 12.00% |
| 140 | Repair of current obstetric laceration | 1,387 | 38 | 2.70% |
| 141 | Other therapeutic obstetrical procedures | 166 | 10 | 6.00% |
| 174 | Female infertility | 1 | - | 0.00% |

**Total 2008 admissions**: 8,203,390

**Total 2008 unique readmissions**: 1,473,914

\*Full Medicare data including those <65 years. Not mutually exclusive; multiple procedures may be performed during a single admission.

## Appendix C – Condition categories assigned to the medical cohorts

| Model Group | CCS | Description | Admits | Unplanned 30 Day Readmits | Unplanned 30-Day Readmit Rate |
|---|---|---|---|---|---|
| Cardiovascular | 106 | Cardiac dysrhythmias | 315,298 | 50,117 | 15.9% |
| Cardiovascular | 102 | Nonspecific chest pain | 142,883 | 15,522 | 10.9% |
| Cardiovascular | 100 | Acute myocardial infarction | 116,810 | 25,221 | 21.6% |
| Cardiovascular | 101 | Coronary atherosclerosis and other heart disease | 116,147 | 15,240 | 13.1% |
| Cardiovascular | 117 | Other circulatory disease | 56,016 | 9,199 | 16.4% |
| Cardiovascular | 105 | Conduction disorders | 33,899 | 3,783 | 11.2% |
| Cardiovascular | 114 | Peripheral and visceral atherosclerosis | 27,169 | 4,294 | 15.8% |
| Cardiovascular | 97 | Peri-; endo-; and myocarditis; cardiomyopathy (except caused by TB/STD | 13,241 | 2,756 | 20.8% |
| Cardiovascular | 96 | Heart valve disorders | 9,920 | 1,812 | 18.3% |
| Cardiovascular | 115 | Aortic; peripheral; and visceral artery aneurysms | 5,010 | 773 | 15.4% |
| Cardiovascular | 116 | Aortic and peripheral arterial embolism or thrombosis | 2,570 | 446 | 17.4% |
| Cardiovascular | 107 | Cardiac arrest and ventricular fibrillation | 2,009 | 362 | 18.0% |
| Cardiovascular | 104 | Other and ill-defined heart disease | 1,749 | 253 | 14.5% |
| Cardiovascular | 213 | Cardiac and circulatory congenital anomalies | 652 | 118 | 18.1% |
| Cardiovascular | | Total | 843,373 | 129,896 | 15.4% |
| Cancer | 45 | Maintenance chemotherapy; radiotherapy | 21,522 | 4,842 | 22.5% |
| Cancer | 44 | Neoplasms of unspecified nature or uncertain behavior | 10,160 | 3,170 | 31.2% |
| Cancer | 38 | Non-Hodgkin's lymphoma | 7,977 | 2,373 | 29.7% |
| Cancer | 39 | Leukemias | 7,809 | 2,301 | 29.5% |
| Cancer | 40 | Multiple myeloma | 4,624 | 1,380 | 29.8% |
| Cancer | 35 | Cancer of brain and nervous system | 3,561 | 836 | 23.5% |
| Cancer | 13 | Cancer of stomach | 3,467 | 820 | 23.7% |
| Cancer | 29 | Cancer of prostate | 3,100 | 497 | 16.0% |
| Cancer | 15 | Cancer of rectum and anus | 3,030 | 505 | 16.7% |
| Cancer | 18 | Cancer of other GI organs; peritoneum | 2,974 | 792 | 26.6% |
| Cancer | 12 | Cancer of esophagus | 2,533 | 604 | 23.8% |
| Cancer | 11 | Cancer of head and neck | 2,515 | 681 | 27.1% |
| Cancer | 33 | Cancer of kidney and renal pelvis | 1,863 | 397 | 21.3% |
| Cancer | 32 | Cancer of bladder | 1,807 | 469 | 26.0% |
| Cancer | 25 | Cancer of uterus | 1,132 | 196 | 17.3% |
| Cancer | 36 | Cancer of thyroid | 879 | 76 | 8.6% |
| Cancer | 21 | Cancer of bone and connective tissue | 763 | 181 | 23.7% |
| Cancer | 20 | Cancer; other respiratory and intrathoracic | 632 | 108 | 17.1% |
| Cancer | 23 | Other non-epithelial cancer of skin | 593 | 117 | 19.7% |
| Cancer | 26 | Cancer of cervix | 586 | 88 | 15.0% |
| Cancer | 28 | Cancer of other female genital organs | 326 | 57 | 17.5% |
| Cancer | 34 | Cancer of other urinary organs | 301 | 54 | 17.9% |
| Cancer | 37 | Hodgkin's disease | 236 | 72 | 30.5% |
| Cancer | 30 | Cancer of testis | 4 | - | 0.0% |
| Cancer | | Total | 82,394 | 20,616 | 25.0% |

| Model Group | CCS | Description | Admits | Unplanned 30 Day Readmits | Unplanned 30-Day Readmit Rate |
|---|---|---|---|---|---|
| Cardiorespiratory | 108 | Congestive heart failure; nonhypertensive | 453,342 | 112,291 | 24.8% |
| Cardiorespiratory | 122 | Pneumonia (except that caused by TB/STD) | 403,973 | 71,911 | 17.8% |
| Cardiorespiratory | 127 | Chronic obstructive pulmonary disease and bronchiectasis | 297,736 | 64,450 | 21.6% |
| Cardiorespiratory | 131 | Respiratory failure; insufficiency; arrest (adult) | 117,569 | 28,678 | 24.4% |
| Cardiorespiratory | 128 | Asthma | 61,696 | 11,148 | 18.1% |
| Cardiorespiratory | 103 | Pulmonary heart disease | 45,122 | 7,496 | 16.6% |
| Cardiorespiratory | 125 | Acute bronchitis | 25,833 | 3,301 | 12.8% |
| Cardiorespiratory | | Total | 1,405,271 | 299,275 | 21.3% |
| Medicine | 2 | Septicemia (except in labor) | 236,993 | 50,800 | 21.4% |
| Medicine | 159 | Urinary tract infections | 232,590 | 41,833 | 18.0% |
| Medicine | 55 | Fluid and electrolyte disorders | 178,808 | 33,032 | 18.5% |
| Medicine | 157 | Acute and unspecified renal failure | 163,357 | 36,435 | 22.3% |
| Medicine | 153 | Gastrointestinal hemorrhage | 135,891 | 23,065 | 17.0% |
| Medicine | 197 | Skin and subcutaneous tissue infections | 111,670 | 17,171 | 15.4% |
| Medicine | 245 | Syncope | 107,933 | 11,885 | 11.0% |
| Medicine | 129 | Aspiration pneumonitis; food/vomitus | 88,296 | 19,365 | 21.9% |
| Medicine | 145 | Intestinal obstruction without hernia | 88,193 | 14,840 | 16.8% |
| Medicine | 146 | Diverticulosis and diverticulitis | 85,920 | 11,991 | 14.0% |
| Medicine | 237 | Complication of device; implant or graft | 81,549 | 18,932 | 23.2% |
| Medicine | 238 | Complications of surgical procedures or medical care | 81,398 | 14,994 | 18.4% |
| Medicine | 59 | Deficiency and other anemia | 79,517 | 17,810 | 22.4% |
| Medicine | 50 | Diabetes mellitus with complications | 74,976 | 14,418 | 19.2% |
| Medicine | 135 | Intestinal infection | 70,077 | 16,274 | 23.2% |
| Medicine | 231 | Other fractures | 69,105 | 10,273 | 14.9% |
| Medicine | 99 | Hypertension with complications and secondary hypertension | 67,337 | 14,943 | 22.2% |
| Medicine | 118 | Phlebitis; thrombophlebitis and thromboembolism | 48,254 | 7,098 | 14.7% |
| Medicine | 205 | Spondylosis; intervertebral disc disorders; other back problems | 46,916 | 7,457 | 15.9% |
| Medicine | 155 | Other gastrointestinal disorders | 44,151 | 9,008 | 20.4% |
| Medicine | 133 | Other lower respiratory disease | 36,203 | 6,484 | 17.9% |
| Medicine | 152 | Pancreatic disorders (not diabetes) | 34,779 | 5,541 | 15.9% |
| Medicine | 149 | Biliary tract disease | 33,718 | 5,583 | 16.6% |
| Medicine | 138 | Esophageal disorders | 33,354 | 4,778 | 14.3% |
| Medicine | 154 | Noninfectious gastroenteritis | 33,236 | 4,775 | 14.4% |
| Medicine | 259 | Residual codes; unclassified | 32,960 | 5,931 | 18.0% |
| Medicine | 93 | Conditions associated with dizziness or vertigo | 30,934 | 2,358 | 7.6% |
| Medicine | 130 | Pleurisy; pneumothorax; pulmonary collapse | 29,482 | 7,543 | 25.6% |
| Medicine | 140 | Gastritis and duodenitis | 29,329 | 5,002 | 17.1% |
| Medicine | 211 | Other connective tissue disease | 28,565 | 4,163 | 14.6% |
| Medicine | 251 | Abdominal pain | 27,091 | 4,480 | 16.5% |
| Medicine | 151 | Other liver diseases | 20,612 | 6,340 | 30.8% |
| Medicine | 244 | Other injuries and conditions due to external causes | 20,470 | 3,104 | 15.2% |
| Medicine | 98 | Essential hypertension | 18,409 | 2,142 | 11.6% |

| Model Group | CCS | Description | Admits | Unplanned 30 Day Readmits | Unplanned 30-Day Readmit Rate |
|-------------|-----|-------------|--------|--------------------------|-------------------------------|
| Medicine | 207 | Pathological fracture | 18,040 | 3,823 | 21.2% |
| Medicine | 239 | Superficial injury; contusion | 17,651 | 2,710 | 15.4% |
| Medicine | 141 | Other disorders of stomach and duodenum | 17,168 | 3,616 | 21.1% |
| Medicine | 58 | Other nutritional; endocrine; and metabolic disorders | 16,379 | 3,416 | 20.9% |
| Medicine | 199 | Chronic ulcer of skin | 16,350 | 3,425 | 20.9% |
| Medicine | 51 | Other endocrine disorders | 16,343 | 3,200 | 19.6% |
| Medicine | 229 | Fracture of upper limb | 15,309 | 2,506 | 16.4% |
| Medicine | 252 | Malaise and fatigue | 14,677 | 2,443 | 16.6% |
| Medicine | 63 | Diseases of white blood cells | 14,138 | 3,399 | 24.0% |
| Medicine | 123 | Influenza | 14,096 | 1,689 | 12.0% |
| Medicine | 7 | Viral infection | 13,805 | 2,200 | 15.9% |
| Medicine | 230 | Fracture of lower limb | 13,448 | 2,049 | 15.2% |
| Medicine | 246 | Fever of unknown origin | 13,079 | 2,323 | 17.8% |
| Medicine | 242 | Poisoning by other medications and drugs | 12,394 | 1,934 | 15.6% |
| Medicine | 160 | Calculus of urinary tract | 12,195 | 1,573 | 12.9% |
| Medicine | 163 | Genitourinary symptoms and ill-defined conditions | 11,122 | 1,948 | 17.5% |
| Medicine | 204 | Other non-traumatic joint disorders | 10,891 | 1,567 | 14.4% |
| Medicine | 250 | Nausea and vomiting | 10,795 | 2,173 | 20.1% |
| Medicine | 120 | Hemorrhoids | 10,365 | 1,628 | 15.7% |
| Medicine | 62 | Coagulation and hemorrhagic disorders | 9,534 | 2,483 | 26.0% |
| Medicine | 134 | Other upper respiratory disease | 9,068 | 1,592 | 17.6% |
| Medicine | 234 | Crushing injury or internal injury | 8,329 | 1,224 | 14.7% |
| Medicine | 201 | Infective arthritis and osteomyelitis (except that caused by TB/STD | 8,105 | 1,692 | 20.9% |
| Medicine | 203 | Osteoarthritis | 7,984 | 1,061 | 13.3% |
| Medicine | 144 | Regional enteritis and ulcerative colitis | 7,954 | 1,601 | 20.1% |
| Medicine | 60 | Acute posthemorrhagic anemia | 7,768 | 1,588 | 20.4% |
| Medicine | 4 | Mycoses | 7,739 | 2,144 | 27.7% |
| Medicine | 126 | Other upper respiratory infections | 7,663 | 975 | 12.7% |
| Medicine | 143 | Abdominal hernia | 7,410 | 1,430 | 19.3% |
| Medicine | 139 | Gastroduodenal ulcer (except hemorrhage) | 7,378 | 1,117 | 15.1% |
| Medicine | 47 | Other and unspecified benign neoplasm | 7,123 | 1,286 | 18.1% |
| Medicine | 161 | Other diseases of kidney and ureters | 7,057 | 1,313 | 18.6% |
| Medicine | 121 | Other diseases of veins and lymphatics | 6,969 | 1,258 | 18.1% |
| Medicine | 232 | Sprains and strains | 6,531 | 895 | 13.7% |
| Medicine | 54 | Gout and other crystal arthropathies | 6,150 | 1,007 | 16.4% |
| Medicine | 84 | Headache; including migraine | 5,839 | 688 | 11.8% |
| Medicine | 147 | Anal and rectal conditions | 5,116 | 1,010 | 19.7% |
| Medicine | 212 | Other bone disease and musculoskeletal deformities | 4,926 | 752 | 15.3% |
| Medicine | 158 | Chronic renal failure | 4,886 | 1,196 | 24.5% |
| Medicine | 228 | Skull and face fractures | 4,632 | 596 | 12.9% |
| Medicine | 165 | Inflammatory conditions of male genital organs | 4,222 | 474 | 11.2% |
| Medicine | 52 | Nutritional deficiencies | 4,003 | 978 | 24.4% |
| Medicine | 253 | Allergic reactions | 3,885 | 575 | 14.8% |

| Model Group | CCS | Description | Admits | Unplanned 30 Day Readmits | Unplanned 30-Day Readmit Rate |
|-------------|-----|-------------|--------|--------------------------|-------------------------------|
| Medicine | 162 | Other diseases of bladder and urethra | 3,850 | 707 | 18.4% |
| Medicine | 137 | Diseases of mouth; excluding dental | 3,821 | 615 | 16.1% |
| Medicine | 164 | Hyperplasia of prostate | 3,734 | 684 | 18.3% |
| Medicine | 148 | Peritonitis and intestinal abscess | 3,663 | 909 | 24.8% |
| Medicine | 48 | Thyroid disorders | 3,634 | 669 | 18.4% |
| Medicine | 235 | Open wounds of head; neck; and trunk | 3,631 | 464 | 12.8% |
| Medicine | 241 | Poisoning by psychotropic agents | 3,191 | 411 | 12.9% |
| Medicine | 6 | Hepatitis | 3,042 | 830 | 27.3% |
| Medicine | 202 | Rheumatoid arthritis and related disease | 2,806 | 486 | 17.3% |
| Medicine | 8 | Other infections; including parasitic | 2,381 | 297 | 12.5% |
| Medicine | 236 | Open wounds of extremities | 2,253 | 356 | 15.8% |
| Medicine | 49 | Diabetes mellitus without complication | 2,198 | 316 | 14.4% |
| Medicine | 198 | Other inflammatory condition of skin | 2,028 | 424 | 20.9% |
| Medicine | 76 | Meningitis (except that caused by TB/STD) | 2,003 | 335 | 16.7% |
| Medicine | 248 | Gangrene | 1,996 | 438 | 21.9% |
| Medicine | 90 | Inflammation; infection of eye (except that caused by by TB/STD) | 1,994 | 276 | 13.8% |
| Medicine | 132 | Lung disease due to external agents | 1,866 | 378 | 20.3% |
| Medicine | 136 | Disorders of teeth and jaw | 1,602 | 194 | 12.1% |
| Medicine | 89 | Blindness and vision defects | 1,550 | 164 | 10.6% |
| Medicine | 210 | Systemic lupus erythematosus and connective tissue disorders | 1,466 | 353 | 24.1% |
| Medicine | 243 | Poisoning by nonmedicinal substances | 1,424 | 114 | 8.0% |
| Medicine | 3 | Bacterial infection; unspecified site | 1,386 | 261 | 18.8% |
| Medicine | 240 | Burns | 1,373 | 223 | 16.2% |
| Medicine | 77 | Encephalitis (except that caused by by TB/STD) | 1,361 | 242 | 17.8% |
| Medicine | 91 | Other eye disorders | 1,344 | 144 | 10.7% |
| Medicine | 175 | Other female genital disorders | 1,119 | 206 | 18.4% |
| Medicine | 225 | Joint disorders and dislocations; trauma-related | 1,104 | 129 | 11.7% |
| Medicine | 94 | Other ear and sense organ disorders | 1,005 | 117 | 11.6% |
| Medicine | 119 | Varicose veins of lower extremity | 991 | 139 | 14.0% |
| Medicine | 200 | Other skin disorders | 985 | 150 | 15.2% |
| Medicine | 167 | Nonmalignant breast conditions | 977 | 124 | 12.7% |
| Medicine | 257 | Other aftercare | 894 | 142 | 15.9% |
| Medicine | 168 | Inflammatory diseases of female pelvic organs | 852 | 139 | 16.3% |
| Medicine | 87 | Retinal detachments; defects; vascular occlusion; and retinopathy | 852 | 84 | 9.9% |
| Medicine | 142 | Appendicitis and other appendiceal conditions | 803 | 100 | 12.5% |
| Medicine | 209 | Other acquired deformities | 760 | 109 | 14.3% |
| Medicine | 156 | Nephritis; nephrosis; renal sclerosis | 756 | 201 | 26.6% |
| Medicine | 173 | Menopausal disorders | 748 | 117 | 15.6% |
| Medicine | 1 | Tuberculosis | 735 | 138 | 18.8% |
| Medicine | 64 | Other hematologic conditions | 730 | 149 | 20.4% |
| Medicine | 92 | Otitis media and related conditions | 724 | 105 | 14.5% |
| Medicine | 166 | Other male genital disorders | 714 | 150 | 21.0% |
| Medicine | 5 | HIV infection | 611 | 178 | 29.1% |

| Model Group | CCS | Description | Admits | Unplanned 30 Day Readmits | Unplanned 30-Day Readmit Rate |
|-------------|-----|-------------|--------|--------------------------|-------------------------------|
| Medicine | 247 | Lymphadenitis | 456 | 88 | 19.3% |
| Medicine | 249 | Shock | 451 | 112 | 24.8% |
| Medicine | 9 | Sexually transmitted infections (not HIV or hepatitis) | 366 | 56 | 15.3% |
| Medicine | 258 | Other screening for suspected conditions (not mental or infectious) | 328 | 41 | 12.5% |
| Medicine | 217 | Other congenital anomalies | 312 | 59 | 18.9% |
| Medicine | 214 | Digestive congenital anomalies | 305 | 50 | 16.4% |
| Medicine | 170 | Prolapse of female genital organs | 257 | 52 | 20.2% |
| Medicine | 215 | Genitourinary congenital anomalies | 239 | 43 | 18.0% |
| Medicine | 124 | Acute and chronic tonsillitis | 221 | 10 | 4.5% |
| Medicine | 61 | Sickle cell anemia | 203 | 49 | 24.1% |
| Medicine | 57 | Immunity disorders | 158 | 54 | 34.2% |
| Medicine | 206 | Osteoporosis | 148 | 22 | 14.9% |
| Medicine | 10 | Immunizations and screening for infectious disease | 127 | 16 | 12.6% |
| Medicine | 88 | Glaucoma | 124 | 20 | 16.1% |
| Medicine | 172 | Ovarian cyst | 114 | 14 | 12.3% |
| Medicine | 208 | Acquired foot deformities | 103 | 17 | 16.5% |
| Medicine | 46 | Benign neoplasm of uterus | 102 | 15 | 14.7% |
| Medicine | 53 | Disorders of lipid metabolism | 98 | 16 | 16.3% |
| Medicine | 171 | Menstrual disorders | 68 | 11 | 16.2% |
| Medicine | 86 | Cataract | 37 | 6 | 16.2% |
| Medicine | 256 | Medical examination/evaluation | 30 | 5 | 16.7% |
| Medicine | 255 | Administrative/social admission | 14 | 2 | 14.3% |
| Medicine | 56 | Cystic fibrosis | 14 | 3 | 21.4% |
| Medicine | 169 | Endometriosis | 13 | 2 | 15.4% |
| Medicine | 174 | Female infertility | 1 | - | 0.0% |
| **Medicine** | | **Total** | **3,009,835** | **549,935** | **18.3%** |
| Neurology | 109 | Acute cerebrovascular disease | 197,598 | 28,961 | 14.7% |
| Neurology | 112 | Transient cerebral ischemia | 82,499 | 9,272 | 11.2% |
| Neurology | 95 | Other nervous system disorders | 58,486 | 10,406 | 17.8% |
| Neurology | 83 | Epilepsy; convulsions | 38,034 | 6,115 | 16.1% |
| Neurology | 233 | Intracranial injury | 35,366 | 5,963 | 16.9% |
| Neurology | 81 | Other hereditary and degenerative nervous system conditions | 10,075 | 1,797 | 17.8% |
| Neurology | 110 | Occlusion or stenosis of precerebral arteries | 9,091 | 1,298 | 14.3% |
| Neurology | 79 | Parkinson`s disease | 6,651 | 921 | 13.8% |
| Neurology | 113 | Late effects of cerebrovascular disease | 6,396 | 1,062 | 16.6% |
| Neurology | 85 | Coma; stupor; and brain damage | 6,092 | 990 | 16.3% |
| Neurology | 111 | Other and ill-defined cerebrovascular disease | 5,316 | 638 | 12.0% |
| Neurology | 80 | Multiple sclerosis | 1,036 | 147 | 14.2% |
| Neurology | 82 | Paralysis | 883 | 135 | 15.3% |
| Neurology | 227 | Spinal cord injury | 832 | 144 | 17.3% |
| Neurology | 78 | Other CNS infection and poliomyelitis | 786 | 139 | 17.7% |
| Neurology | 216 | Nervous system congenital anomalies | 48 | 12 | 25.0% |
| **Neurology** | | **Total** | **459,189** | **68,000** | **14.8%** |

| Model Group | CCS | Description | Admits | Unplanned 30 Day Readmits | Unplanned 30-Day Readmit Rate |
|-------------|-----|-------------|--------|--------------------------|-------------------------------|
| Psych | 653 | Delirium, dementia, and amnestic and other cognitive disorders | 44,266 | 6,581 | 14.9% |
| Psych | 661 | Substance-related disorders | 11,050 | 1,942 | 17.6% |
| Psych | 660 | Alcohol-related disorders | 8,578 | 1,270 | 14.8% |
| Psych | 657 | Mood disorders | 7,874 | 1,197 | 15.2% |
| Psych | 659 | Schizophrenia and other psychotic disorders | 7,849 | 1,253 | 16.0% |
| Psych | 663 | Screening and history of mental health and substance abuse codes | 4,482 | 1,142 | 25.5% |
| Psych | 651 | Anxiety disorders | 3,153 | 394 | 12.5% |
| Psych | 670 | Miscellaneous disorders | 1,315 | 207 | 15.7% |
| Psych | 654 | Developmental disorders | 594 | 123 | 20.7% |
| Psych | 650 | Adjustment disorders | 399 | 67 | 16.8% |
| Psych | 658 | Personality disorders | 127 | 21 | 16.5% |
| Psych | 652 | Attention-deficit, conduct, and disruptive behavior disorders | 119 | 18 | 15.1% |
| Psych | 656 | Impulse control disorders, NEC | 27 | 4 | 14.8% |
| Psych | 655 | Disorders usually diagnosed in infancy, childhood, or adolescence | 16 | 4 | 25.0% |
| Psych | 662 | Suicide and intentional self-inflicted injury | 10 | 2 | 20.0% |
| **Psych** | | **Total** | **89,859** | **14,225** | **15.8%** |

## Appendix D – Conditions that are treated as complications if occurring during index admission

| CC | Label | Potential Complications |
|----|-------|------------------------|
| **2** | Septicemia/Shock | x |
| **6** | Other Infectious Diseases | x |
| **17** | Diabetes with Acute Complications | x |
| **23** | Disorders of Fluid/Electrolyte/Acid-Base | x |
| **24** | Other Endocrine/Metabolic/ Nutritional Disorders | |
| **28** | Acute Liver Failure/Disease | x |
| **31** | Intestinal Obstruction/Perforation | x |
| **34** | Peptic Ulcer, Hemorrhage, Other Specified Gastrointestinal Disorders | x |
| **36** | Other Gastrointestinal Disorders | |
| **37** | Bone/Joint/Muscle Infections/Necrosis | |
| **43** | Other Musculoskeletal and Connective Tissue Disorders | |
| **46** | Coagulation Defects and Other Specified Hematological Disorders | x |
| **47** | Iron Deficiency and Other/ Unspecified Anemias and Blood Disease | |
| **48** | Delirium and Encephalopathy | x |
| **51** | Drug/Alcohol Psychosis | |
| **75** | Coma, Brain Compression/Anoxic Damage | x |
| **76** | Mononeuropathy, Other Neurological Conditions/Injuries | |
| **77** | Respirator Dependence/Tracheostomy Status | x |
| **78** | Respiratory Arrest | x |
| **79** | Cardio-Respiratory Failure and Shock | x |
| **80** | Congestive Heart Failure | x |
| **81** | Acute Myocardial Infarction | x |
| **82** | Unstable Angina and Other Acute Ischemic Heart Disease | x |
| **85** | Heart Infection/Inflammation, Except Rheumatic | |
| **92** | Specified Heart Arrhythmias | x |
| **93** | Other Heart Rhythm and Conduction Disorders | x |
| **95** | Cerebral Hemorrhage | x |
| **96** | Ischemic or Unspecified Stroke | x |
| **97** | Precerebral Arterial Occlusion and Transient Cerebral Ischemia | x |
| **100** | Hemiplegia/Hemiparesis | x |
| **101** | Diplegia (Upper), Monoplegia, and Other Paralytic Syndromes | x |
| **102** | Speech, Language, Cognitive, Perceptual | x |
| **104** | Vascular Disease with Complications | x |
| **105** | Vascular Disease | x |
| **106** | Other Circulatory Disease | x |
| **111** | Aspiration and Specified Bacterial Pneumonias | x |
| **112** | Pneumococcal Pneumonia, Emphysema, Lung Abscess | x |
| **114** | Pleural Effusion/Pneumothorax | x |
| **124** | Other Eye Disorders | |

| CC | Label | Potential Complications |
|----|-------|------------------------|
| 129 | End Stage Renal Disease | x |
| 130 | Dialysis Status | x |
| 131 | Renal Failure | x |
| 132 | Nephritis | x |
| 133 | Urinary Obstruction and Retention | x |
| 135 | Urinary Tract Infection | x |
| 148 | Decubitus Ulcer of Skin | x |
| 152 | Cellulitis, Local Skin Infection | x |
| 154 | Severe Head Injury | x |
| 155 | Major Head Injury | x |
| 156 | Concussion or Unspecified Head Injury | x |
| 157 | Vertebral Fractures | |
| 158 | Hip Fracture/Dislocation | x |
| 159 | Major Fracture, Except of Skull, Vertebrae, or Hip | x |
| 160 | Internal Injuries | |
| 161 | Traumatic Amputation | |
| 162 | Other Injuries | |
| 163 | Poisonings and Allergic Reactions | x |
| 164 | Major Complications of Medical Care and Trauma | x |
| 165 | Other Complications of Medical Care | x |
| 166 | Major Symptoms, Abnormalities | |
| 174 | Major Organ Transplant Status | x |
| 175 | Other Organ Transplant/Replacement | x |
| 176 | Artificial Openings for Feeding or Elimination | x |
| 177 | Amputation Status, Lower Limb/Amputation | x |
| 178 | Amputation Status, Upper Limb | x |
| 179 | Post-Surgical States/Aftercare/Elective | x |

## Appendix E –Candidate risk variables

| Label | Pope et al. CCs          | Description*                                             |
|-------|--------------------------|----------------------------------------------------------|
| rf1   | 1, 3-5                   | History of Infection                                     |
| rf2   | 6                        | Other infectious disease                                 |
| rf3   | 7                        | Metastatic cancer/acute leukemia                         |
| rf4   | 8                        | Lung or other severe cancers                             |
| rf5   | 9                        | Other major cancers                                      |
| rf6   | 10                       | Other major cancers                                      |
| rf7   | 11                       | Cancer                                                   |
| rf8   | 12                       | Cancer                                                   |
| rf9   | 15,16,18-20, 119, 120    | Diabetes mellitus or DM complications                    |
| rf10  | 21                       | Protein-calorie malnutrition                             |
| rf11  | 25, 26                   | Liver or biliary disease                                 |
| rf12  | 44                       | Other hematologoical disorders                           |
| rf13  | 49, 50                   | Dementia or other specified brain disorders              |
| rf14  | 52, 53                   | Drug/alcohol abuse/dependence/psychosis                  |
| rf15  | 54-56                    | Major psychiatric disorders                              |
| rf16  | 58                       | Depression                                               |
| rf17  | 60                       | Other psychiatric disorders                              |
| rf18  | 67-69, 100-102, 177, 178 | Hemiplegia, paraplegia, paralysis, functional disability |
| rf19  | 74                       | Seizure disorders and convulsions                        |
| rf20  | 80                       | CHF                                                      |
| rf21  | 83, 84                   | Coronary atherosclerosis or angina                       |
| rf22  | 86                       | Valvular or rheumatic heart disease                      |
| rf23  | 90                       | Hypertensive heart failure                               |
| rf24  | 92, 93                   | Specified arrhythmias                                    |
| rf25  | 98, 99, 103              | Cerebrovascular disease                                  |
| rf26  | 108                      | COPD                                                     |
| rf27  | 109                      | Fibrosis of lung or other chronic lung disorders         |
| rf28  | 110                      | Asthma                                                   |
| rf29  | 129, 130                 | End stage renal disease                                  |
| rf30  | 149                      | Decubitus ulcer or chronic skin ulcer                    |
| rf31  | 2                        | Septicemia/Shock                                         |
| rf32  | 22, 23                   | Disorders of fluid, electrolyte, acid-base               |
| rf33  | 47                       | Iron deficiency                                          |
| rf34  | 79                       | Cardio-respiratory failure or shock                      |
| rf35  | 81, 82                   | Acute coronary syndrome                                  |
| rf36  | 95, 96                   | Stroke                                                   |
| rf37  | 104, 105, 106            | Circulatory or vascular disease                          |
| rf38  | 111, 112, 113            | Pneumonia                                                |
| rf39  | 131                      | Renal failure                                            |
| rf40  | 136                      | Other urinary tract disorders                            |
| rf41  | 148                      | Decubitus ulcer                                          |

## Appendix F – Final risk-adjustment variables

| Label | Pope et al. CCs | Description* | Not adjusted for if only present on index admission (complication) |
|---|---|---|---|
| **Age** | n/a | **Age (-65)** | |
| **Cond. Ind.** | n/a | **Condition indicator (AHRQ CCS)** | |
| | 1, 3-5 | **Severe infection** | |
| | 1 | HIV/AIDS | |
| **rf1** | 3 | Central nervous system infection | |
| | 4 | Tuberculosis | |
| | 5 | Opportunistic infections | |
| | 6, 111-113 | **Other infectious disease & pneumonias** | |
| | 6 | Other infectious disease | x |
| **rf2** | 111 | Aspiration and specified bacterial pneumonias | x |
| | 112 | Pneumococcal pneumonia, emphysema, lung abscess | x |
| | 113 | Viral and unspecified pneumonia, pleurisy | x |
| **rf3** | 7 | **Metastatic cancer/acute leukemia** | |
| | 8, 9 | **Severe cancer** | |
| **rf4** | 8 | Lung, upper digestive tract, and other severe cancers | |
| | 9 | Other major cancers | |
| | 10, 11, 12 | **Other major cancers** | |
| | 10 | Breast, prostate, colorectal and other cancers and tumors | |
| **rf6** | 11 | Other respiratory and heart neoplasms | |
| | 12 | Other digestive and urinary neoplasms | |
| | 15,16,18-20, 119, 120 | **Diabetes mellitus** | |
| | 15 | Diabetes with renal manifestation | |
| | 16 | Diabetes with neurologic or peripheral circulatory manifestation | |
| **rf9** | 17 | Diabetes with acute complications | x |
| | 18 | Diabetes with ophthalmologic manifestation | |
| | 19 | Diabetes with no or unspecified complications | |
| | 20 | Type I diabetes mellitus | |
| | 119 | Proliferative diabetic retinopathy and vitreous hemorrhage | |
| | 120 | Diabetic and other vascular retinopathies | |
| **rf10** | 21 | **Protein-calorie malnutrition** | |
| | 25, 26 | **End-Stage liver disease** | |
| **rf11** | 25 | End-Stage Liver Disease | |

| Label | Pope et al. CCs | Description* | Not adjusted for if only present on index admission (complication) |
|-------|-----------------|--------------|--------------------------------------------------|
| | 26 | Cirrhosis of Liver | |
| rf12 | 44 | **Other hematologoical disorders** | |
| | 51-52 | Drug and Alcohol disorders | |
| rf14 | 52 | Drug/alcohol dependence | |
| | 51 | Drug/alcohol psychosis | |
| | 54-56, 58, 60 | **Psychiatric comorbidity** | |
| | 54 | Schizophrenia | |
| rf15 | 55 | Major depressive, bipolar, and paranoid disorders | |
| | 56 | Reactive and unspecified psychosis | |
| | 58 | Depression | |
| | 60 | Other psychiatric disorders | |
| | 67-69, 100-102, 177, 178 | **Hemiplegia, paraplegia, paralysis, functional disability** | |
| | 67 | Quadriplegia, other extensive paralysis | |
| | 68 | Paraplegia | |
| | 69 | Spinal Cord Disorders/Injuries | |
| rf18 | 100 | Hemiplegia/hemiparesis | |
| | 101 | Diplegia (upper), monoplegia, and other paralytic syndromes | |
| | 102 | Speech, language, cognitive, perceptual | |
| | 177 | Amputation status, lower limb/amputation | |
| | 178 | Amputation status, upper limb | |
| rf19 | 74 | **Seizure disorders and convulsions** | |
| rf20 | 80 | **CHF** | x |
| | 81-84, 89, 98, 99, 103-106 | **Coronary atherosclerosis or angina, cerebrovascular disease** | |
| | 81 | Acute myocardial infarction | x |
| | 82 | Unstable angina and other acute ischemic heart disease | x |
| | 83 | Angina pectoris/old myocardial infarction | |
| rf21 | 84 | Coronary atherosclerosis/other chronic ischemic heart disease | |
| | 89 | Hypertensive heart and renal disease or ensephalopathy | |
| | 98 | Cerebral atherosclerosis and aneurysm | |
| | 99 | Cerebrovascular disease, unspecified | |
| | 103 | Cerebrovascular disease late effects, unspecified | |
| | 104 | Vascular disease with complications | x |
| | 105 | Vascular disease | x |

| Label | Pope et al. CCs | Description* | Not adjusted for if only present on index admission (complication) |
|-------|-----------------|--------------------------------------------------------------|------------------------------------------------------|
| | 106 | Other circulatory disease | x |
| | 92, 93 | **Specified arrhythmias** | |
| rf24 | 92 | Specified heart arrhythmias | |
| | 93 | Other heart rhythm and conduction disorders | |
| rf26 | 108 | **Chronic obstructive pulmonary disease** | |
| rf27 | 109 | **Fibrosis of lung or other chronic lung disorders** | |
| rf29 | 130 | **Dialysis Status** | x |
| | 148-149 | **Ulcers** | |
| rf30 | 148 | Decubitus ulcer | x |
| | 149 | Decubitus ulcer or chronic skin ulcer | |
| rf31 | 2 | **Septicemia/shock** | x |
| | 22-23 | **Disorders of fluid, electrolyte, acid-base** | |
| rf32 | 22 | Other significant endocrine and metabolic disorders | x |
| | 23 | Disorders of fluid/electrolyte/acid-base | x |
| rf33 | 47 | **Iron deficiency** | x |
| rf34 | 79 | **Cardio-respiratory failure or cardio-respiratory shock** | x |
| rf39 | 131 | **Acute Renal failure** | x |
| rf40 | 32 | **Pancreatic disease** | |
| rf41 | 38 | **Rheumatoid arthritis and inflammatory connective tissue disease** | |
| rf42 | 77 | **Respirator dependence/tracheostomy status** | |
| | 128, 174 | **Transplants** | |
| rf43 | 128 | Kidney transplant status | |
| | 174 | Major organ transplant status | |
| rf44 | 46 | **Coagulation defects and other specified hematological disorders** | |
| rf45 | 158 | **Hip fracture/dislocation** | |
