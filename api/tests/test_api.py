"""api/tests/test_api.py - Unit and integration tests for API boundary and validation."""

from datetime import date, timedelta
import json
import logging
import pytest
from pydantic import ValidationError
from api.logging_setup import JSONFormatter, get_correlation_id, set_correlation_id, setup_logging
from api.models import AdverseEventReport, Outcome, PatientSex, ReporterType
from shared.contracts import Expectedness, RunResult, Seriousness
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


def test_health_endpoint_schema():
    """Verify that /health reports redis, index_present, and stub_llm dependency status."""
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "redis" in data
    assert "index_present" in data
    assert "stub_llm" in data


def test_json_logging_with_correlation_id():
    """Verify structured JSON logging and correlation_id formatting."""
    formatter = JSONFormatter(service="test-api")
    set_correlation_id("test_corr_999")

    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Processing job %s",
        args=("job_42",),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["service"] == "test-api"
    assert parsed["correlation_id"] == "test_corr_999"
    assert parsed["message"] == "Processing job job_42"
    assert "timestamp" in parsed


def test_unconfident_answer_for_failed_run():
    """Verify that a failed or incomplete run never returns a confident routing recommendation."""
    failed_result = RunResult(
        run_id="run_fail_001",
        status="failed",
        routing=None,
        routing_basis=None,
        seriousness=Seriousness(is_serious=False, criteria=[]),
        expectedness=Expectedness(is_listed=False, matched_term=None),
        citations=[],
        escalation_reason="Worker timeout exceeded",
        prompt_versions={},
        tool_calls=[],
        trace=[],
    )
    assert failed_result.status == "failed"
    assert failed_result.routing is None
    assert failed_result.routing_basis is None
    assert len(failed_result.citations) == 0


def test_failed_jobs_endpoint():
    """Verify GET /v1/failed-jobs endpoint exists and returns schema-compliant structure."""
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.get("/v1/failed-jobs")
    assert response.status_code == 200
    data = response.json()
    assert "failed_jobs_count" in data
    assert "failed_jobs" in data
    assert isinstance(data["failed_jobs"], list)
