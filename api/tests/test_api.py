"""api/tests/test_api.py - Unit and integration tests for API boundary and validation."""

from datetime import date, timedelta
import pytest
from pydantic import ValidationError
from api.models import AdverseEventReport, Outcome, PatientSex, ReporterType
from shared.contracts import RunResult
from worker.placeholder import run_graph


def test_valid_report_model():
    """Verify that a compliant report passes validation."""
    today = date.today()
    report = AdverseEventReport(
        report_id="rep_test_001",
        reporter_type=ReporterType.PHYSICIAN,
        patient_age=45,
        patient_sex=PatientSex.FEMALE,
        suspect_drug="Lamotrigine",
        drug_start_date=today - timedelta(days=14),
        event_date=today - timedelta(days=7),
        reaction_description="Severe epidermal necrolysis with extensive peeling",
        outcome=Outcome.NOT_RECOVERED,
        narrative="Patient admitted to burn unit.",
    )
    assert report.report_id == "rep_test_001"
    assert report.patient_age == 45
    assert report.suspect_drug == "Lamotrigine"


def test_invalid_age_rejected():
    """Verify patient_age > 120 is rejected."""
    today = date.today()
    with pytest.raises(ValidationError) as exc:
        AdverseEventReport(
            reporter_type=ReporterType.PHYSICIAN,
            patient_age=150,
            patient_sex=PatientSex.MALE,
            suspect_drug="Aspirin",
            drug_start_date=today - timedelta(days=5),
            event_date=today,
            reaction_description="Rash",
            outcome=Outcome.RECOVERED,
        )
    assert "less_than_equal" in str(exc.value)


def test_cross_field_dates_rejected():
    """Verify event_date before drug_start_date is rejected."""
    today = date.today()
    with pytest.raises(ValidationError) as exc:
        AdverseEventReport(
            reporter_type=ReporterType.PATIENT,
            patient_sex=PatientSex.FEMALE,
            suspect_drug="Amoxicillin",
            drug_start_date=today - timedelta(days=3),
            event_date=today - timedelta(days=10),  # Prior to drug intake!
            reaction_description="Hives and facial swelling",
            outcome=Outcome.RECOVERING,
        )
    assert "event_date" in str(exc.value)
    assert "must be on or after drug_start_date" in str(exc.value)


def test_future_dates_rejected():
    """Verify dates in the future are rejected."""
    today = date.today()
    with pytest.raises(ValidationError) as exc:
        AdverseEventReport(
            reporter_type=ReporterType.PHARMACIST,
            patient_sex=PatientSex.MALE,
            suspect_drug="Warfarin",
            drug_start_date=today + timedelta(days=2),  # Future date!
            event_date=today + timedelta(days=3),
            reaction_description="Bleeding",
            outcome=Outcome.NOT_RECOVERED,
        )
    assert "cannot be in the future" in str(exc.value)


def test_empty_reaction_description_rejected():
    """Verify whitespace-only reaction description is rejected."""
    today = date.today()
    with pytest.raises(ValidationError) as exc:
        AdverseEventReport(
            reporter_type=ReporterType.PHYSICIAN,
            patient_sex=PatientSex.OTHER,
            suspect_drug="Carbamazepine",
            drug_start_date=today - timedelta(days=5),
            event_date=today - timedelta(days=2),
            reaction_description="    ",
            outcome=Outcome.UNKNOWN,
        )
    assert "reaction_description" in str(exc.value)


def test_placeholder_returns_valid_run_result():
    """Verify that worker/placeholder.py returns a valid RunResult instance."""
    report_dict = {
        "suspect_drug": "Lamotrigine",
        "reaction_description": "Skin peeling",
    }
    result = run_graph(report_dict, "run_unit_001")
    assert isinstance(result, RunResult)
    assert result.status == "completed"
    assert result.routing == "expedited"
    assert result.seriousness.is_serious is True
    assert len(result.citations) > 0
    assert len(result.tool_calls) > 0
    assert len(result.trace) > 0
    # Validate through Pydantic v2
    validated = RunResult.model_validate(result.model_dump())
    assert validated.run_id == "run_unit_001"
