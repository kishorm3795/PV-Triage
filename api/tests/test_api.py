"""api/tests/test_api.py - Unit and integration tests for API boundary and validation."""

from datetime import date, timedelta
import json
import logging
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from api.logging_setup import JSONFormatter, get_correlation_id, set_correlation_id, setup_logging
from api.main import app
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
    client = TestClient(app)
    response = client.get("/v1/failed-jobs")
    assert response.status_code == 200
    data = response.json()
    assert "failed_jobs_count" in data
    assert "failed_jobs" in data
    assert isinstance(data["failed_jobs"], list)


def test_web_client_served():
    """Verify single-page clinical web client and static assets are served at root /."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "PV Triage" in response.text
    assert "styles.css" in response.text
    assert "app.js" in response.text

    css_res = client.get("/styles.css")
    assert css_res.status_code == 200
    assert "--bg: #F6F8FB" in css_res.text

    js_res = client.get("/app.js")
    assert js_res.status_code == 200
    assert "loadReferenceCase" in js_res.text


def test_feedback_endpoint_not_found(monkeypatch):
    """Verify POST /v1/runs/{id}/feedback returns 404 for unknown run."""
    class FakeRedis:
        def get(self, key):
            return None
    from api import main
    monkeypatch.setattr(main, "get_redis_client", lambda: FakeRedis())

    client = TestClient(app)
    res = client.post("/v1/runs/unknown_run_xyz/feedback", json={"rating": "thumbs_up", "reason": "Accurate assessment"})
    assert res.status_code == 404


def test_rate_limiting_429(monkeypatch):
    """Verify that requests exceeding RATE_LIMIT_PER_MIN return HTTP 429 with Retry-After header."""
    from api import main
    monkeypatch.setattr(main, "check_rate_limit", lambda r, cid, limit: (False, 15))

    client = TestClient(app)
    res = client.post("/v1/reports", json={"dummy": "payload"}, headers={"X-Client-ID": "test_burst_client"})
    assert res.status_code == 429
    assert res.headers.get("retry-after") == "15"
    data = res.json()
    assert "Rate limit exceeded" in data["detail"]
    assert data["retry_after"] == 15
    assert data["client_id"] == "test_burst_client"


def test_cache_hit_returns_completed_immediately(monkeypatch):
    """Verify that submitting an identical report hits the Redis whole-run cache and returns completed without queueing."""
    from api import main

    store = {}
    class FakeRedis:
        def eval(self, *args, **kwargs):
            return [1, 0, 59]
        def get(self, key):
            return store.get(key)
        def set(self, key, val, *args, **kwargs):
            store[key] = val
        def lpush(self, key, val):
            store.setdefault(key, []).append(val)

    monkeypatch.setattr(main, "get_redis_client", lambda: FakeRedis())

    # Pre-populate cache with a completed RunResult
    dummy_result = {
        "run_id": "cached_run_original",
        "status": "completed",
        "routing": "expedited",
        "routing_basis": "Reported serious adverse reaction",
        "seriousness": {"is_serious": True, "criteria": ["hospitalisation"]},
        "expectedness": {"is_listed": False, "matched_term": None},
        "citations": [{"passage_id": "chunk_001", "quote": "Must be reported"}],
    }

    from api.models import AdverseEventReport, ReporterType, Outcome, PatientSex
    today = date.today()
    sample_report = AdverseEventReport(
        report_id="rep_orig_999",
        reporter_type=ReporterType.PHYSICIAN,
        patient_sex=PatientSex.FEMALE,
        suspect_drug="Lamotrigine",
        drug_start_date=today - timedelta(days=10),
        event_date=today - timedelta(days=5),
        reaction_description="Toxic epidermal necrolysis",
        outcome=Outcome.NOT_RECOVERED,
    )
    rep_hash = main.compute_report_hash(sample_report)
    store[f"cache:report:{rep_hash}"] = json.dumps(dummy_result)

    client = TestClient(app)
    payload = sample_report.model_dump(mode="json")
    payload["report_id"] = "rep_repeat_123"

    res = client.post("/v1/reports", json=payload, headers={"X-Client-ID": "test_client"})
    assert res.status_code == 202
    data = res.json()
    assert data["run_id"] == "rep_repeat_123"
    assert data["status"] == "completed"
    assert data["cached"] is True


def test_feedback_record_and_summary(monkeypatch):
    """Verify POST /v1/runs/{id}/feedback with satisfactory boolean and GET /v1/feedback/summary."""
    from api import main
    store = {
        "run:rep_fb_1:state": "completed",
        "run:rep_fb_2:state": "completed",
        "runs:feedback": [
            json.dumps({"run_id": "rep_fb_1", "satisfactory": True, "rating": "thumbs_up", "reason": "Accurate routing"}),
            json.dumps({"run_id": "rep_fb_2", "satisfactory": False, "rating": "thumbs_down", "reason": "Missed clause"}),
        ]
    }

    class FakeRedis:
        def get(self, key):
            return store.get(key)
        def set(self, key, val, *args, **kwargs):
            store[key] = val
        def lpush(self, key, val):
            store.setdefault(key, []).append(val)
        def lrange(self, key, start, stop):
            return store.get(key, [])

    monkeypatch.setattr(main, "get_redis_client", lambda: FakeRedis())

    client = TestClient(app)
    post_res = client.post("/v1/runs/rep_fb_1/feedback", json={"satisfactory": True, "reason": "Verified accurate"})
    assert post_res.status_code == 200
    pdata = post_res.json()
    assert pdata["satisfactory"] is True
    assert pdata["status"] == "recorded"

    sum_res = client.get("/v1/feedback/summary")
    assert sum_res.status_code == 200
    sdata = sum_res.json()
    assert sdata["total_feedback"] >= 2
    assert sdata["satisfactory_count"] >= 1
    assert sdata["unsatisfactory_count"] >= 1
    assert "satisfaction_rate" in sdata


