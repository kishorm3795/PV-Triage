"""agents/tests/test_tools.py - Unit tests for Phase 2 Member B agent tools and retrievers."""

import os
import time
import pytest
from agents.tools import (
    MockRetriever,
    RealRetrieverAdapter,
    ToolCallLimitExceeded,
    ToolTimeoutError,
    clear_run_reports,
    get_clause,
    get_default_retriever,
    get_request_fields,
    make_tool_wrapper,
    register_run_report,
    reset_retriever,
    rewrite_query,
    search_corpus,
    wrap_tools,
)
from shared.contracts import Passage, Retriever, ToolCall


@pytest.fixture(autouse=True)
def cleanup_environment():
    """Ensure clean retriever and registry state for every test."""
    clear_run_reports()
    reset_retriever()
    old_retriever_env = os.environ.get("RETRIEVER")
    yield
    if old_retriever_env is not None:
        os.environ["RETRIEVER"] = old_retriever_env
    else:
        os.environ.pop("RETRIEVER", None)
    reset_retriever()
    clear_run_reports()


# ========================================================================
# Task 1: Retriever Protocol, MockRetriever, RealRetrieverAdapter, Env Switching
# ========================================================================

def test_mock_retriever_implements_protocol():
    """Verify MockRetriever satisfies the frozen Retriever protocol."""
    retriever = MockRetriever()
    assert isinstance(retriever, Retriever)


def test_mock_retriever_search_and_clause():
    """Verify MockRetriever searches correctly and finds exact clauses."""
    retriever = MockRetriever()
    passages = retriever.search("Lamotrigine adverse reaction", k=3)
    assert isinstance(passages, list)
    assert len(passages) <= 3
    assert len(passages) > 0
    assert all(isinstance(p, Passage) for p in passages)

    # Verify score ranking
    scores = [p.score for p in passages if p.score is not None]
    assert scores == sorted(scores, reverse=True)

    # Verify get_clause
    clause = retriever.get_clause("ndct-2019-second-sched-table1")
    assert clause is not None
    assert clause.clause_id == "ndct-2019-second-sched-table1"
    assert "fifteen calendar days" in clause.text

    assert retriever.get_clause("non-existent-clause") is None


def test_real_retriever_adapter_protocol():
    """Verify RealRetrieverAdapter satisfies the Retriever protocol."""
    adapter = RealRetrieverAdapter()
    assert isinstance(adapter, Retriever)


def test_real_retriever_adapter_missing_module():
    """Verify RealRetrieverAdapter raises clear NotImplementedError if pipeline.retrieval is missing."""
    adapter = RealRetrieverAdapter(retrieval_module_path="non_existent_pipeline_module")
    with pytest.raises(NotImplementedError) as exc_info:
        adapter.search("test query")
    assert "RealRetrieverAdapter" in str(exc_info.value)
    assert "non_existent_pipeline_module" in str(exc_info.value)


def test_real_retriever_adapter_with_mocked_pipeline(monkeypatch):
    """Verify RealRetrieverAdapter delegates search/get_clause and normalizes passages."""
    import sys
    from types import ModuleType

    dummy_mod = ModuleType("pipeline.retrieval")

    class DummyRetriever:
        def search(self, query: str, k: int = 5):
            return [
                Passage(
                    id="dummy-1",
                    text=f"Result for {query}",
                    source_doc="Doc 1",
                    page=1,
                    clause_id="clause-1",
                    score=0.99,
                )
            ]

        def get_clause(self, clause_id: str):
            if clause_id == "clause-1":
                return Passage(
                    id="dummy-1",
                    text="Exact clause text",
                    source_doc="Doc 1",
                    clause_id="clause-1",
                    score=1.0,
                )
            return None

    dummy_mod.ChromaRetriever = DummyRetriever
    monkeypatch.setitem(sys.modules, "pipeline.retrieval", dummy_mod)

    adapter = RealRetrieverAdapter("pipeline.retrieval")
    results = adapter.search("Lamotrigine", k=1)
    assert len(results) == 1
    assert results[0].id == "dummy-1"
    assert "Lamotrigine" in results[0].text

    clause = adapter.get_clause("clause-1")
    assert clause is not None
    assert clause.clause_id == "clause-1"


def test_retriever_env_factory_switching():
    """Verify get_default_retriever switches implementation based on RETRIEVER env var."""
    os.environ["RETRIEVER"] = "mock"
    retriever_mock = get_default_retriever()
    assert isinstance(retriever_mock, MockRetriever)

    os.environ["RETRIEVER"] = "real"
    retriever_real = get_default_retriever()
    assert isinstance(retriever_real, RealRetrieverAdapter)

    # Defaults to mock if unspecified
    os.environ.pop("RETRIEVER", None)
    assert isinstance(get_default_retriever(), MockRetriever)


# ========================================================================
# Task 2: rewrite_query(lay_text) with 3-5 terms and fallback dictionary
# ========================================================================

@pytest.mark.parametrize(
    "lay_text, expected_terms",
    [
        (
            "Patient skin started peeling and blistering badly after 1 week",
            ["Toxic epidermal necrolysis", "Stevens-Johnson syndrome"],
        ),
        (
            "Severe hives and body rash with itching",
            ["Urticaria", "Maculopapular rash"],
        ),
        (
            "Yellow skin and eyes, suspected liver injury",
            ["Drug-induced liver injury", "Jaundice", "Hepatotoxicity"],
        ),
        (
            "Internal stomach bleeding and black stool",
            ["Gastrointestinal hemorrhage", "Hemorrhage"],
        ),
        (
            "Severe high fever and convulsion",
            ["Pyrexia", "Convulsion"],
        ),
    ],
)
def test_rewrite_query_deterministic_fallback(lay_text, expected_terms):
    """Verify rewrite_query returns 3-5 candidate terms matching fallback vocabulary."""
    candidates = rewrite_query(lay_text)
    assert isinstance(candidates, list)
    assert 3 <= len(candidates) <= 5
    assert all(isinstance(term, str) and len(term) > 0 for term in candidates)
    # Check that at least one expected term is present
    assert any(any(exp.lower() in cand.lower() for exp in expected_terms) for cand in candidates)


def test_rewrite_query_length_boundary():
    """Verify rewrite_query strictly bounds candidates between 3 and 5 items."""
    # Unknown lay text with no direct keyword match
    unknown_candidates = rewrite_query("Patient felt completely strange and unspecific")
    assert 3 <= len(unknown_candidates) <= 5

    # Text with multiple matching keywords (peeling, blister, skin, rash, hives)
    rich_candidates = rewrite_query("Patient had skin peeling, rash, hives, and blisters everywhere")
    assert 3 <= len(rich_candidates) <= 5
    assert len(rich_candidates) == len(set(rich_candidates))  # Deduplicated


# ========================================================================
# Task 3: get_request_fields(run_id)
# ========================================================================

def test_get_request_fields_direct():
    """Verify request field extraction when report dict is passed."""
    report = {
        "report_id": "rep_101",
        "suspect_drug": "Lamotrigine",
        "patient_age": 45,
        "patient_sex": "female",
        "reporter_type": "physician",
        "drug_start_date": "2026-01-01",
        "event_date": "2026-01-10",
        "reaction_description": "Skin peeling and mucosal detachment",
        "outcome": "not_recovered",
        "narrative": "Admitted to ICU burn unit.",
    }
    fields = get_request_fields("rep_101", report=report)
    assert fields["run_id"] == "rep_101"
    assert fields["report_id"] == "rep_101"
    assert fields["suspect_drug"] == "Lamotrigine"
    assert fields["patient_age"] == 45
    assert fields["reaction_description"] == "Skin peeling and mucosal detachment"
    assert fields["outcome"] == "not_recovered"


def test_get_request_fields_from_registry():
    """Verify request field extraction using registered run_id without passing report."""
    run_id = "run_registered_77"
    report = {
        "report_id": "rep_77",
        "suspect_drug": "Carbamazepine",
        "patient_age": 30,
        "reaction_description": "Stevens-Johnson syndrome",
        "outcome": "recovering",
    }
    register_run_report(run_id, report)

    # Call with ONLY run_id
    fields = get_request_fields(run_id)
    assert fields["run_id"] == run_id
    assert fields["report_id"] == "rep_77"
    assert fields["suspect_drug"] == "Carbamazepine"
    assert fields["reaction_description"] == "Stevens-Johnson syndrome"


def test_get_request_fields_fallback_unknown():
    """Verify get_request_fields returns graceful fallback for unknown run_id."""
    fields = get_request_fields("unknown_run_xyz")
    assert fields == {"run_id": "unknown_run_xyz"}


# ========================================================================
# Task 4: Tool Wrapper: Audit Logging, MAX_TOOL_CALLS, and Per-call Timeout
# ========================================================================

def test_tool_wrapper_audit_logging():
    """Verify tool wrapper records EVERY call with complete audit fields."""
    tool_log: list[ToolCall] = []
    tools = wrap_tools(tool_log)

    terms = tools.rewrite_query("skin peeling")
    assert len(terms) >= 3
    assert len(tool_log) == 1

    entry = tool_log[0]
    assert entry.step == 1
    assert entry.tool == "rewrite_query"
    assert entry.input == {"lay_text": "skin peeling"}
    assert "Rewrote to" in entry.output_summary
    assert entry.latency_ms > 0
    assert entry.ok is True

    # Call second tool
    passages = tools.search_corpus("Lamotrigine", k=2)
    assert len(passages) > 0
    assert len(tool_log) == 2

    entry2 = tool_log[1]
    assert entry2.step == 2
    assert entry2.tool == "search_corpus"
    assert entry2.input == {"query": "Lamotrigine", "k": 2}
    assert "Retrieved" in entry2.output_summary
    assert entry2.ok is True


def test_tool_wrapper_max_tool_calls_enforcement():
    """Verify tool wrapper enforces MAX_TOOL_CALLS and logs failure before raising."""
    tool_log: list[ToolCall] = []
    max_allowed = 3
    tools = wrap_tools(tool_log, max_calls=max_allowed)

    # Make 3 allowed calls
    tools.rewrite_query("rash")
    tools.get_clause("ndct-2019-second-sched-table1")
    tools.search_corpus("Lamotrigine", k=1)
    assert len(tool_log) == 3
    assert all(t.ok is True for t in tool_log)

    # 4th call must breach MAX_TOOL_CALLS
    with pytest.raises(ToolCallLimitExceeded) as exc_info:
        tools.rewrite_query("another symptom")

    assert "Tool call limit exceeded: 3/3" in str(exc_info.value)
    # Verify the breached call is recorded in the tool_log with ok=False
    assert len(tool_log) == 4
    breached_call = tool_log[3]
    assert breached_call.step == 4
    assert breached_call.tool == "rewrite_query"
    assert breached_call.ok is False
    assert "limit exceeded" in breached_call.output_summary.lower()


def test_tool_wrapper_timeout_enforcement():
    """Verify tool wrapper enforces per-call timeout and logs failure before raising."""
    tool_log: list[ToolCall] = []

    def slow_tool(duration: float) -> str:
        time.sleep(duration)
        return "finished"

    # Wrap with 0.1s timeout
    wrapped_slow_tool = make_tool_wrapper("slow_tool", tool_log, timeout_s=0.1)(slow_tool)

    with pytest.raises(ToolTimeoutError) as exc_info:
        wrapped_slow_tool(0.3)

    assert "timed out after 0.1s" in str(exc_info.value)
    assert len(tool_log) == 1
    timeout_entry = tool_log[0]
    assert timeout_entry.step == 1
    assert timeout_entry.tool == "slow_tool"
    assert timeout_entry.ok is False
    assert "timed out" in timeout_entry.output_summary.lower()


def test_sample_run_tool_log_output(capsys):
    """PROOF TO SHOW: Print a formatted tool_log for a sample triage run."""
    tool_log: list[ToolCall] = []
    tools = wrap_tools(tool_log, max_calls=10, timeout_s=5.0)

    # Execute all 4 tools in a realistic triage sequence
    # 1. get_request_fields
    report_dict = {
        "report_id": "rep_proof_42",
        "suspect_drug": "Lamotrigine",
        "reaction_description": "Severe skin peeling with mucosal detachment",
        "outcome": "not_recovered",
        "narrative": "Patient admitted to burn unit.",
    }
    fields = tools.get_request_fields("rep_proof_42", report=report_dict)

    # 2. rewrite_query
    medical_terms = tools.rewrite_query(fields["reaction_description"])

    # 3. search_corpus
    search_query = f"{fields['suspect_drug']} {' '.join(medical_terms[:2])} seriousness hospitalisation"
    passages = tools.search_corpus(search_query, k=3)

    # 4. get_clause
    clause = tools.get_clause("ndct-2019-second-sched-table1")

    assert len(tool_log) == 4
    assert all(t.ok is True for t in tool_log)
    assert [t.tool for t in tool_log] == [
        "get_request_fields",
        "rewrite_query",
        "search_corpus",
        "get_clause",
    ]

    print("\n" + "=" * 70)
    print("PHASE 2 MEMBER B - SAMPLE RUN TOOL LOG AUDIT TRAIL")
    print("=" * 70)
    for call in tool_log:
        status_str = "OK" if call.ok else "FAILED"
        print(
            f"Step {call.step} | Tool: {call.tool:<18} | Status: {status_str:<4} | Latency: {call.latency_ms:>6.2f}ms"
        )
        print(f"       Input : {call.input}")
        print(f"       Output: {call.output_summary}")
    print("=" * 70 + "\n")
