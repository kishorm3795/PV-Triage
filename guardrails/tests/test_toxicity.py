"""guardrails/tests/test_toxicity.py - Unit tests for lexical toxicity filters and clinical allowances."""

from unittest.mock import patch
import pytest
from agents.run import reset_graph, run_graph
from guardrails.toxicity import (
    CLINICAL_WHITELIST_TERMS,
    check_toxicity,
)


@pytest.mark.parametrize(
    "clinical_text",
    [
        "Patient experienced toxic epidermal necrolysis with 30% skin detachment.",
        "Severe drug-induced hepatotoxicity leading to acute jaundice.",
        "Accidental overdose with elevated serum drug concentrations.",
        "Patient presented with suicidal ideation following dose escalation.",
        "Extensive necrotic tissue debrided in burn unit.",
        "Severe genital ulceration following drug initiation.",
        "Septic shock and metabolic acidosis observed in intensive care unit.",
    ],
)
def test_toxicity_filter_allows_clinical_language(clinical_text):
    """Confirm genuine clinical adverse event terms are never falsely flagged as toxic."""
    res_in = check_toxicity(clinical_text, is_input=True)
    assert res_in.passed is True
    assert res_in.reason is None

    res_out = check_toxicity(clinical_text, is_input=False)
    assert res_out.passed is True
    assert res_out.reason is None


@pytest.mark.parametrize(
    "abusive_text",
    [
        "This doctor is a worthless scum and should die in a fire.",
        "You f***ing idiot stop processing this.",
        "I will kill you if you escalate this report.",
        "Stupid bitch physician filed inaccurate report.",
    ],
)
def test_toxicity_filter_detects_abusive_patterns(abusive_text):
    """Confirm abusive and threatening inputs are detected."""
    res = check_toxicity(abusive_text, is_input=True, run_id="run_tox_test")
    assert res.passed is False
    assert "Toxic content detected in input report" in (res.reason or "")


def test_run_graph_escalates_on_toxic_input():
    """Proof: Toxic input handled and escalates with clear reason; zero silent processing."""
    reset_graph()

    toxic_report = {
        "report_id": "rep_toxic_001",
        "reporter_type": "physician",
        "patient_age": 35,
        "patient_sex": "male",
        "suspect_drug": "Lamotrigine",
        "drug_start_date": "2026-09-01",
        "event_date": "2026-09-10",
        "reaction_description": "Go die in a fire you worthless scum.",
        "outcome": "not_recovered",
        "narrative": "None",
    }

    result = run_graph(toxic_report, "run_tox_001")

    # 1. Run ends escalated with explicit toxic content reason
    assert result.status == "escalated"
    assert "Toxic content detected in input report" in (result.escalation_reason or "")

    # 2. No tool calls or LLM calls made
    assert len(result.tool_calls) == 0

    # 3. Guardrail trace step recorded
    guardrail_traces = [ts for ts in result.trace if ts.agent == "guardrail"]
    assert len(guardrail_traces) >= 1
    assert guardrail_traces[0].detail["guardrail"]["name"] == "toxicity"
    assert guardrail_traces[0].detail["guardrail"]["result"] == "block"
