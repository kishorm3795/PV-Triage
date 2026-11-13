"""guardrails/tests/test_output.py - Unit tests for output regulatory boundaries guardrail."""

from unittest.mock import patch, MagicMock
import pytest
from agents.run import reset_graph, run_graph
from guardrails.output import (
    REGULATORY_ACTION_BLOCK_PATTERNS,
    check_output_guardrail,
)


@pytest.mark.parametrize(
    "prohibited_phrase",
    [
        "This report has been submitted to CDSCO.",
        "The adverse event was filed with the regulatory agency.",
        "I have reported this event to the pharmacovigilance centre.",
        "Case report has been sent to national authority.",
        "Approved for filing under 15-day timeline.",
        "Filing completed on 2026-10-01.",
        "Submission complete.",
        "We have submitted the individual case safety report.",
    ],
)
def test_output_guardrail_blocks_final_action(prohibited_phrase):
    """Verify output guardrail blocks any claim asserting a final regulatory filing."""
    res = check_output_guardrail(prohibited_phrase, run_id="run_out_test")
    assert res.passed is False
    assert "claims a final regulatory action" in (res.reason or "")
    assert "System must only provide recommendations" in (res.reason or "")


@pytest.mark.parametrize(
    "compliant_recommendation",
    [
        "Recommended routing: expedited 15-day reporting for qualified person review.",
        "Expedited reporting is recommended under NDCT Rules 2019 Table 1.",
        "Periodic safety update reporting is recommended based on approved package insert.",
        "Recommending human medical review of serious adverse event documentation.",
        "Assessment recommends expedited notification to the marketing authorization holder.",
    ],
)
def test_output_guardrail_allows_recommendations(compliant_recommendation):
    """Verify output guardrail permits valid recommendation language."""
    res = check_output_guardrail(compliant_recommendation, run_id="run_rec_test")
    assert res.passed is True
    assert res.reason is None


def test_run_graph_blocks_submitted_phrasing():
    """Proof: An output-filter test that blocks a 'submitted' phrasing and ends run escalated."""
    from llm.client import _SESSION_POOL
    reset_graph()

    # Mock the LLM to generate prohibited 'has been submitted' phrasing
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "text": "The adverse event report has been submitted to the CDSCO regulatory portal.",
        "prompt_tokens": 120,
        "completion_tokens": 45,
        "latency_ms": 20.0,
        "model": "stub-llm",
    }

    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp

    with patch.object(_SESSION_POOL, 'get_session', return_value=mock_session):
        report = {
            "report_id": "rep_test_output_001",
            "reporter_type": "physician",
            "patient_age": 52,
            "patient_sex": "male",
            "suspect_drug": "Lamotrigine",
            "drug_start_date": "2026-09-01",
            "event_date": "2026-09-10",
            "reaction_description": "Severe skin blistering requiring hospitalization",
            "outcome": "not_recovered",
            "narrative": "Patient admitted with Stevens-Johnson syndrome.",
        }

        result = run_graph(report, "run_test_output_001")

        # 1. Output guardrail must escalate the run
        assert result.status == "escalated"
        assert "Output guardrail blocked" in (result.escalation_reason or "")
        assert "final regulatory action" in (result.escalation_reason or "")

        # 2. Prohibited text is NOT returned (never silently rewritten)
        assert result.routing_basis is None

        # 3. Output guardrail trace step recorded
        out_traces = [ts for ts in result.trace if ts.kind == "output_guardrail"]
        assert len(out_traces) >= 1
        assert out_traces[0].detail["guardrail"]["result"] == "block"
        assert out_traces[0].detail["guardrail"]["name"] == "output_guardrail"
