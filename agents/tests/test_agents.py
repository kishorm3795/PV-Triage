"""agents/tests/test_agents.py - Unit tests for LangGraph triage workflow execution."""

from unittest.mock import patch
import pytest

from agents.run import run_graph
from shared.contracts import RunResult


@pytest.fixture(autouse=True)
def mock_llm_response():
    """Mock the LLMClient response for deterministic local unit testing."""
    with patch("llm.client.requests.post") as mock_post:
        mock_resp = mock_post.return_value
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "text": (
                "The patient experienced toxic epidermal necrolysis 7 days after starting "
                "Lamotrigine, resulting in inpatient hospitalization. This meets statutory "
                "seriousness criteria under IPC Pharmacovigilance Guidance. Since it is an "
                "unexpected severe adverse reaction not listed in the package insert, expedited "
                "15-day reporting is recommended under NDCT Rules 2019."
            ),
            "prompt_tokens": 150,
            "completion_tokens": 65,
            "latency_ms": 35.0,
            "model": "stub-llm",
        }
        yield mock_post


def test_run_graph_reference_case():
    """Verify run_graph produces a fully validated RunResult for the reference case."""
    report = {
        "report_id": "rep_test_ref_001",
        "reporter_type": "physician",
        "patient_age": 45,
        "patient_sex": "female",
        "suspect_drug": "Lamotrigine",
        "drug_start_date": "2026-09-20",
        "event_date": "2026-09-27",
        "reaction_description": "Severe skin peeling with widespread blistering and epidermal necrolysis",
        "outcome": "not_recovered",
        "narrative": "Patient admitted to burn intensive care unit for inpatient hospitalization.",
    }

    result = run_graph(report, "run_ref_001")

    # 1. Type and contract validation
    assert isinstance(result, RunResult)
    validated = RunResult.model_validate(result.model_dump())
    assert validated.run_id == "run_ref_001"

    # 2. Status and routing
    assert result.status == "completed"
    assert result.routing == "expedited"
    assert "Expedited 15-day" in result.routing_basis

    # 3. Seriousness and Expectedness
    assert result.seriousness.is_serious is True
    assert "hospitalisation" in result.seriousness.criteria
    assert result.expectedness.is_listed is False

    # 4. Citations validation
    assert len(result.citations) >= 2
    passage_ids = [c.passage_id for c in result.citations]
    assert "ndct-2019-second-sched-table1" in passage_ids
    assert "ipc-pv-guidance-sec4-seriousness" in passage_ids

    # 5. Prompt versions tracked
    assert "assessor" in result.prompt_versions
    assert "verifier" in result.prompt_versions
    assert result.prompt_versions["assessor"] == "v1"
    assert result.prompt_versions["verifier"] == "v1"

    # 6. Tool calls logged
    assert len(result.tool_calls) >= 3
    tool_names = [tc.tool for tc in result.tool_calls]
    assert "rewrite_query" in tool_names
    assert "search_corpus" in tool_names
    assert "get_clause" in tool_names
    assert all(tc.ok is True for tc in result.tool_calls)

    # 7. Trace steps logged with token and cost accounting
    assert len(result.trace) >= 2
    agents_in_trace = [ts.agent for ts in result.trace]
    assert "assessor" in agents_in_trace
    assert "verifier" in agents_in_trace
    assert all(ts.prompt_tokens > 0 for ts in result.trace)
    assert all(ts.completion_tokens > 0 for ts in result.trace)
    assert all(ts.cost_usd > 0.0 for ts in result.trace)


def test_run_graph_error_handling():
    """Verify run_graph handles unhandled graph exceptions by returning status='failed'."""
    with patch("agents.run.get_graph", side_effect=RuntimeError("Graph engine crashed")):
        result = run_graph({}, "run_fail_001")
        assert isinstance(result, RunResult)
        assert result.status == "failed"
        assert "Execution error: Graph engine crashed" in (result.escalation_reason or "")
