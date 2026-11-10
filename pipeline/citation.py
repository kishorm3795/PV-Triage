"""pipeline/citation.py - Citation resolution helper and validator.

Validates that cited passage IDs exist in retrieved passages and that
cited quotes appear verbatim within the retrieved text.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from shared.contracts import Citation, Passage


def resolve_citation(
    citation: Citation,
    retrieved_passages: List[Passage | Dict[str, Any]],
) -> Tuple[bool, Optional[str]]:
    """Resolve a single citation against retrieved passages.

    Returns:
        (True, None) if resolved and verbatim.
        (False, error_message) if resolution or verbatim check fails.
    """
    passages_by_id: Dict[str, str] = {}
    for p in retrieved_passages:
        if isinstance(p, Passage):
            passages_by_id[p.id] = p.text
            if p.clause_id:
                passages_by_id[p.clause_id] = p.text
        elif isinstance(p, dict):
            pid = p.get("id")
            if pid:
                passages_by_id[pid] = p.get("text", "")
            cid = p.get("clause_id")
            if cid:
                passages_by_id[cid] = p.get("text", "")

    if citation.passage_id not in passages_by_id:
        return False, f"Cited passage_id '{citation.passage_id}' was not retrieved in this run."

    target_text = passages_by_id[citation.passage_id]
    if citation.quote not in target_text:
        return False, f"Quote for passage '{citation.passage_id}' is not a verbatim match in retrieved text."

    return True, None


def resolve_all_citations(
    citations: List[Citation],
    retrieved_passages: List[Passage | Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    """Resolve a list of citations against retrieved passages.

    Returns:
        (all_passed, list_of_errors)
    """
    errors: List[str] = []
    for c in citations:
        ok, err = resolve_citation(c, retrieved_passages)
        if not ok and err:
            errors.append(err)

    return len(errors) == 0, errors
