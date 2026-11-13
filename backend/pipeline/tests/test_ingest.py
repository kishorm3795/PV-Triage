"""pipeline/tests/test_ingest.py - Unit tests for ingestion, chunking, and freshness tracking."""

import os
import tempfile
from pathlib import Path
import pytest
from pipeline.chunker import (
    ADVERSE_REACTION_TERMS,
    compute_content_hash,
)
from pipeline.meta import (
    CHROMA_DIR,
    IndexMeta,
    SourceDocMeta,
    load_index_meta,
    update_prometheus_metrics,
)


def test_content_hash_deterministic():
    """Verify compute_content_hash produces deterministic 16-char hashes."""
    text1 = "This is a test chunk text."
    text2 = "This is a test chunk text."
    text3 = "Different text."

    hash1 = compute_content_hash(text1)
    hash2 = compute_content_hash(text2)
    hash3 = compute_content_hash(text3)

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 16


def test_index_meta_freshness_exists():
    """Verify index_meta.json exists, loads correctly, and contains valid metadata."""
    meta = load_index_meta(CHROMA_DIR)
    assert meta is not None
    assert isinstance(meta, IndexMeta)
    assert meta.total_chunks > 0
    assert meta.chunks_per_second > 0
    assert meta.embed_model == "all-MiniLM-L6-v2"
    assert len(meta.source_docs) == 3

    doc_names = {sd.name for sd in meta.source_docs}
    assert "ipc_pv_guidance_mah.pdf" in doc_names
    assert "lamotrigine_package_insert.pdf" in doc_names
    assert "ndct_rules_2019.pdf" in doc_names

    for sd in meta.source_docs:
        assert sd.chunk_count > 0
        assert sd.size_bytes > 0
        assert len(sd.content_hash) > 0


def test_prometheus_metrics_update():
    """Verify update_prometheus_metrics sets gauges without error."""
    meta = load_index_meta(CHROMA_DIR)
    assert meta is not None
    # Should update gauges cleanly
    update_prometheus_metrics(meta)


def test_adverse_reaction_terms_count():
    """Verify all 18 listed adverse reaction terms are indexed in Chroma."""
    from pipeline.retrieval import get_chroma_client
    client = get_chroma_client(CHROMA_DIR)
    col = client.get_collection("pv_corpus")
    res = col.get(where={"clause_id": "adverse_reaction_terms"}, include=["documents"])
    assert len(res["ids"]) == len(ADVERSE_REACTION_TERMS)
