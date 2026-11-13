"""agents/scoring.py - Scorer protocol and deterministic local scorer.

Implements the Scorer protocol for evaluating agent outputs. Provides a deterministic
local scorer (SCORER=local) and optional import of Member C's eval scorers (SCORER=eval).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Protocol, TypedDict

from shared.contracts import Citation, Passage, RunResult

logger = logging.getLogger("agents.scoring")


class ScoreResult(TypedDict):
    """Result of a scoring evaluation."""

    groundedness: float  # 0.0 to 1.0
    citation_resolve: bool  # All citations resolve to retrieved passages
    claim_support: float  # 0.0 to 1.0 (fraction of claims supported by passages)
    quote_verbatim: bool  # All quotes are exact substrings of cited passages
    metadata: Dict[str, Any]


class Scorer(Protocol):
    """Protocol for scoring agent run results."""

    def score(self, result: RunResult, retrieved_passages: List[Passage]) -> ScoreResult:
        """Evaluate a run result against retrieved passages."""
        ...


class LocalScorer:
    """Deterministic local scorer for offline evaluation.

    Checks:
    1. groundedness: 1.0 if all citations resolve AND all quotes verbatim, else 0.0
    2. citation_resolve: True if every citation passage_id exists in retrieved_passages
    3. claim_support: Fraction of claims supported by passages (simplified: 1.0 if seriousness/timeline/expectedness claims have support)
    4. quote_verbatim: True if every citation quote is exact substring of its passage text
    """

    def score(self, result: RunResult, retrieved_passages: List[Passage]) -> ScoreResult:
        passage_map: Dict[str, Passage] = {p.id: p for p in retrieved_passages}

        # Check 1: Citation resolution
        citation_resolve = True
        for citation in result.citations:
            if citation.passage_id not in passage_map:
                citation_resolve = False
                break

        # Check 2: Quote verbatim
        quote_verbatim = True
        for citation in result.citations:
            if citation.passage_id in passage_map:
                passage_text = passage_map[citation.passage_id].text
                if citation.quote not in passage_text:
                    quote_verbatim = False
                    break
            else:
                quote_verbatim = False
                break

        # Check 3: Claim support (simplified heuristic)
        # Check seriousness claim
        seriousness_supported = False
        if result.seriousness.is_serious:
            for citation in result.citations:
                if citation.passage_id in passage_map:
                    p_text = passage_map[citation.passage_id].text.lower()
                    if any(
                        term in p_text
                        for term in [
                            "hospital",
                            "inpatient",
                            "death",
                            "disability",
                            "life-threatening",
                            "serious",
                        ]
                    ):
                        seriousness_supported = True
                        break
        else:
            seriousness_supported = True  # No claim to support

        # Check timeline claim
        timeline_supported = False
        if result.routing == "expedited":
            for citation in result.citations:
                if citation.passage_id in passage_map:
                    p_text = passage_map[citation.passage_id].text.lower()
                    if any(
                        term in p_text for term in ["fifteen", "15", "expedited", "calendar days"]
                    ):
                        timeline_supported = True
                        break
        else:
            timeline_supported = True  # No expedited claim

        # Check expectedness claim
        listedness_supported = False
        if result.expectedness.is_listed:
            for citation in result.citations:
                if citation.passage_id in passage_map:
                    p_text = passage_map[citation.passage_id].text.lower()
                    if any(
                        term in p_text
                        for term in [
                            "stevens-johnson",
                            "toxic epidermal",
                            "rash",
                            "undesirable",
                            "warning",
                        ]
                    ):
                        listedness_supported = True
                        break
        else:
            listedness_supported = True  # No listed claim

        claims_checked = 0
        claims_supported = 0
        if result.seriousness.is_serious:
            claims_checked += 1
            if seriousness_supported:
                claims_supported += 1
        if result.routing == "expedited":
            claims_checked += 1
            if timeline_supported:
                claims_supported += 1
        if result.expectedness.is_listed:
            claims_checked += 1
            if listedness_supported:
                claims_supported += 1

        claim_support = claims_supported / claims_checked if claims_checked > 0 else 1.0

        # Overall groundedness: strict AND of resolution and verbatim
        groundedness = 1.0 if (citation_resolve and quote_verbatim) else 0.0

        return ScoreResult(
            groundedness=groundedness,
            citation_resolve=citation_resolve,
            claim_support=claim_support,
            quote_verbatim=quote_verbatim,
            metadata={
                "scorer": "local",
                "citations_count": len(result.citations),
                "passages_retrieved": len(retrieved_passages),
                "seriousness_supported": seriousness_supported,
                "timeline_supported": timeline_supported,
                "listedness_supported": listedness_supported,
                "claims_checked": claims_checked,
                "claims_supported": claims_supported,
            },
        )


# Global scorer instance cache
_SCORER_INSTANCE: Optional[Scorer] = None
_SCORER_MODE: Optional[str] = None


def get_scorer() -> Scorer:
    """Return the active scorer instance based on SCORER environment variable.

    SCORER=local  -> LocalScorer (default, deterministic, no external deps)
    SCORER=eval   -> Tries to import Member C's EvalScorer; falls back to LocalScorer on ImportError

    Automatically re-creates instance if SCORER environment variable changes.
    """
    global _SCORER_INSTANCE, _SCORER_MODE

    current_mode = os.getenv("SCORER", "local").lower().strip()

    if _SCORER_INSTANCE is not None and _SCORER_MODE == current_mode:
        return _SCORER_INSTANCE

    if current_mode == "eval":
        try:
            # Try to import Member C's eval scorer
            # Expected location: eval.scorers or similar
            import importlib

            mod = importlib.import_module("eval.scorers")
            EvalScorer = getattr(mod, "EvalScorer", None) or getattr(mod, "Scorer", None)
            if EvalScorer is None:
                raise ImportError("eval.scorers does not export EvalScorer or Scorer")
            _SCORER_INSTANCE = EvalScorer()
            logger.info("Using Member C's EvalScorer (SCORER=eval)")
        except Exception as exc:
            logger.warning(
                "Failed to import Member C's eval scorers (%s). Falling back to LocalScorer.",
                exc,
            )
            _SCORER_INSTANCE = LocalScorer()
    else:
        _SCORER_INSTANCE = LocalScorer()
        logger.info("Using LocalScorer (SCORER=local)")

    _SCORER_MODE = current_mode
    return _SCORER_INSTANCE


def reset_scorer() -> None:
    """Reset the cached scorer instance (useful for testing)."""
    global _SCORER_INSTANCE, _SCORER_MODE
    _SCORER_INSTANCE = None
    _SCORER_MODE = None
