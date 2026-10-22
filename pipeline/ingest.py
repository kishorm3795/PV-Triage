"""pipeline/ingest.py - Corpus ingestion CLI.

Usage: python -m pipeline ingest [--reembed <doc>] [--force]

Steps:
1. Read PDF documents from corpus/
2. Parse with page-awareness, keeping clause numbers and section headings
3. Chunk with clause-boundary chunks, heading prepended, adverse reaction terms
4. Embed locally with sentence-transformers (model from EMBED_MODEL)
5. Index in Chroma at CHROMA_DIR
6. Idempotent: content hash per chunk; unchanged chunks skipped
7. --reembed re-embeds one document without rebuilding the whole index
8. Write index_meta.json and expose Prometheus gauges
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

import chromadb
from chromadb.config import Settings

from pipeline.chunker import chunk_document, Chunk
from pipeline.embedder import Embedder
from pipeline.meta import (
    IndexMeta,
    SourceDocMeta,
    get_source_doc_meta,
    load_index_meta,
    save_index_meta,
    update_prometheus_metrics,
    compute_file_hash,
)

# Corpus documents to process
CORPUS_DOCS = {
    "ipc_pv_guidance_mah.pdf": "corpus/ipc_pv_guidance_mah.pdf",
    "lamotrigine_package_insert.pdf": "corpus/lamotrigine_package_insert.pdf",
    "ndct_rules_2019.pdf": "corpus/ndct_rules_2019.pdf",
}

CHROMA_DIR = os.getenv("CHROMA_DIR", "./data/chroma")
COLLECTION_NAME = "pv_corpus"


def get_chroma_client():
    """Get ChromaDB client."""
    from pipeline.retrieval import get_chroma_client as _get_client
    return _get_client(CHROMA_DIR)


def get_collection(client):
    """Get or create the corpus collection."""
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def chunk_exists(collection, chunk_id: str) -> bool:
    """Check if a chunk already exists in the collection."""
    try:
        result = collection.get(ids=[chunk_id], include=[])
        return len(result.get("ids", [])) > 0
    except Exception:
        return False


def get_existing_hashes(collection) -> Set[str]:
    """Get all existing content hashes from the collection."""
    try:
        # Get all IDs and extract hashes
        result = collection.get(include=["metadatas"])
        hashes = set()
        for metadata in result.get("metadatas", []):
            if metadata and "content_hash" in metadata:
                hashes.add(metadata["content_hash"])
        return hashes
    except Exception:
        return set()


def ingest_document(
    doc_name: str,
    doc_path: str,
    collection,
    embedder: Embedder,
    force: bool = False,
    reembed: bool = False,
    existing_hashes: Optional[Set[str]] = None,
) -> Tuple[List[Chunk], List[Chunk], SourceDocMeta]:
    """Ingest a single document.

    Returns: (new_chunks, updated_chunks, source_doc_meta)
    """
    print(f"  Processing {doc_name}...")

    # Get source document metadata
    src_meta = get_source_doc_meta(doc_path, doc_name)

    # Check if document has changed
    meta = load_index_meta(CHROMA_DIR)
    doc_changed = True
    existing_chunk_count = 0
    if meta and not force and not reembed:
        for src in meta.source_docs:
            if src.name == doc_name and src.content_hash == src_meta.content_hash:
                doc_changed = False
                existing_chunk_count = src.chunk_count
                break

    if not doc_changed and not force and not reembed:
        print(f"    Skipped (unchanged)")
        src_meta.chunk_count = existing_chunk_count
        return [], [], src_meta

    if reembed:
        print(f"    Re-embedding (forced)")

    # Chunk the document
    chunks = chunk_document(doc_path, doc_name)
    print(f"    Created {len(chunks)} chunks")

    # Filter out unchanged chunks (by content hash)
    new_chunks = []
    updated_chunks = []

    if existing_hashes is None:
        existing_hashes = get_existing_hashes(collection)

    for chunk in chunks:
        if chunk.content_hash in existing_hashes and not force and not reembed:
            continue  # Skip unchanged

        if chunk.content_hash in existing_hashes:
            updated_chunks.append(chunk)
        else:
            new_chunks.append(chunk)

    print(f"    New: {len(new_chunks)}, Updated: {len(updated_chunks)}")

    # Embed and index new/updated chunks
    all_chunks = new_chunks + updated_chunks
    if all_chunks:
        texts = [c.text for c in all_chunks]
        embeddings = embedder.embed(texts)

        ids = [c.id for c in all_chunks]
        metadatas = [
            {
                "source_doc": c.source_doc,
                "page": c.page,
                "clause_id": c.clause_id or "",
                "section": c.section or "",
                "content_hash": c.content_hash,
            }
            for c in all_chunks
        ]

        # Upsert into Chroma
        collection.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas,
        )

        # Update existing hashes
        for c in all_chunks:
            existing_hashes.add(c.content_hash)

    # Update source doc meta with chunk count
    src_meta.chunk_count = len(chunks)

    return new_chunks, updated_chunks, src_meta


def ingest_all(
    force: bool = False,
    reembed_doc: Optional[str] = None,
) -> IndexMeta:
    """Run full ingestion pipeline."""
    start_time = time.time()

    client = get_chroma_client()
    collection = get_collection(client)
    embedder = Embedder()

    print(f"Using Chroma at: {CHROMA_DIR}")
    print(f"Using embed model: {embedder.model_name}")
    print(f"Embedding dimension: {embedder.dimension}")

    # Get existing hashes for idempotency
    existing_hashes = get_existing_hashes(collection)
    print(f"Existing chunks in index: {len(existing_hashes)}")

    all_new_chunks = 0
    all_updated_chunks = 0
    source_docs_meta = []

    # Determine which documents to process
    docs_to_process = CORPUS_DOCS
    if reembed_doc:
        if reembed_doc not in CORPUS_DOCS:
            print(f"Error: Unknown document '{reembed_doc}'. Available: {list(CORPUS_DOCS.keys())}")
            sys.exit(1)
        docs_to_process = {reembed_doc: CORPUS_DOCS[reembed_doc]}
        print(f"Re-embedding single document: {reembed_doc}")

    for doc_name, doc_path in docs_to_process.items():
        if not Path(doc_path).exists():
            print(f"  Warning: {doc_path} not found, skipping")
            continue

        new_chunks, updated_chunks, src_meta = ingest_document(
            doc_name, doc_path, collection, embedder,
            force=force, reembed=bool(reembed_doc),
            existing_hashes=existing_hashes,
        )
        all_new_chunks += len(new_chunks)
        all_updated_chunks += len(updated_chunks)
        source_docs_meta.append(src_meta)

    # If reembedding single doc, merge with existing meta for other docs
    if reembed_doc:
        meta = load_index_meta(CHROMA_DIR)
        if meta:
            existing_names = {s.name for s in source_docs_meta}
            for src in meta.source_docs:
                if src.name not in existing_names:
                    source_docs_meta.append(src)

    elapsed = time.time() - start_time
    total_chunks = collection.count()
    chunks_per_sec = total_chunks / elapsed if elapsed > 0 else 0

    print(f"\nIngestion complete in {elapsed:.2f}s")
    print(f"  Total chunks in index: {total_chunks}")
    print(f"  New chunks: {all_new_chunks}")
    print(f"  Updated chunks: {all_updated_chunks}")
    print(f"  Chunks/sec: {chunks_per_sec:.1f}")

    # Create and save index metadata
    index_meta = IndexMeta(
        build_time=time.time(),
        embed_model=embedder.model_name,
        total_chunks=total_chunks,
        chunks_per_second=chunks_per_sec,
        source_docs=source_docs_meta,
        index_dir=CHROMA_DIR,
    )

    save_index_meta(index_meta)
    update_prometheus_metrics(index_meta)

    print(f"Metadata saved to {CHROMA_DIR}/index_meta.json")
    print(f"Prometheus metrics updated")

    return index_meta


def main():
    import sys
    # Handle "python -m pipeline ingest" - sys.argv will be ['__main__.py', 'ingest', ...]
    # We need to skip the 'ingest' argument if present
    argv = sys.argv[1:]
    if argv and argv[0] == "ingest":
        argv = argv[1:]

    parser = argparse.ArgumentParser(
        description="PV-Triage Corpus Ingestion Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m pipeline ingest                    # Normal incremental ingest
  python -m pipeline ingest --force            # Force re-process all documents
  python -m pipeline ingest --reembed lamotrigine_package_insert.pdf  # Re-embed one doc
        """
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-processing of all documents, ignoring content hashes",
    )
    parser.add_argument(
        "--reembed",
        metavar="DOC",
        help="Re-embed a single document without rebuilding the whole index",
    )

    args = parser.parse_args(argv)

    try:
        ingest_all(force=args.force, reembed_doc=args.reembed)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()