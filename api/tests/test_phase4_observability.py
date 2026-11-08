"""api/tests/test_phase4_observability.py - Tests for Phase 4 OpenTelemetry, Prometheus metrics, and trace reconstruction."""

import json
import logging
import os
import tempfile
import time
from fastapi.testclient import TestClient
import pytest
from api.logging_setup import JSONFormatter, get_correlation_id, set_correlation_id, setup_logging
from api.main import app, get_redis_client
from shared.contracts import Citation, Expectedness, RunResult, Seriousness, ToolCall, TraceStep
from shared.metrics import (
    ESCALATIONS_TOTAL,
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_TOTAL,
    QUEUE_DEPTH,
    RUN_E2E_DURATION,
    RUN_ERRORS_TOTAL,
    RUNS_BY_STATUS_TOTAL,
    RUNS_THROUGHPUT_TOTAL,
    record_run_e2e_latency,
)
from shared.telemetry import (
    build_and_export_run_trace,
    extract_queries_from_tool_calls,
    extract_retrieved_passage_ids,
    init_tracer,
    persist_trace_sqlite,
)


@pytest.fixture
def sample_run_result() -> RunResult:
    return RunResult(
        run_id="case_obs_001",
        status="completed",
        routing="expedited",
        routing_basis="Life-threatening serious adverse drug experience under 21 CFR 314.80(c)(1)(i)",
        seriousness=Seriousness(is_serious=True, criteria=["life_threatening", "hospitalization"]),
        expectedness=Expectedness(is_listed=False, matched_term=None),
        citations=[
            Citation(passage_id="CHROMA_fda_21cfr314_80_c1i_0", quote="Fifteen-day alert reports"),
            Citation(passage_id="CHROMA_lamictal_sec5_0", quote="Serious skin reactions"),
        ],
        escalation_reason=None,
        prompt_versions={"assessor": "v1", "verifier": "v1"},
        tool_calls=[
            ToolCall(
                step=1,
                tool="rewrite_query",
                input={"lay_text": "Severe blistering skin rash"},
                output_summary="Rewrote to 3 terms: ['toxic epidermal necrolysis', 'Stevens-Johnson syndrome', 'erythema multiforme']",
                latency_ms=25.0,
                ok=True,
            ),
            ToolCall(
                step=2,
                tool="search_regulatory_corpus",
                input={"query": "Stevens-Johnson syndrome 15-day alert", "k": 5},
                output_summary="Retrieved 2 passages: ['CHROMA_fda_21cfr314_80_c1i_0', 'CHROMA_ema_gvp_vi_b1_0']",
                latency_ms=45.0,
                ok=True,
            ),
            ToolCall(
                step=3,
                tool="get_clause",
                input={"clause_id": "21 CFR 314.80(c)(1)(i)"},
                output_summary="Passage(id='CHROMA_fda_21cfr314_80_c1i_0', clause='21 CFR 314.80(c)(1)(i)', source='21 CFR 314.80.pdf')",
                latency_ms=12.0,
                ok=True,
            ),
        ],
        trace=[
            TraceStep(
                step=1,
                agent="assessor",
                kind="query_expansion",
                latency_ms=30.0,
                prompt_tokens=150,
                completion_tokens=40,
                cost_usd=0.0003,
                detail={"action": "rewrite_lay_terms"},
            ),
            TraceStep(
                step=2,
                agent="assessor",
                kind="assessment_generation",
                latency_ms=120.0,
                prompt_tokens=450,
                completion_tokens=110,
                cost_usd=0.0009,
                detail={"action": "draft_triage_assessment", "routing": "expedited"},
            ),
            TraceStep(
                step=3,
                agent="verifier",
                kind="verification_audit",
                latency_ms=20.0,
                prompt_tokens=100,
                completion_tokens=30,
                cost_usd=0.0002,
                detail={
                    "verification_passed": True,
                    "verified_citations": 2,
                    "verification_errors": [],
                },
            ),
        ],
    )


def test_telemetry_extraction_helpers(sample_run_result):
    """Verify query extraction and retrieved passage id extraction from tool calls and citations."""
    queries = extract_queries_from_tool_calls(sample_run_result.tool_calls)
    assert len(queries) >= 3
    assert "Severe blistering skin rash" in queries
    assert "Stevens-Johnson syndrome 15-day alert" in queries
    assert "clause:21 CFR 314.80(c)(1)(i)" in queries

    retrieved_ids = extract_retrieved_passage_ids(
        sample_run_result.tool_calls, sample_run_result.citations
    )
    assert "CHROMA_fda_21cfr314_80_c1i_0" in retrieved_ids
    assert "CHROMA_lamictal_sec5_0" in retrieved_ids
    assert "CHROMA_ema_gvp_vi_b1_0" in retrieved_ids


def test_build_and_export_run_trace_structure(sample_run_result):
    """Verify that build_and_export_run_trace produces a complete audit document with child spans."""
    t0 = time.time()
    t1 = t0 + 0.5
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp_db:
        trace_doc = build_and_export_run_trace(
            run_id="case_obs_001",
            run_result=sample_run_result,
            start_time_epoch=t0,
            finish_time_epoch=t1,
            sqlite_path=tmp_db.name,
        )

        assert trace_doc["run_id"] == "case_obs_001"
        assert trace_doc["correlation_id"] == "case_obs_001"
        assert trace_doc["status"] == "completed"
        assert trace_doc["routing"] == "expedited"
        assert len(trace_doc["queries"]) >= 3
        assert len(trace_doc["retrieved_passage_ids"]) >= 3
        assert trace_doc["prompt_versions"] == {"assessor": "v1", "verifier": "v1"}
        assert len(trace_doc["step_latencies"]) == 3
        assert trace_doc["tokens_and_cost"]["total_prompt_tokens"] == 700
        assert trace_doc["tokens_and_cost"]["total_completion_tokens"] == 180
        assert trace_doc["tokens_and_cost"]["total_tokens"] == 880
        assert trace_doc["verification_outcome"]["passed"] is True
        assert trace_doc["verification_outcome"]["verified_citations"] == 2
        assert len(trace_doc["tool_calls"]) == 3
        assert len(trace_doc["trace"]) == 3


def test_trace_persists_in_sqlite(sample_run_result):
    """Verify SQLite persistence of traces survives worker execution."""
    t0 = time.time()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = tmp_db.name

    try:
        trace_doc = build_and_export_run_trace(
            run_id="case_sqlite_test",
            run_result=sample_run_result,
            start_time_epoch=t0,
            finish_time_epoch=t0 + 0.2,
            sqlite_path=db_path,
        )

        # Read back directly from SQLite
        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT payload FROM traces WHERE run_id = ?", ("case_sqlite_test",))
        row = cur.fetchone()
        conn.close()

        assert row is not None
        saved = json.loads(row[0])
        assert saved["run_id"] == "case_sqlite_test"
        assert saved["status"] == "completed"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_prometheus_metrics_definitions():
    """Verify that all 7 required Prometheus metrics exist and can observe values."""
    # 1. Request latency histogram
    HTTP_REQUEST_DURATION.labels(endpoint="/v1/reports").observe(0.045)

    # 2. End-to-end run latency
    RUN_E2E_DURATION.labels(status="completed").observe(1.25)

    # 3. Error rate
    RUN_ERRORS_TOTAL.labels(error_type="timeout").inc()
    HTTP_REQUESTS_TOTAL.labels(method="POST", endpoint="/v1/reports", status="202").inc()

    # 4. Throughput
    RUNS_THROUGHPUT_TOTAL.labels(status="completed").inc()

    # 5. Queue depth
    QUEUE_DEPTH.set(4)

    # 6. Runs by status
    RUNS_BY_STATUS_TOTAL.labels(status="completed").inc()
    RUNS_BY_STATUS_TOTAL.labels(status="escalated").inc()

    # 7. Escalations
    ESCALATIONS_TOTAL.labels(reason="unverified_citation").inc()


def test_record_run_e2e_latency_helper():
    """Verify that record_run_e2e_latency calculates time delta from queued_at."""
    class DummyRedis:
        def __init__(self):
            import datetime
            past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=3)).isoformat()
            self.data = {"run:dummy_01:queued_at": past}

        def get(self, key):
            return self.data.get(key)

    dummy_r = DummyRedis()
    duration = record_run_e2e_latency(dummy_r, "dummy_01", "completed")
    assert duration is not None
    assert 2.5 <= duration <= 4.5


def test_correlation_id_in_log_formatter():
    """Verify correlation_id (= run_id) formatting across API, worker, and agent-step log lines."""
    setup_logging("test_observability")
    formatter = JSONFormatter(service="worker")

    set_correlation_id("run_corr_alpha")

    # Agent step record
    rec = logging.LogRecord(
        name="agents.graph",
        level=logging.INFO,
        pathname="agents/graph.py",
        lineno=120,
        msg="Assessor step %d executed: %s",
        args=(1, "initial_search"),
        exc_info=None,
    )
    formatted = formatter.format(rec)
    data = json.loads(formatted)

    assert data["service"] == "worker"
    assert data["logger"] == "agents.graph"
    assert data["correlation_id"] == "run_corr_alpha"
    assert "Assessor step 1 executed" in data["message"]


def test_get_run_trace_endpoint(sample_run_result):
    """Verify GET /v1/runs/{run_id}/trace returns all required fields."""
    client = TestClient(app)

    # 1. Non-existent run -> 404
    resp_404 = client.get("/v1/runs/non_existent_999/trace")
    assert resp_404.status_code == 404

    # 2. Existing run seeded into Redis
    r = get_redis_client()
    run_id = "test_trace_endpoint_01"
    trace_doc = build_and_export_run_trace(
        run_id=run_id,
        run_result=sample_run_result,
        start_time_epoch=time.time() - 1.0,
        finish_time_epoch=time.time(),
        redis_client=r,
    )
    r.set(f"run:{run_id}:state", "completed")

    resp = client.get(f"/v1/runs/{run_id}/trace")
    assert resp.status_code == 200
    data = resp.json()

    assert data["run_id"] == run_id
    assert data["correlation_id"] == run_id
    assert data["status"] == "completed"
    assert "queries" in data
    assert "retrieved_passage_ids" in data
    assert "prompt_versions" in data
    assert "step_latencies" in data
    assert "tokens_and_cost" in data
    assert "verification_outcome" in data
    assert "tool_calls" in data
    assert "trace" in data
    assert data["verification_outcome"]["passed"] is True
