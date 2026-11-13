# Corpus Audit & Regulatory Ground Truth

**Branch:** `c/data`  
**Owner:** Member C (Data, RAG, Eval)  
**Phase:** Phase 1 (Corpus Lock & Reference Case Verification)  
**Evaluator Reference:** Evaluation 1 Ground Truth Evidence

---

## 1. Document Inventory and Text Layer Audit

Each source document in `./corpus` was inspected using PyMuPDF (`fitz`) to verify page counts, digital text layer presence, and OCR requirements.

| Document Title | Version / Date | Official Source URL | Page Count | Text Layer Status | OCR Required? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **New Drugs and Clinical Trials Rules, 2019** (Gazette Notification G.S.R. 227(E)) | March 19, 2019 | [CDSCO Gazette Portal](https://cdsco.gov.in/opencms/resources/UploadCDSCOWeb/2018/UploadGazette_NotificationsFiles/gsr227e.pdf) | 264 pages | Digital text layer present across all 264 pages (264/264) | **No** (Direct extraction supported) |
| **Pharmacovigilance Guidance Document for Marketing Authorization Holders of Pharmaceutical Products** | Version 2.0 (September 2024) | [CDSCO Post-Marketing DSM Portal](https://cdsco.gov.in/opencms/resources/UploadCDSCOWeb/2024/PSURFiles/Guidance_Documentpsur2.pdf) | 86 pages | Digital text layer present on 83/86 pages (pages 2, 4, 85 are blank/dividers) | **No** (Direct extraction supported) |
| **LAMICTAL (lamotrigine) Full Prescribing Information** | Revised April 2025 (Reference ID: 5579217) | [FDA CDER Drugs@FDA Database](https://www.accessdata.fda.gov/drugsatfda_docs/label/2025/020241s066s067,020764s059s060,022251s030s031lbl.pdf) | 71 pages | Digital text layer present across all 71 pages (71/71) | **No** (Direct extraction supported) |

---

## 2. Verbatim Regulatory Evidence for the Reference Case

### (a) Package Insert: Listed Severe Skin Reactions

- **Document:** `corpus/lamotrigine_package_insert.pdf` (LAMICTAL Prescribing Information)
- **Section ID:** `Boxed Warning: WARNING: SERIOUS SKIN RASHES`
- **Page Number:** Page 2
- **Verbatim Quote:**
> "WARNING: SERIOUS SKIN RASHES
> LAMICTAL can cause serious rashes requiring hospitalization and discontinuation of treatment. The incidence of these rashes, which have included Stevens-Johnson syndrome, is approximately 0.3% to 0.8% in pediatric patients (aged 2 to 17 years) and 0.08% to 0.3% in adults receiving LAMICTAL. One rash-related death was reported in a prospectively followed cohort of 1,983 pediatric patients (aged 2 to 16 years) with epilepsy taking LAMICTAL as adjunctive therapy. In worldwide postmarketing experience, rare cases of toxic epidermal necrolysis and/or rash-related death have been reported in adult and pediatric patients, but their numbers are too few to permit a precise estimate of the rate. Other than age, there are as yet no factors identified that are known to predict the risk of occurrence or the severity of rash caused by LAMICTAL. There are suggestions, yet to be proven, that the risk of rash may also be increased by (1) coadministration of LAMICTAL with valproate (includes valproic acid and divalproex sodium), (2) exceeding the recommended initial dose of LAMICTAL, or (3) exceeding the recommended dose escalation for LAMICTAL. However, cases have occurred in the absence of these factors. Nearly all cases of life-threatening rashes caused by LAMICTAL have occurred within 2 to 8 weeks of treatment initiation."

- **Document:** `corpus/lamotrigine_package_insert.pdf`
- **Section ID:** `Section 5.1: Warnings and Precautions - Serious Skin Rashes (Adult Population)`
- **Page Number:** Page 16
- **Verbatim Quote:**
> "Serious rash associated with hospitalization and discontinuation of LAMICTAL occurred in 0.3% (11 of 3,348) of adult patients who received LAMICTAL in premarketing clinical trials of epilepsy. In the bipolar and other mood disorders clinical trials, the rate of serious rash was 0.08% (1 of 1,233) of adult patients who received LAMICTAL as initial monotherapy and 0.13% (2 of 1,538) of adult patients who received LAMICTAL as adjunctive therapy. No fatalities occurred among these individuals. However, in worldwide postmarketing experience, rare cases of rash-related death have been reported, but their numbers are too few to permit a precise estimate of the rate.
> Among the rashes leading to hospitalization were Stevens-Johnson syndrome, toxic epidermal necrolysis, angioedema, and those associated with multiorgan hypersensitivity [see Warnings and Precautions (5.3)]."

- **Document:** `corpus/lamotrigine_package_insert.pdf`
- **Section ID:** `Section 6.2: Other Adverse Reactions Observed in All Clinical Trials - Skin and Subcutaneous Tissue Disorders`
- **Page Number:** Page 32
- **Verbatim Quote:**
> "Infrequent: Acne, alopecia, hirsutism, maculopapular rash, skin discoloration, urticaria.
> Rare: Angioedema, erythema, exfoliative dermatitis, fungal dermatitis, herpes zoster, leukoderma, multiforme erythema, petechial rash, pustular rash, Stevens-Johnson syndrome, vesiculobullous rash."

---

### (b) Seriousness Criteria (Inpatient Hospitalisation)

- **Document:** `corpus/ipc_pv_guidance_mah.pdf` (IPC Pharmacovigilance Guidance for MAHs, Version 2.0)
- **Section ID:** `Chapter 2, Section 2.5.3.6: Seriousness of the reaction`
- **Page Number:** Page 31
- **Verbatim Quote:**
> "2.5.3.6 Seriousness of the reaction: If any adverse drug reaction is serious in nature, tick the appropriate reason for seriousness as-
> (i) Death: If, the patient died, mention the cause and date of death.
> (ii) Life-threatening: If, the patient was at substantial risk of dying at the time of Adverse Events.
> (iii) Hospitalization /prolongation of existing hospitalization: If Adverse Events caused hospitalization or increased the hospital stay of the patient."

- **Document:** `corpus/ipc_pv_guidance_mah.pdf`
- **Section ID:** `Appendix Glossary, Item 17: Serious Adverse Event`
- **Page Number:** Page 80
- **Verbatim Quote:**
> "17. Serious Adverse Event
> A serious adverse event or reaction is any untoward medical occurrence at any dose that results in;
> (i) Death
> (ii) Life threatening
> (iii) Hospitalization – Initial/Prolonged
> (iv) Congenital anomaly
> (v) Disability
> (vi) Other medically important Event"

---

### (c) Reporting Provision for Expedited vs. Periodic Reporting

- **Document:** `corpus/ndct_rules_2019.pdf` (New Drugs and Clinical Trials Rules, 2019)
- **Section ID:** `Fifth Schedule, Clause 1(5)(C)(iii): Post marketing surveillance through periodic safety update reports`
- **Page Number:** Pages 228–229
- **Verbatim Quote:**
> "(iii) All relevant clinical and non-clinical safety data should cover only the period of the report (interval data). The periodic safety update reports shall be submitted every six months for the first two years after approval of the drug is granted to the applicant. For subsequent two years – the periodic safety update reports need to be submitted annually. Central Licencing Authority may extend the total duration of submission of periodic safety update reports if it is considered necessary in the interest of public health.
> Periodic safety update reports due for a period must be submitted within thirty calendar days of the last day of the reporting period. However, all cases involving serious unexpected adverse reactions must be reported to the licencing authority within fifteen days of initial receipt of the information by the applicant. If marketing of the new drug is delayed by the applicant after obtaining approval to market, such data will have to be provided on the deferred basis beginning from the time the new drug is marketed."

- **Document:** `corpus/ipc_pv_guidance_mah.pdf` (IPC Guidance for MAHs, Version 2.0)
- **Section ID:** `Chapter 2, Section 2.7: Reporting time lines`
- **Page Number:** Page 33
- **Verbatim Quote:**
> "2.7 Reporting time lines
> 2.7.1 All Serious Adverse Events must be reported by MAH within 15 calendar days of receipt of information from any source, to
> (i) National Regulatory Authority (NRA), i.e., CDSCO through email - pharma.covig@cdsco.nic.in
> (ii) National Coordination Centre, Pharmacovigilance Programme of India, Indian Pharmacopoeia Commission through email - mah.nccpvpi-ipc@gov.in.
> 2.7.2 All Non-Serious Adverse Events must be reported by MAH within 90 calendar days of receipt of information from any source, to
> (i) National Regulatory Authority (NRA), i.e., CDSCO through email – pharma.covig@cdsco.nic.in
> (ii) National Coordination Centre, Pharmacovigilance Programme of India, Indian Pharmacopoeia Commission through email - mah.nccpvpi-ipc@gov.in."

- **Document:** `corpus/ipc_pv_guidance_mah.pdf`
- **Section ID:** `Appendix - E: Frequently Asked Questions (FAQs), Question 5`
- **Page Number:** Page 82
- **Verbatim Quote:**
> "Q.5 What is timeline for the reporting of Serious Unexpected Adverse Reactions to the PvPI & Licensing Authority by the applicant?
> Ans. All Serious Adverse Events should be reported to the PvPI & Licensing Authority within 15 calendar days of initial receipt of the information by the applicant."

---

### (d) Provisions That Modify the Reporting Timeline

- **Document:** `corpus/ndct_rules_2019.pdf`
- **Section ID:** `Fifth Schedule, Clause 1(5)(C)(iii)`
- **Page Number:** Page 229
- **Verbatim Quotes:**
  1. **Expedited 15-day override for serious unexpected events (overrides the 6-month / annual PSUR periodic cycle):**
     > "However, all cases involving serious unexpected adverse reactions must be reported to the licencing authority within fifteen days of initial receipt of the information by the applicant."
  2. **Regulatory extension of PSUR periodic reporting duration:**
     > "Central Licencing Authority may extend the total duration of submission of periodic safety update reports if it is considered necessary in the interest of public health."
  3. **Deferred periodic reporting timeline in case of delayed marketing:**
     > "If marketing of the new drug is delayed by the applicant after obtaining approval to market, such data will have to be provided on the deferred basis beginning from the time the new drug is marketed."

- **Document:** `corpus/ndct_rules_2019.pdf`
- **Section ID:** `Rule 82: Conditions of permission for manufacture of new drug for sale or distribution`
- **Page Number:** Page 176
- **Verbatim Quote:**
> "82. Conditions of permission for manufacture of new drug for sale or distribution.― The permission granted under rule 81 in Form CT-22 or in Form CT-23 shall be subject to following conditions, namely:―
> ...
> (iv) as post marketing surveillance, the applicant shall submit Periodic Safety Update Reports as specified in the Fifth Schedule;
> (v) all reported serious unexpected adverse reactions related to the drug shall be intimated to the Central Licencing Authority and regulatory action resulting from their review shall be complied with;"

---

## 3. Explicit List of Items NOT Found in the Source Documents

In accordance with Global Rule 2 ("Never invent regulatory clauses, deadlines or package-insert text") and Phase 1 instructions, the following items were **not found** in the physical documents:

1. **Second Schedule Table 1 "Clause 4(3)" with 15-day text:**
   - In `agents/tools.py` (MockRetriever), Member B used the passage ID `ndct-2019-second-sched-table1` referencing `Second Schedule, Table 1, Clause 4(3)` on page 218 for a 15-calendar-day MAH reporting rule.
   - **Finding:** In the authentic Gazette notification (`corpus/ndct_rules_2019.pdf`), Second Schedule Table 1 is located on pages 194–200 and covers clinical trial data requirements, not post-marketing MAH reporting timelines. Page 218 contains Table 5 and Investigator Declaration Clause 7(xi), which states a **14-day** investigator reporting requirement.
   - **Ground truth location:** The actual statutory 15-day post-marketing reporting requirement for serious unexpected adverse reactions is located in the **Fifth Schedule, Clause 1(5)(C)(iii)** on **Pages 228–229**, and in IPC Guidance Version 2.0 Section 2.7.1 on **Page 33**.

2. **Literal term "skin peeling" in the package insert:**
   - The verbatim colloquial term `"skin peeling"` or `"skin started peeling badly"` does **not** appear anywhere in `corpus/lamotrigine_package_insert.pdf`.
   - **Finding:** The package insert lists the reaction under medical terminology:
     - `"Toxic epidermal necrolysis"` (TEN) (Boxed Warning, Section 5.1, Section 6.2)
     - `"Stevens-Johnson syndrome"` (SJS) (Boxed Warning, Section 5.1, Section 6.2)
     - `"Exfoliative dermatitis"` (Section 6.2, Page 32)
     - `"Serious skin rashes"` / `"vesiculobullous rash"` (Section 5.1, Section 6.2)
   - This proves the need for the lay-to-medical query rewriter in Phase 2/3.

3. **Statutory grace period / extension for the 15-day expedited reporting timeline:**
   - We searched for any provision permitting an MAH or manufacturer to extend or pause the 15-calendar-day expedited clock (e.g., for incomplete investigations, public holidays, or weekends).
   - **Finding:** No such extension provision exists. Both the NDCT Rules 2019 (Fifth Schedule) and the IPC Guidance for MAHs mandate reporting within 15 calendar days of receipt of initial information. Any lack of initial complete data requires submission of an initial report within 15 days followed by a follow-up report.
