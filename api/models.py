"""api/models.py - Pydantic v2 Adverse Event Report validation models.

Implements strict schema, type, range, categorical (enum), and cross-field
validation as mandated by the Pharmacovigilance Intake Data Contract.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
import uuid
from typing import Self
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PatientSex(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class ReporterType(str, Enum):
    PHYSICIAN = "physician"
    PHARMACIST = "pharmacist"
    OTHER_HCP = "other_hcp"
    CONSUMER = "consumer"
    PATIENT = "patient"


class Outcome(str, Enum):
    RECOVERED = "recovered"
    RECOVERING = "recovering"
    NOT_RECOVERED = "not_recovered"
    FATAL = "fatal"
    UNKNOWN = "unknown"
    RECOVERED_WITH_SEQUELAE = "recovered_with_sequelae"


class AdverseEventReport(BaseModel):
    """Statutory Adverse Event Report input model."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "description": "Adverse drug reaction report submitted to the pharmacovigilance triage service."
        },
    )

    report_id: str = Field(
        default_factory=lambda: f"rep_{uuid.uuid4().hex[:8]}",
        description="Unique report identifier.",
        min_length=1,
        max_length=64,
    )
    reporter_type: ReporterType = Field(
        ...,
        description="Role or profession of the adverse event reporter.",
    )
    patient_age: int | None = Field(
        default=None,
        ge=0,
        le=120,
        description="Patient age in years at reaction onset (0-120).",
    )
    patient_sex: PatientSex = Field(
        ...,
        description="Patient biological sex or gender classification.",
    )
    suspect_drug: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the suspect active drug substance or medicinal product.",
    )
    drug_start_date: date = Field(
        ...,
        description="Date when the patient began taking the suspect drug (YYYY-MM-DD).",
    )
    event_date: date = Field(
        ...,
        description="Date of onset of the adverse event (YYYY-MM-DD).",
    )
    reaction_description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Detailed description of the adverse reaction (max 2000 characters).",
    )
    outcome: Outcome = Field(
        ...,
        description="Clinical outcome of the adverse drug reaction.",
    )
    narrative: str | None = Field(
        default=None,
        max_length=5000,
        description="Optional clinical narrative, laboratory findings, or medical history.",
    )

    @field_validator("reaction_description")
    @classmethod
    def validate_non_empty_reaction(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("reaction_description cannot be empty or purely whitespace")
        return stripped

    @model_validator(mode="after")
    def validate_dates_and_cross_fields(self) -> Self:
        today = date.today()
        # No future dates rule
        if self.drug_start_date > today:
            raise ValueError(
                f"drug_start_date ({self.drug_start_date}) cannot be in the future (today: {today})"
            )
        if self.event_date > today:
            raise ValueError(
                f"event_date ({self.event_date}) cannot be in the future (today: {today})"
            )
        # Temporal consistency rule
        if self.event_date < self.drug_start_date:
            raise ValueError(
                f"event_date ({self.event_date}) must be on or after drug_start_date ({self.drug_start_date})"
            )
        return self
