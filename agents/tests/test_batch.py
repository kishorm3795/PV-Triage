"""agents/tests/test_batch.py - Unit tests for batch evaluation runner."""

from unittest.mock import patch, MagicMock
import pytest
import os
import sys

# Ensure agents module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestBatchRunner:
    """Tests for agents.batch module."""

    def test_load_scenarios_valid_jsonl(self, tmp_path):
        """Test loading scenarios from valid JSONL file."""
        from agents.batch import load_scenarios

        scenarios_file = tmp_path / "scenarios.jsonl"
        scenarios_file.write_text(
            '{"report_id": "rep_001", "reaction_description": "Test reaction"}\n'
            '{"report_id": "rep_002", "reaction_description": "Another reaction"}\n'
        )

        scenarios = load_scenarios(str(scenarios_file))
        assert len(scenarios) == 2
        assert scenarios[0]["report_id"] == "rep_001"
        assert scenarios[1]["report_id"] == "rep_002"

    def test_load_scenarios_skips_invalid_lines(self, tmp_path):
        """Test that invalid JSON lines are skipped with warning."""
        from agents.batch import load_scenarios

        scenarios_file = tmp_path / "scenarios.jsonl"
        scenarios_file.write_text(
            '{"report_id": "rep_001", "reaction_description": "Valid"}\n'
            'not valid json\n'
            '{"report_id": "rep_002", "reaction_description": "Also valid"}\n'
        )

        scenarios = load_scenarios(str(scenarios_file))
        assert len(scenarios) == 2

    def test_load_scenarios_empty_file(self, tmp_path):
        """Test loading from empty file returns empty list."""
        from agents.batch import load_scenarios

        scenarios_file = tmp_path / "empty.jsonl"
        scenarios_file.write_text("")

        scenarios = load_scenarios(str(scenarios_file))
        assert scenarios == []

    @patch("agents.batch.run_graph")
    @patch("agents.batch.get_scorer")
    @patch("agents.batch.get_default_retriever")
    def test_run_batch_basic(self, mock_retriever, mock_scorer, mock_run_graph):
        """Test basic batch run with mocked components."""
        from agents.batch import run_batch

        # Setup mocks
        mock_result = MagicMock()
        mock_result.run_id = "batch_test_0000"
        mock_result.status = "completed"
        mock_result.routing = "expedited"
        mock_result.routing_basis = "Test basis"
        mock_result.seriousness = MagicMock(is_serious=True, criteria=["test"])
        mock_result.expectedness = MagicMock(is_listed=False, matched_term=None)
        mock_result.citations = []
        mock_result.escalation_reason = None
        mock_result.trace = []
        mock_result.tool_calls = []
        mock_result.prompt_versions = {"assessor": "v1"}
        mock_result.verification_passed = True

        mock_run_graph.return_value = mock_result

        mock_score = {"groundedness": 1.0, "citation_resolve": True, "claim_support": 1.0, "quote_verbatim": True}
        mock_scorer.return_value.score.return_value = mock_score

        scenarios = [
            {"report_id": "rep_001", "reaction_description": "Test", "expected_routing": "expedited"},
        ]

        results = run_batch(scenarios, "v1", "mock", "local")

        assert len(results) == 1
        assert results[0]["run_id"].startswith("batch_v1_mock_")
        assert results[0]["status"] == "completed"
        assert results[0]["routing"] == "expedited"
        assert results[0]["verifier_outcome"] == "passed"
        assert results[0]["routing_correct"] is True

    @patch("agents.batch.run_graph")
    @patch("agents.batch.get_scorer")
    @patch("agents.batch.get_default_retriever")
    def test_run_batch_verification_failed(self, mock_retriever, mock_scorer, mock_run_graph):
        """Test batch run with failed verification."""
        from agents.batch import run_batch

        mock_result = MagicMock()
        mock_result.run_id = "batch_test_0000"
        mock_result.status = "completed"
        mock_result.routing = "expedited"
        mock_result.routing_basis = "Test basis"
        mock_result.seriousness = MagicMock(is_serious=True, criteria=["test"])
        mock_result.expectedness = MagicMock(is_listed=False, matched_term=None)
        mock_result.citations = []
        mock_result.escalation_reason = None
        mock_result.trace = []
        mock_result.tool_calls = []
        mock_result.prompt_versions = {"assessor": "v1"}
        mock_result.verification_passed = False

        mock_run_graph.return_value = mock_result

        mock_score = {"groundedness": 0.5, "citation_resolve": False, "claim_support": 0.5, "quote_verbatim": False}
        mock_scorer.return_value.score.return_value = mock_score

        scenarios = [{"report_id": "rep_001", "reaction_description": "Test"}]

        results = run_batch(scenarios, "v1", "mock", "local")

        assert results[0]["verifier_outcome"] == "failed"

    @patch("agents.batch.run_graph")
    @patch("agents.batch.get_scorer")
    @patch("agents.batch.get_default_retriever")
    def test_run_batch_verification_skipped_no_verifier(self, mock_retriever, mock_scorer, mock_run_graph):
        """Test batch run with no verifier step (verification_passed is None)."""
        from agents.batch import run_batch

        mock_result = MagicMock()
        mock_result.run_id = "batch_test_0000"
        mock_result.status = "completed"
        mock_result.routing = "expedited"
        mock_result.routing_basis = "Test basis"
        mock_result.seriousness = MagicMock(is_serious=True, criteria=["test"])
        mock_result.expectedness = MagicMock(is_listed=False, matched_term=None)
        mock_result.citations = []
        mock_result.escalation_reason = None
        mock_result.trace = []
        mock_result.tool_calls = []
        mock_result.prompt_versions = {"assessor": "v1"}
        mock_result.verification_passed = None  # No verifier step

        mock_run_graph.return_value = mock_result

        mock_score = {"groundedness": 1.0, "citation_resolve": True, "claim_support": 1.0, "quote_verbatim": True}
        mock_scorer.return_value.score.return_value = mock_score

        scenarios = [{"report_id": "rep_001", "reaction_description": "Test"}]

        results = run_batch(scenarios, "v1", "mock", "local")

        assert results[0]["verifier_outcome"] == "skipped"

    def test_print_summary_runs_without_error(self, capsys):
        """Test that print_summary executes without error."""
        from agents.batch import print_summary

        results = [
            {
                "run_id": "batch_v1_mock_0000",
                "scenario_id": "scenario_0",
                "status": "completed",
                "routing": "expedited",
                "routing_basis": "Test",
                "seriousness": {"is_serious": True, "criteria": []},
                "expectedness": {"is_listed": False, "matched_term": None},
                "citations_resolved": True,
                "citations_count": 2,
                "verifier_outcome": "passed",
                "escalation_reason": None,
                "steps": 5,
                "tool_calls": 2,
                "total_tokens": 100,
                "prompt_tokens": 60,
                "completion_tokens": 40,
                "cost_usd": 0.0001,
                "prompt_versions": {"assessor": "v1"},
                "elapsed_ms": 500.0,
                "score": {},
                "routing_correct": True,
            }
        ]

        print_summary(results, "v1")
        captured = capsys.readouterr()
        assert "BATCH EVALUATION SUMMARY" in captured.out
        assert "v1" in captured.out
        assert "completed" in captured.out

    def test_save_results_creates_file(self, tmp_path):
        """Test that save_results creates a valid JSON file."""
        from agents.batch import save_results

        results = [{"run_id": "test"}]
        filepath = save_results(results, "v1", "mock", "local")

        assert filepath.exists()
        assert filepath.name.startswith("batch_v1_mock_local_")
        assert filepath.name.endswith(".json")

        import json
        with open(filepath) as f:
            data = json.load(f)
        assert data["metadata"]["prompt_version"] == "v1"
        assert data["metadata"]["retriever_mode"] == "mock"
        assert data["metadata"]["scorer_mode"] == "local"
        assert len(data["results"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
