"""agents/tests/test_agents.py - Unit tests for LangGraph triage workflow execution."""

from unittest.mock import patch
import pytest

from agents.run import reset_graph, run_graph
from shared.contracts import RunResult


@pytest.fixture(autouse=True)
def mock_llm_response():
    """Mock the LLMClient response for deterministic local unit testing."""
    reset_graph()
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
    """Proof (i): Verify run_graph produces a fully validated RunResult for the reference case."""
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
    assert "Expedited 15-day" in (result.routing_basis or "")

    # 3. Seriousness and Expectedness
    assert result.seriousness.is_serious is True
    assert "hospitalisation" in result.seriousness.criteria
    assert result.expectedness.is_listed is False

    # 4. Citations validation: every cited passage was retrieved & quote is verbatim
    assert len(result.citations) >= 2
    passage_ids = [c.passage_id for c in result.citations]
    assert "ndct-2019-second-sched-table1" in passage_ids
    assert "ipc-pv-guidance-sec4-seriousness" in passage_ids
    for citation in result.citations:
        assert len(citation.quote) > 10

    # 5. Prompt versions tracked
    assert "assessor" in result.prompt_versions
    assert "verifier" in result.prompt_versions
    assert result.prompt_versions["assessor"] == "v1"
    assert result.prompt_versions["verifier"] == "v1"

    # 6. Tool calls logged
    assert len(result.tool_calls) >= 4
    tool_names = [tc.tool for tc in result.tool_calls]
    assert "get_request_fields" in tool_names
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


def test_run_graph_out_of_corpus_drug_escalates():
    """Proof (ii): Verify an out-of-corpus suspect drug immediately escalates with clear reason."""
    report = {
        "report_id": "rep_test_ooc_001",
        "reporter_type": "physician",
        "patient_age": 52,
        "patient_sex": "male",
        "suspect_drug": "Metformin",
        "drug_start_date": "2026-09-01",
        "event_date": "2026-09-15",
        "reaction_description": "Severe lactic acidosis and hypoglycemia",
        "outcome": "recovered",
        "narrative": "Patient on Metformin developed lactic acidosis requiring emergency care.",
    }

    result = run_graph(report, "run_ooc_001")
    assert isinstance(result, RunResult)
    assert result.status == "escalated"
    assert "outside the approved regulatory corpus" in (result.escalation_reason or "")
    assert "Metformin" in (result.escalation_reason or "")


def test_run_graph_forced_unsupported_citation_caught_by_verifier():
    """Proof (iii): A deliberately forced unsupported citation is caught by Verifier and escalates."""
    report = {
        "report_id": "rep_test_unsupported_001",
        "reporter_type": "physician",
        "patient_age": 30,
        "patient_sex": "female",
        "suspect_drug": "Lamotrigine",
        "drug_start_date": "2026-09-10",
        "event_date": "2026-09-17",
        "reaction_description": "Severe skin peeling requiring hospital admission",
        "outcome": "not_recovered",
        "narrative": "Patient admitted with skin desquamation.",
        "force_invalid_citation": True,
    }

    result = run_graph(report, "run_unsupported_001")
    assert isinstance(result, RunResult)
    # Verifier must catch the unsupported citation and refuse to complete
    assert result.status == "escalated"
    assert "Verification failed after 2 retries" in (result.escalation_reason or "")


def test_run_graph_missing_dates_escalates():
    """Verify missing dates escalate with timing reason."""
    report = {
        "report_id": "rep_missing_dates",
        "suspect_drug": "Lamotrigine",
        "reaction_description": "Skin peeling and blistering",
        "outcome": "not_recovered",
        # Missing drug_start_date and event_date
    }
    result = run_graph(report, "run_timing_001")
    assert isinstance(result, RunResult)
    assert result.status == "escalated"
    assert "Timing is unclear" in (result.escalation_reason or "")
    assert "missing" in (result.escalation_reason or "")


def test_run_graph_inconsistent_dates_escalates():
    """Verify event_date earlier than drug_start_date escalates with chronological inconsistency reason."""
    report = {
        "report_id": "rep_bad_dates",
        "suspect_drug": "Lamotrigine",
        "drug_start_date": "2026-09-20",
        "event_date": "2026-09-10",  # 10 days before drug started!
        "reaction_description": "Skin peeling and blistering",
        "outcome": "not_recovered",
    }
    result = run_graph(report, "run_timing_002")
    assert isinstance(result, RunResult)
    assert result.status == "escalated"
    assert "precedes drug_start_date" in (result.escalation_reason or "")


def test_run_graph_unmatchable_reaction_escalates():
    """Verify non-clinical reaction description that cannot be matched to package insert escalates."""
    report = {
        "report_id": "rep_unmatchable",
        "suspect_drug": "Lamotrigine",
        "drug_start_date": "2026-09-20",
        "event_date": "2026-09-27",
        "reaction_description": "Patient felt completely funny and weird throughout the evening",
        "outcome": "recovered",
    }
    result = run_graph(report, "run_unmatchable_001")
    assert isinstance(result, RunResult)
    assert result.status == "escalated"
    assert "cannot be matched to the package insert with confidence" in (result.escalation_reason or "")


def test_run_graph_assessor_crash_fails():
    """Task 5: Assessor crash returns status='failed'."""
    report = {
        "report_id": "rep_crash_assessor",
        "suspect_drug": "Lamotrigine",
        "drug_start_date": "2026-09-20",
        "event_date": "2026-09-27",
        "reaction_description": "Skin peeling badly",
    }
    with patch("agents.graph.wrap_tools", side_effect=ZeroDivisionError("Assessor internal fault")):
        result = run_graph(report, "run_crash_001")
        assert isinstance(result, RunResult)
        assert result.status == "failed"
        assert "Assessor crashed" in (result.escalation_reason or "") or "Assessor internal fault" in (result.escalation_reason or "")


def test_run_graph_verifier_crash_escalates():
    """Task 5: Verifier crash returns status='escalated' per Global Rule 6."""
    report = {
        "report_id": "rep_crash_verifier",
        "suspect_drug": "Lamotrigine",
        "drug_start_date": "2026-09-20",
        "event_date": "2026-09-27",
        "reaction_description": "Severe skin peeling with hospital admission",
    }

    def mock_load_prompt(name, *args, **kwargs):
        if name == "verifier":
            raise RuntimeError("Verifier internal audit crashed")
        return ("system prompt", "v1")

    with patch("agents.graph.load_prompt", side_effect=mock_load_prompt):
        result = run_graph(report, "run_crash_002")
        assert isinstance(result, RunResult)
        assert result.status == "escalated"
        assert "Verifier crashed" in (result.escalation_reason or "")


def test_run_graph_error_handling():
    """Verify run_graph handles top-level graph exceptions by returning status='failed'."""
    with patch("agents.run.get_graph", side_effect=RuntimeError("Graph engine crashed")):
        result = run_graph({}, "run_fail_001")
        assert isinstance(result, RunResult)
        assert result.status == "failed"
        assert "Execution error: Graph engine crashed" in (result.escalation_reason or "")


def test_run_graph_max_tool_calls_escalates(monkeypatch):
    """Verify exceeding MAX_TOOL_CALLS immediately escalates with the bound named in reason."""
    monkeypatch.setenv("MAX_TOOL_CALLS", "2")
    report = {
        "report_id": "rep_bound_exceeded",
        "suspect_drug": "Lamotrigine",
        "reaction_description": "Skin peeling and blistering",
        "outcome": "not_recovered",
    }
    result = run_graph(report, "run_bound_001")
    assert isinstance(result, RunResult)
    assert result.status == "escalated"
    assert "MAX_TOOL_CALLS" in (result.escalation_reason or "")
    # Breaching tool call should be captured in tool_calls
    assert len(result.tool_calls) == 3
    assert result.tool_calls[-1].ok is False


def test_run_graph_bounds_step_limit_escalates(monkeypatch):
    """Task 4: Exceeding MAX_STEPS escalates with bound reason."""
    monkeypatch.setenv("MAX_STEPS", "1")
    report = {
        "report_id": "rep_step_bound",
        "suspect_drug": "Lamotrigine",
        "drug_start_date": "2026-09-20",
        "event_date": "2026-09-27",
        "reaction_description": "Skin peeling and blistering admitted to hospital",
    }
    result = run_graph(report, "run_step_bound_001")
    assert isinstance(result, RunResult)
    assert result.status == "escalated"
    assert "MAX_STEPS" in (result.escalation_reason or "")
