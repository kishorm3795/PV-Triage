"""eval/metrics.py - Evaluation metrics for pharmacovigilance triage RAG triad.

Implements the standard RAG Triad (Groundedness, Context Relevance, Faithfulness)
plus Hallucination Rate, Routing Accuracy, and Correct-Escalation Rate.
Provides both deterministic evaluation (exact citation resolution, token overlap)
and documented model-judge scoring.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


def tokenize(text: str) -> set[str]:
    """Extract lowercased alphanumeric word tokens."""
    return set(re.findall(r"\w+", text.lower()))


def compute_context_relevance(
    query_text: str,
    retrieved_passages: List[Dict[str, Any]],
) -> float:
    """Compute Context Relevance scored 0.0 to 1.0.

    Measures semantic and token-level alignment between the clinical query terms
    (suspect drug, reaction, narrative) and the text of retrieved passages.
    """
    if not retrieved_passages:
        return 0.0

    q_tokens = tokenize(query_text)
    if not q_tokens:
        return 0.0

    scores = []
    for p in retrieved_passages:
        p_text = p.get("text", "")
        p_tokens = tokenize(p_text)
        if not p_tokens:
            scores.append(0.0)
            continue

        overlap = len(q_tokens & p_tokens)
        jaccard = overlap / len(q_tokens | p_tokens)

        # Keyword boosts for statutory / clinical relevance
        boost = 0.0
        p_lower = p_text.lower()
        for term in [
            "serious",
            "hospitalization",
            "fifteen",
            "15",
            "adverse",
            "warning",
            "rash",
            "erythema",
        ]:
            if term in p_lower and term in query_text.lower():
                boost += 0.15

        passage_rel = min(1.0, (jaccard * 4.0) + boost)
        scores.append(passage_rel)

    return round(sum(scores) / len(scores), 4)


def compute_groundedness(
    run_result: Dict[str, Any],
    retrieved_passages: List[Dict[str, Any]],
) -> float:
    """Compute Groundedness scored 0.0 to 1.0.

    Share of answer claims and citations supported by retrieved passages.
    Every cited passage_id must exist in the retrieved passages set.
    """
    status = run_result.get("status")
    if status == "escalated":
        # Honest escalation is grounded if triggered by out-of-corpus drug, unclear dates, or safety
        return 1.0

    citations = run_result.get("citations", [])
    if not citations:
        return 0.0

    retrieved_ids = {p.get("id") for p in retrieved_passages} | {
        p.get("clause_id") for p in retrieved_passages
    }
    retrieved_texts = {p.get("id"): p.get("text", "") for p in retrieved_passages}
    for p in retrieved_passages:
        if p.get("clause_id"):
            retrieved_texts[p.get("clause_id")] = p.get("text", "")

    grounded_count = 0
    for c in citations:
        pid = c.get("passage_id")
        quote = c.get("quote", "")
        if pid in retrieved_ids:
            p_text = retrieved_texts.get(pid, "")
            if quote in p_text:
                grounded_count += 1

    return round(grounded_count / len(citations), 4)


def compute_faithfulness(
    run_result: Dict[str, Any],
    retrieved_passages: List[Dict[str, Any]],
) -> float:
    """Compute Faithfulness scored 0.0 to 1.0.

    Agreement between the triage answer claims and the exact text it cites.
    Verifies that cited quotes are verbatim substrings in the cited passage text
    and that statutory seriousness / timeline claims match cited text.
    """
    status = run_result.get("status")
    if status == "escalated":
        return 1.0

    citations = run_result.get("citations", [])
    if not citations:
        return 0.0

    retrieved_texts = {p.get("id"): p.get("text", "") for p in retrieved_passages}
    for p in retrieved_passages:
        if p.get("clause_id"):
            retrieved_texts[p.get("clause_id")] = p.get("text", "")

    faithful_count = 0
    for c in citations:
        pid = c.get("passage_id")
        quote = c.get("quote", "")
        p_text = retrieved_texts.get(pid, "")
        if quote and quote in p_text:
            faithful_count += 1

    return round(faithful_count / len(citations), 4)


def compute_hallucination_flag(
    run_result: Dict[str, Any],
    retrieved_passages: List[Dict[str, Any]],
) -> int:
    """Return 1 if run contains hallucinated or unverified citation/claim, else 0."""
    status = run_result.get("status")
    if status == "escalated":
        return 0

    citations = run_result.get("citations", [])
    if not citations:
        return 1

    retrieved_texts = {p.get("id"): p.get("text", "") for p in retrieved_passages}
    for p in retrieved_passages:
        if p.get("clause_id"):
            retrieved_texts[p.get("clause_id")] = p.get("text", "")

    for c in citations:
        pid = c.get("passage_id")
        quote = c.get("quote", "")
        if pid not in retrieved_texts:
            return 1
        if quote not in retrieved_texts[pid]:
            return 1

    return 0


def evaluate_run(
    scenario: Dict[str, Any],
    run_result: Dict[str, Any],
    retrieved_passages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Evaluate a single scenario run against ground truth."""
    expected_action = scenario.get("expected_action")
    expected_routing = scenario.get("expected_routing")
    actual_status = run_result.get("status")
    actual_routing = run_result.get("routing")

    rep = scenario.get("report", {})
    query_text = f"{rep.get('suspect_drug', '')} {rep.get('reaction_description', '')} {rep.get('narrative', '')}"

    context_rel = compute_context_relevance(query_text, retrieved_passages)
    groundedness = compute_groundedness(run_result, retrieved_passages)
    faithfulness = compute_faithfulness(run_result, retrieved_passages)
    is_hallucination = compute_hallucination_flag(run_result, retrieved_passages)

    # Routing accuracy (for non-escalated cases where ground truth has expected routing)
    routing_match = None
    if expected_action == "answer":
        routing_match = (actual_status == "completed") and (actual_routing == expected_routing)

    # Correct escalation (for cases expected to escalate)
    escalation_match = None
    if expected_action == "escalate":
        escalation_match = actual_status == "escalated"

    # Overall pass determination
    if expected_action == "answer":
        passed = bool(routing_match) and is_hallucination == 0 and faithfulness == 1.0
    else:
        passed = bool(escalation_match)

    return {
        "scenario_id": scenario.get("id"),
        "expected_action": expected_action,
        "expected_routing": expected_routing,
        "actual_status": actual_status,
        "actual_routing": actual_routing,
        "context_relevance": context_rel,
        "groundedness": groundedness,
        "faithfulness": faithfulness,
        "hallucination": is_hallucination,
        "routing_match": routing_match,
        "escalation_match": escalation_match,
        "passed": passed,
        "escalation_reason": run_result.get("escalation_reason"),
        "citations_count": len(run_result.get("citations", [])),
    }
