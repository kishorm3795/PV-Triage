# Adverse Event Report Data Contract

This folder documents the formal data contract for adverse event intake via `POST /v1/reports`.
The JSON Schema definition is exported in [`report.schema.json`](./report.schema.json).

---

## 1. Field Specification Table

| Field Name | Type | Required | Constraints / Allowed Values | Description |
| :--- | :--- | :---: | :--- | :--- |
| `report_id` | `string` | No (auto-gen) | Length: 1–64 characters | Unique report identifier (auto-generated if omitted). |
| `reporter_type` | `string` (enum) | **Yes** | `physician`, `pharmacist`, `other_hcp`, `consumer`, `patient` | Qualification/role of the reporter. |
| `patient_age` | `integer` | No | `0 <= patient_age <= 120` | Patient age in years at reaction onset. |
| `patient_sex` | `string` (enum) | **Yes** | `male`, `female`, `other`, `unknown` | Patient biological sex or classification. |
| `suspect_drug` | `string` | **Yes** | Length: 1–200 characters | Name of the suspect active drug substance. |
| `drug_start_date` | `string` (date) | **Yes** | Format: `YYYY-MM-DD`, cannot be in the future | Date the patient started the suspect drug. |
| `event_date` | `string` (date) | **Yes** | Format: `YYYY-MM-DD`, cannot be in the future | Date of adverse reaction onset. |
| `reaction_description` | `string` | **Yes** | Length: 1–2000 characters, non-empty | Free-text description of the adverse reaction. |
| `outcome` | `string` (enum) | **Yes** | `recovered`, `recovering`, `not_recovered`, `fatal`, `unknown`, `recovered_with_sequelae` | Clinical outcome of the reaction. |
| `narrative` | `string` | No | Max length: 5000 characters | Optional clinical narrative, notes, or history. |

---

## 2. Validation Rules

1. **Strict Field Whitelist (`extra="forbid"`)**: Any unrecognized fields in the request body cause immediate validation failure.
2. **Age Range**: When provided, `patient_age` must be an integer between 0 and 120 inclusive.
3. **Temporal Consistency (Cross-field)**:
   - `drug_start_date` must not be in the future (`<= today`).
   - `event_date` must not be in the future (`<= today`).
   - `event_date >= drug_start_date` (adverse event cannot begin before drug intake).
4. **Non-Empty Reaction**: `reaction_description` must contain non-whitespace text up to 2000 characters.
5. **Categorical Enforcement**: `reporter_type`, `patient_sex`, and `outcome` must exactly match the allowed enum strings.

---

## 3. Valid Report Example

### Request Body (`POST /v1/reports`)
```json
{
  "report_id": "rep_ref_case_001",
  "reporter_type": "physician",
  "patient_age": 42,
  "patient_sex": "female",
  "suspect_drug": "Lamotrigine",
  "drug_start_date": "2026-09-01",
  "event_date": "2026-09-08",
  "reaction_description": "The patient's skin started peeling badly a week after starting the drug, and she was admitted to hospital.",
  "outcome": "not_recovered",
  "narrative": "Patient initiated on 25mg daily. Developed widespread epidermal blistering and peeling involving >30% body surface area. Admitted to the ICU burn unit."
}
```

### Response (`HTTP 202 Accepted`)
```json
{
  "run_id": "rep_ref_case_001",
  "status": "queued",
  "message": "Report validated successfully and enqueued for triage assessment."
}
```

---

## 4. Invalid Report Example (Quarantined)

### Request Body (`POST /v1/reports`)
```json
{
  "report_id": "rep_invalid_001",
  "reporter_type": "dentist",
  "patient_age": 150,
  "patient_sex": "unknown",
  "suspect_drug": "Lamotrigine",
  "drug_start_date": "2026-10-01",
  "event_date": "2026-09-20",
  "reaction_description": "   ",
  "outcome": "healed"
}
```

### Errors Triggered
- `reporter_type`: `'dentist'` is not one of `['physician', 'pharmacist', 'other_hcp', 'consumer', 'patient']`
- `patient_age`: `150` exceeds maximum allowed value `120`
- `reaction_description`: empty/whitespace-only string
- `outcome`: `'healed'` is not one of allowed enum values
- `event_date`: `2026-09-20` is earlier than `drug_start_date` (`2026-10-01`)

### Response (`HTTP 422 Unprocessable Entity`)
```json
{
  "detail": [
    {
      "loc": ["body", "reporter_type"],
      "msg": "Input should be 'physician', 'pharmacist', 'other_hcp', 'consumer' or 'patient'",
      "type": "enum"
    },
    {
      "loc": ["body", "patient_age"],
      "msg": "Input should be less than or equal to 120",
      "type": "less_than_equal"
    },
    {
      "loc": ["body", "reaction_description"],
      "msg": "Value error, reaction_description cannot be empty or purely whitespace",
      "type": "value_error"
    },
    {
      "loc": ["body", "outcome"],
      "msg": "Input should be 'recovered', 'recovering', 'not_recovered', 'fatal', 'unknown' or 'recovered_with_sequelae'",
      "type": "enum"
    },
    {
      "loc": ["body"],
      "msg": "Value error, event_date (2026-09-20) must be on or after drug_start_date (2026-10-01)",
      "type": "value_error"
    }
  ],
  "quarantined": true,
  "quarantine_id": "rep_invalid_001"
}
```
*(The rejected report is stored in the quarantine repository with field errors; nothing is enqueued to Redis.)*
