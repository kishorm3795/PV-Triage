"""pipeline/tests/test_retrieval.py - Unit tests for Member C ChromaRetriever."""

import os
import pytest
from pipeline.retrieval import ChromaRetriever, get_clause, search
from shared.contracts import Passage, Retriever


def test_chroma_retriever_implements_protocol():
    """Verify ChromaRetriever conforms to the frozen Retriever protocol."""
    retriever = ChromaRetriever()
    assert isinstance(retriever, Retriever)


def test_search_returns_passages_with_scores():
    """Verify search returns Passage objects with similarity scores."""
    retriever = ChromaRetriever()
    passages = retriever.search("Lamotrigine adverse reaction", k=5)

    assert isinstance(passages, list)
    assert len(passages) > 0
    assert len(passages) <= 5
    assert all(isinstance(p, Passage) for p in passages)
    assert all(p.score is not None and 0.0 <= p.score <= 1.0 for p in passages)

    # Scores must be sorted descending
    scores = [p.score for p in passages if p.score is not None]
    assert scores == sorted(scores, reverse=True)


def test_search_lay_query_vocabulary_gap():
    """Verify search with colloquial lay phrase retrieves clinical SCAR concepts."""
    retriever = ChromaRetriever()
    passages = retriever.search("skin started peeling badly", k=5)

    assert len(passages) > 0
    # Must retrieve adverse reaction term chunks or warnings mentioning SJS / TEN
    retrieved_texts = " ".join([p.text.lower() for p in passages])
    assert any(
        term in retrieved_texts
        for term in [
            "stevens-johnson",
            "toxic epidermal necrolysis",
            "skin rashes",
            "erythema multiforme",
            "exfoliative dermatitis",
        ]
    )


def test_search_medical_query_reference_case():
    """Verify search with formal medical term retrieves package insert warnings."""
    retriever = ChromaRetriever()
    passages = retriever.search("toxic epidermal necrolysis", k=5)

    assert len(passages) > 0
    top = passages[0]
    assert top.score is not None and top.score > 0.5
    assert "toxic epidermal necrolysis" in top.text.lower()


def test_get_clause_statutory_identifiers():
    """Verify get_clause resolves both canonical slugs and numbered statutory clauses."""
    retriever = ChromaRetriever()

    # 1. NDCT 2019 Expedited Reporting (15 days)
    ndct_clause = retriever.get_clause("ndct-2019-second-sched-table1")
    assert ndct_clause is not None
    assert isinstance(ndct_clause, Passage)

    # 2. IPC Guidance Seriousness Criteria (2.5.3.6)
    ipc_clause = retriever.get_clause("ipc-pv-guidance-sec4-seriousness")
    assert ipc_clause is not None
    assert "hospitalization" in ipc_clause.text.lower() or "serious" in ipc_clause.text.lower()

    # 3. Lamotrigine Package Insert Boxed Warning / Section 5.1
    pi_clause = retriever.get_clause("lamotrigine-pi-sec4-8-undesirable")
    assert pi_clause is not None
    assert "rash" in pi_clause.text.lower() or "boxed warning" in pi_clause.text.lower()

    # 4. Numbered clause lookup
    clause_2536 = retriever.get_clause("2.5.3.6")
    assert clause_2536 is not None
    assert "2.5.3.6" in clause_2536.text

    clause_271 = retriever.get_clause("2.7.1")
    assert clause_271 is not None
    assert "2.7.1" in clause_271.text

    # 5. Non-existent clause lookup returns None
    missing = retriever.get_clause("non-existent-clause-xyz")
    assert missing is None


def test_module_level_retriever_functions():
    """Verify module-level search and get_clause functions work directly."""
    passages = search("Lamotrigine", k=2)
    assert len(passages) <= 2
    assert all(isinstance(p, Passage) for p in passages)

    clause = get_clause("2.5.3.6")
    assert clause is not None
    assert isinstance(clause, Passage)
