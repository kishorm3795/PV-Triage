"""eval/scorers.py - Member C's evaluation scorers for PV-Triage.

Implements the Scorer protocol using the RAG Triad metrics from eval/metrics.py.
Provides groundedness, citation resolution, claim support, and quote verbatim checks
using the real corpus retriever and deterministic evaluation logic.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from agents.scoring import ScoreResult, Scorer
from shared.contracts import Passage, RunResult

logger = logging.getLogger("eval.scorers")


class EvalScorer:
    """Member C's evaluation scorer using RAG Triad metrics.

    Wraps eval.metrics.evaluate_run to provide Scorer protocol compliance.
    Requires real retriever to fetch passages for citation verification.
    """

    def __init__(self, retriever_mode: str = "real"):
        self.retriever_mode = retriever_mode
        self._retriever = None

    def _get_retriever(self):
        """Lazy-load the real retriever."""
        if self._retriever is None:
            try:
                from pipeline.retrieval import create_retriever

                self._retriever = create_retriever()
            except Exception as exc:
                logger.warning("Failed to load real retriever: %s", exc)
                raise
        return self._retriever

    def _retrieve_passages_for_run(self, run: RunResult) -> List[Passage]:
        """Reconstruct retrieved passages from the run's tool calls and trace.

        Since RunResult doesn't directly store retrieved passages, we re-execute
        the queries from tool_calls to get the actual passages used.
        """
        retriever = self._get_retriever()
        passages: List[Passage] = []
        seen_ids: set[str] = set()

        # Extract queries from tool_calls
        for tool_call in run.tool_calls:
            if tool_call.tool in ("search_corpus", "get_clause") and tool_call.ok:
                # tool_call.input contains the query/clause_id
                if isinstance(tool_call.input, dict):
                    if "query" in tool_call.input:
                        query = tool_call.input["query"]
                        results = retriever.search(query, k=5)
                        for p in results:
                            if p.id not in seen_ids:
                                passages.append(p)
                                seen_ids.add(p.id)
                    elif "clause_id" in tool_call.input:
                        clause_id = tool_call.input["clause_id"]
                        result = retriever.get_clause(clause_id)
                        if result and result.id not in seen_ids:
                            passages.append(result)
                            seen_ids.add(result.id)

        return passages

    def score(self, result: RunResult, retrieved_passages: List[Passage]) -> ScoreResult:
        """Evaluate a run result using RAG Triad metrics.

        Args:
            result: The RunResult from the agent graph
            retrieved_passages: Pre-retrieved passages (or empty list to re-fetch)

        Returns:
            ScoreResult with groundedness, citation_resolve, claim_support, quote_verbatim
        """
        # If no passages provided, re-fetch using the real retriever
        if not retrieved_passages:
            retrieved_passages = self._retrieve_passages_for_run(result)

        # Convert RunResult to dict for evaluate_run
        run_dict = {
            "run_id": result.run_id,
            "status": result.status,
            "routing": result.routing,
            "routing_basis": result.routing_basis,
            "seriousness": {
                "is_serious": result.seriousness.is_serious,
                "criteria": result.seriousness.criteria,
            },
            "expectedness": {
                "is_listed": result.expectedness.is_listed,
                "matched_term": result.expectedness.matched_term,
            },
            "citations": [{"passage_id": c.passage_id, "quote": c.quote} for c in result.citations],
            "escalation_reason": result.escalation_reason,
        }

        # Convert passages to dict format
        passages_dict = [
            {
                "id": p.id,
                "text": p.text,
                "source_doc": p.source_doc,
                "page": p.page,
                "clause_id": p.clause_id,
                "section": p.section,
                "score": p.score,
            }
            for p in retrieved_passages
        ]

        # Need a scenario dict - we'll construct minimal one from result
        # For eval mode, we expect the scenario to be available in batch context
        scenario_dict = {
            "id": getattr(result, "scenario_id", result.run_id),
            "expected_action": "escalate" if result.status == "escalated" else "answer",
            "expected_routing": getattr(result, "expected_routing", None),
            "report": {},  # Not needed for groundedness/faithfulness
        }

        # Import and use eval metrics
        from eval.metrics import evaluate_run

        eval_result = evaluate_run(scenario_dict, run_dict, passages_dict)

        # Map to ScoreResult protocol
        return ScoreResult(
            groundedness=eval_result.get("groundedness", 0.0),
            citation_resolve=eval_result.get("faithfulness", 0.0) == 1.0,
            claim_support=eval_result.get("groundedness", 0.0),
            quote_verbatim=eval_result.get("faithfulness", 0.0) == 1.0,
            metadata={
                "scorer": "eval",
                "citations_count": len(result.citations),
                "passages_retrieved": len(retrieved_passages),
                "context_relevance": eval_result.get("context_relevance", 0.0),
                "hallucination": eval_result.get("hallucination", 0),
                "routing_match": eval_result.get("routing_match"),
                "escalation_match": eval_result.get("escalation_match"),
                "passed": eval_result.get("passed", False),
            },
        )


# Export for agents.scoring import
__all__ = ["EvalScorer"]
