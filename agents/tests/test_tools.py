"""agents/tests/test_tools.py - Unit tests for agent tools and MockRetriever."""

from agents.tools import (
    MockRetriever,
    get_clause,
    get_request_fields,
    rewrite_query,
    search_corpus,
)
from shared.contracts import Passage, Retriever


def test_mock_retriever_implements_protocol():
    """Verify MockRetriever satisfies the Retriever protocol."""
    retriever = MockRetriever()
    assert isinstance(retriever, Retriever)


def test_search_corpus():
    """Verify corpus search returns Passage objects."""
    passages = search_corpus("Lamotrigine adverse reaction")
    assert isinstance(passages, list)
    assert len(passages) > 0
    assert all(isinstance(p, Passage) for p in passages)
    assert any("lamotrigine" in p.id.lower() or "ndct" in p.id.lower() for p in passages)


def test_get_clause():
    """Verify exact clause lookup."""
    passage = get_clause("ndct-2019-second-sched-table1")
    assert passage is not None
    assert passage.id == "ndct-2019-second-sched-table1"
    assert "fifteen calendar days" in passage.text

    missing = get_clause("unknown-clause-999")
    assert missing is None


def test_get_request_fields():
    """Verify request field extraction."""
    report = {
        "report_id": "rep_123",
        "suspect_drug": "Lamotrigine",
        "patient_age": 42,
        "reaction_description": "Severe skin peeling",
        "outcome": "not_recovered",
    }
    fields = get_request_fields("rep_123", report)
    assert fields["run_id"] == "rep_123"
    assert fields["suspect_drug"] == "Lamotrigine"
    assert fields["reaction_description"] == "Severe skin peeling"


def test_rewrite_query():
    """Verify lay terms rewrite to candidate medical terms."""
    terms = rewrite_query("Patient skin started peeling and blistering badly")
    assert isinstance(terms, list)
    assert any("necrolysis" in t.lower() or "stevens-johnson" in t.lower() for t in terms)
