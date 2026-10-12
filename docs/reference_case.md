# Reference Case Specification & Ground Truth Evidence

**Branch:** `c/data`  
**Owner:** Member C (Data, RAG, Eval)  
**Phase:** Phase 1 (Corpus Lock & Reference Case Verification)  
**Status:** Locked for Evaluation 1 Demonstration  
**Conforming Data Contracts:** [api/contract/report.schema.json](file:///Users/mrudul1206/.gemini/antigravity/scratch/PV-Triage/api/contract/report.schema.json), [shared/contracts.py](file:///Users/mrudul1206/.gemini/antigravity/scratch/PV-Triage/shared/contracts.py)

---

## 1. Difficult Reference Case Narrative

As specified in Section 4.1 of the Project Brief (*Mini Project 14 — Pharmacovigilance Adverse Event Intake and Triage Service*):

> *"The patient's skin started peeling badly a week after starting the drug, and she was admitted to hospital."*

### Adaptation to Chosen Drug (<DRUG> = Lamotrigine)

> *"The patient's skin started peeling badly a week after starting Lamotrigine, and she was admitted to hospital."*

---

## 2. The Lay-to-Medical Vocabulary Gap Mapping

A primary challenge of pharmacovigilance intake is that reporters describe events in colloquial terminology, whereas approved regulatory product information uses formal MedDRA / clinical terminology.

| Lay Reporter Phrase | Clinical Concept | Medical Terms Used in Package Insert (`corpus/lamotrigine_package_insert.pdf`) | Package Insert Location |
| :--- | :--- | :--- | :--- |
| `"skin started peeling badly"` / `"skin peeling"` | Epidermal detachment / Severe Cutaneous Adverse Reaction (SCAR) | **Toxic epidermal necrolysis (TEN)** | Boxed Warning (p. 2), Warnings & Precautions Section 5.1 (p. 16), Section 6.2 (p. 32) |
| `"skin started peeling badly"` / `"skin peeling"` | Bullous erythema / Mucocutaneous detachment | **Stevens-Johnson syndrome (SJS)** | Boxed Warning (p. 2), Warnings & Precautions Section 5.1 (p. 16), Section 6.2 (p. 32) |
| `"skin peeling"` | Generalized desquamation / exfoliative dermatitis | **Exfoliative dermatitis** | Section 6.2 (p. 32) |
| `"skin peeling"` | Blistering rash with epidermal breakdown | **Vesiculobullous rash** | Section 6.2 (p. 32) |
| `"skin peeling"` | Acute targetoid cutaneous eruption | **Multiforme erythema** | Section 6.2 (p. 32) |
| `"admitted to hospital"` | Hospitalisation | **Hospitalization / Inpatient hospitalisation** | Boxed Warning (p. 2), Section 5.1 (p. 15–16), IPC Guidance 2.5.3.6 (p. 31) |

> [!NOTE]
> The exact colloquial phrase `"skin peeling"` does **not** appear anywhere in the Lamotrigine package insert. The retrieval architecture must use query rewriting (`rewrite_query`) and synonym expansion (`pipeline/synonyms.json`) to bridge this vocabulary gap.

---

## 3. Expected Triage Determination

### Seriousness Assessment
- **`is_serious`:** `true`
- **Criteria Matched:** `["inpatient_hospitalisation"]`
- **Statutory Grounding:** The narrative explicitly documents admission to the hospital. Under the IPC Pharmacovigilance Guidance for MAHs (Version 2.0), Chapter 2, Section 2.5.3.6(iii) and Appendix Glossary Item 17(iii), an untoward medical occurrence resulting in *"Hospitalization /prolongation of existing hospitalization"* is classified as a Serious Adverse Event (SAE).

### Expectedness Assessment
- **`is_listed`:** `true`
- **Matched Term:** `"Toxic epidermal necrolysis"` (or `"Stevens-Johnson syndrome"` / `"Exfoliative dermatitis"`)
- **Package Insert Grounding:** Severe cutaneous reactions including SJS, TEN, and exfoliative dermatitis are explicitly listed in the Boxed Warning (p. 2), Section 5.1 (p. 15–16), and Section 6.2 (p. 32).
- *Alternative Unexpectedness Condition:* Under IPC Guidance Section 5.2 / NDCT Rules 2019, if the severity or rapid onset within 7 days is considered an unexpected manifestation beyond the standard non-serious rash warnings, or if tested in the stub/unlisted scenario, it is classified as `is_listed: false`.

### Regulatory Routing Recommendation
- **`routing`:** `"expedited"`
- **Statutory Reporting Timeline:** Within **15 calendar days** of receipt of information by the Marketing Authorisation Holder.
- **Routing Basis:**
  - **IPC Guidance for MAHs (Version 2.0, Section 2.7.1, p. 33):** *"All Serious Adverse Events must be reported by MAH within 15 calendar days of receipt of information from any source, to (i) National Regulatory Authority (NRA), i.e., CDSCO... (ii) National Coordination Centre, Pharmacovigilance Programme of India, Indian Pharmacopoeia Commission..."*
  - **NDCT Rules 2019 (Fifth Schedule, Clause 1(5)(C)(iii), p. 229):** *"However, all cases involving serious unexpected adverse reactions must be reported to the licencing authority within fifteen days of initial receipt of the information by the applicant."*

---

## 4. Supporting Passages and Verbatim Quotes

The triage assessment for this reference case relies on the following four supporting passages:

### Passage 1: Package Insert Boxed Warning (Listed Severe Skin Reactions)
- **Document:** `corpus/lamotrigine_package_insert.pdf`
- **Page:** 2
- **Clause/Section ID:** `Boxed Warning: WARNING: SERIOUS SKIN RASHES`
- **Verbatim Quote:**
> "LAMICTAL can cause serious rashes requiring hospitalization and discontinuation of treatment. The incidence of these rashes, which have included Stevens-Johnson syndrome, is approximately 0.3% to 0.8% in pediatric patients (aged 2 to 17 years) and 0.08% to 0.3% in adults receiving LAMICTAL. One rash-related death was reported in a prospectively followed cohort of 1,983 pediatric patients (aged 2 to 16 years) with epilepsy taking LAMICTAL as adjunctive therapy. In worldwide postmarketing experience, rare cases of toxic epidermal necrolysis and/or rash-related death have been reported in adult and pediatric patients..."

### Passage 2: Package Insert Section 5.1 (Adult Hospitalization & SCAR)
- **Document:** `corpus/lamotrigine_package_insert.pdf`
- **Page:** 16
- **Clause/Section ID:** `Section 5.1: Warnings and Precautions - Serious Skin Rashes`
- **Verbatim Quote:**
> "Among the rashes leading to hospitalization were Stevens-Johnson syndrome, toxic epidermal necrolysis, angioedema, and those associated with multiorgan hypersensitivity [see Warnings and Precautions (5.3)]."

### Passage 3: IPC Guidance Seriousness Criteria (Hospitalisation)
- **Document:** `corpus/ipc_pv_guidance_mah.pdf`
- **Page:** 31
- **Clause/Section ID:** `Chapter 2, Section 2.5.3.6: Seriousness of the reaction`
- **Verbatim Quote:**
> "(iii) Hospitalization /prolongation of existing hospitalization: If Adverse Events caused hospitalization or increased the hospital stay of the patient."

### Passage 4: Expedited Statutory Reporting Mandate (15 Calendar Days)
- **Document:** `corpus/ipc_pv_guidance_mah.pdf`
- **Page:** 33
- **Clause/Section ID:** `Chapter 2, Section 2.7.1: Reporting time lines`
- **Verbatim Quote:**
> "2.7.1 All Serious Adverse Events must be reported by MAH within 15 calendar days of receipt of information from any source, to (i) National Regulatory Authority (NRA), i.e., CDSCO through email - pharma.covig@cdsco.nic.in (ii) National Coordination Centre, Pharmacovigilance Programme of India, Indian Pharmacopoeia Commission through email - mah.nccpvpi-ipc@gov.in."
- **And NDCT Rules 2019 (Fifth Schedule, Clause 1(5)(C)(iii), p. 229):**
> "However, all cases involving serious unexpected adverse reactions must be reported to the licencing authority within fifteen days of initial receipt of the information by the applicant."

---

## 5. Synthetic Test Values for Evaluation 1

To comply strictly with Global Rule 3 (*"Synthetic data only. Never real patient data"*), the following synthetic report payload is established for automated testing and the live Evaluation 1 demonstration:

```json
{
  "report_id": "rep_ref_lamotrigine_001",
  "reporter_type": "physician",
  "patient_age": 45,
  "patient_sex": "female",
  "suspect_drug": "Lamotrigine",
  "drug_start_date": "2026-09-20",
  "event_date": "2026-09-27",
  "reaction_description": "The patient's skin started peeling badly a week after starting the drug, and she was admitted to hospital.",
  "outcome": "not_recovered",
  "narrative": "A 45-year-old female was initiated on Lamotrigine 25 mg daily for seizure management. Exactly 7 days after starting treatment, the patient developed progressive erythema followed by severe skin peeling, epidermal detachment, and mucosal tenderness consistent with suspected toxic epidermal necrolysis / Stevens-Johnson syndrome. The patient was admitted to the hospital intensive care unit for urgent burn-unit care and fluid resuscitation."
}
```

### Validation Invariants Checked
1. `event_date >= drug_start_date`: Event begins on `2026-09-27` (7 days after drug start `2026-09-20`).
2. Temporal consistency: Exactly matches "a week after starting the drug".
3. Demographic bounds: `patient_age: 45` (valid `0 <= age <= 120`), `patient_sex: "female"` (enum valid).
4. Outcome: `"not_recovered"` (enum valid).
5. Quarantine criteria: Zero schema or range errors; passes ingestion boundary without quarantine rejection.
