"""pipeline/retrieval.py - Retriever implementation for the frozen Retriever protocol.

Implements:
- search(query: str, k: int = 5) -> list[Passage]
- get_clause(clause_id: str) -> Passage | None

Uses ChromaDB for vector search with local sentence-transformers embeddings,
and hybrid lay-to-medical expansion via pipeline/synonyms.json.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from pipeline.embedder import Embedder
from shared.contracts import Passage, Retriever as RetrieverProtocol

logger = logging.getLogger("pipeline.retrieval")

CHROMA_DIR = os.getenv("CHROMA_DIR", "./data/chroma")
COLLECTION_NAME = "pv_corpus"
CHROMA_SETTINGS = Settings(anonymized_telemetry=False)


def get_chroma_client(chroma_dir: Optional[str] = None) -> chromadb.PersistentClient:
    """Get ChromaDB PersistentClient with shared standard settings."""
    target_dir = chroma_dir or CHROMA_DIR
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=target_dir, settings=CHROMA_SETTINGS)

# Known canonical clause aliases across team contracts and reference cases
CLAUSE_ALIASES: Dict[str, List[str]] = {
    "ndct-2019-second-sched-table1": [
        "ndct-2019-second-sched-table1",
        "Second Schedule, Table 1",
        "Second Schedule",
        "Fifth Schedule",
        "Table 1",
        "2.7.1",
    ],
    "ipc-pv-guidance-sec4-seriousness": [
        "ipc-pv-guidance-sec4-seriousness",
        "2.5.3.6",
        "Section 4.1",
        "Seriousness of the reaction",
        "Hospitalization",
    ],
    "lamotrigine-pi-sec4-8-undesirable": [
        "lamotrigine-pi-sec4-8-undesirable",
        "lamotrigine-pi-boxed-warning",
        "Boxed Warning",
        "5.1",
        "6.2",
        "Section 5.1",
        "Section 6.2",
        "adverse_reaction_terms",
    ],
    "ipc-pv-guidance-sec5-expectedness": [
        "ipc-pv-guidance-sec5-expectedness",
        "5.2",
        "Section 5.2",
        "Expectedness Assessment",
    ],
    "2.5.3.6": [
        "ipc-pv-guidance-sec4-seriousness",
        "2.5.3.6",
        "Seriousness of the reaction",
    ],
    "2.7.1": [
        "ipc-pv-guidance-sec2-7-1",
        "2.7.1",
        "Reporting time lines",
    ],
    "5.1": [
        "lamotrigine-pi-sec5-1",
        "5.1",
        "Serious Skin Rashes",
    ],
    "Boxed Warning": [
        "Boxed Warning",
        "lamotrigine-pi-boxed-warning",
        "lamotrigine-pi-sec4-8-undesirable",
    ],
}


def _load_synonyms() -> Dict[str, List[str]]:
    """Load lay-to-medical synonyms dictionary if present."""
    synonyms_path = Path(__file__).resolve().parent / "synonyms.json"
    if synonyms_path.exists():
        try:
            with open(synonyms_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.debug("Failed loading synonyms: %s", exc)
    return {}


class ChromaRetriever:
    """Retriever implementation using ChromaDB vector store conforming to Retriever protocol."""

    def __init__(
        self,
        chroma_dir: Optional[str] = None,
        collection_name: str = COLLECTION_NAME,
        embedder: Optional[Embedder] = None,
    ):
        self.chroma_dir = chroma_dir or CHROMA_DIR
        self.collection_name = collection_name
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection = None
        self._embedder = embedder or Embedder()
        self._synonyms = _load_synonyms()

    @property
    def client(self) -> chromadb.PersistentClient:
        if self._client is None:
            self._client = get_chroma_client(self.chroma_dir)
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_collection(self.collection_name)
        return self._collection

    def _expand_query(self, query: str) -> str:
        """Expand query with medical MedDRA synonyms if lay terms are present."""
        query_lower = query.lower()
        matched_synonyms = []

        for phrase, expansions in self._synonyms.items():
            if phrase in query_lower:
                matched_synonyms.extend(expansions[:2])

        if matched_synonyms:
            # Append distinct synonyms to query to bridge vocabulary gap
            seen = set(query_lower.split())
            new_terms = [t for t in matched_synonyms if t.lower() not in seen]
            if new_terms:
                return f"{query} {' '.join(new_terms)}"

        return query

    def search(self, query: str, k: int = 5) -> List[Passage]:
        """Search corpus for top-k passages matching the query."""
        expanded_query = self._expand_query(query)
        query_embedding = self._embedder.embed([expanded_query])[0]

        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        passages: List[Passage] = []
        if results.get("ids") and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                document = results["documents"][0][i] if results.get("documents") else ""
                distance = results["distances"][0][i] if results.get("distances") else 1.0

                # Cosine distance to similarity: 1.0 - distance
                score = max(0.0, 1.0 - distance)

                passage = Passage(
                    id=chunk_id,
                    text=document,
                    source_doc=metadata.get("source_doc", ""),
                    page=metadata.get("page"),
                    clause_id=metadata.get("clause_id") or None,
                    section=metadata.get("section") or None,
                    score=score,
                )
                passages.append(passage)

        return passages

    def get_clause(self, clause_id: str) -> Optional[Passage]:
        """Lookup a specific regulatory clause by exact identifier or standard alias."""
        # Tier 1: Exact clause_id match
        try:
            results = self.collection.get(
                where={"clause_id": clause_id},
                include=["documents", "metadatas"],
                limit=1,
            )
            if results.get("ids") and results["ids"]:
                chunk_id = results["ids"][0]
                metadata = results["metadatas"][0] if results.get("metadatas") else {}
                document = results["documents"][0] if results.get("documents") else ""
                return Passage(
                    id=chunk_id,
                    text=document,
                    source_doc=metadata.get("source_doc", ""),
                    page=metadata.get("page"),
                    clause_id=metadata.get("clause_id") or clause_id,
                    section=metadata.get("section") or None,
                    score=1.0,
                )
        except Exception:
            pass

        # Tier 2: Search via canonical aliases
        aliases = CLAUSE_ALIASES.get(clause_id, [])
        for alias in aliases:
            try:
                results = self.collection.get(
                    where={"clause_id": alias},
                    include=["documents", "metadatas"],
                    limit=1,
                )
                if results.get("ids") and results["ids"]:
                    chunk_id = results["ids"][0]
                    metadata = results["metadatas"][0] if results.get("metadatas") else {}
                    document = results["documents"][0] if results.get("documents") else ""
                    return Passage(
                        id=chunk_id,
                        text=document,
                        source_doc=metadata.get("source_doc", ""),
                        page=metadata.get("page"),
                        clause_id=metadata.get("clause_id") or clause_id,
                        section=metadata.get("section") or None,
                        score=1.0,
                    )
            except Exception:
                continue

        # Tier 3: Scan all collection metadata for matching prefix/substring in clause_id or section
        try:
            all_entries = self.collection.get(include=["metadatas", "documents"])
            for doc, meta, cid in zip(
                all_entries.get("documents", []),
                all_entries.get("metadatas", []),
                all_entries.get("ids", []),
            ):
                meta_clause = (meta.get("clause_id") or "").lower()
                meta_section = (meta.get("section") or "").lower()
                target = clause_id.lower()

                if target in meta_clause or target in meta_section or target in cid.lower():
                    return Passage(
                        id=cid,
                        text=doc,
                        source_doc=meta.get("source_doc", ""),
                        page=meta.get("page"),
                        clause_id=meta.get("clause_id") or clause_id,
                        section=meta.get("section") or None,
                        score=1.0,
                    )
        except Exception:
            pass

        return None


# Re-export ChromaRetriever as Retriever class for standard consumer imports
Retriever = ChromaRetriever


def create_retriever() -> RetrieverProtocol:
    """Factory function to create a Retriever instance conforming to Retriever protocol."""
    return ChromaRetriever()


get_retriever = create_retriever

# Module-level singleton and functions for functional imports
_default_retriever: Optional[ChromaRetriever] = None


def _get_default_retriever() -> ChromaRetriever:
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = ChromaRetriever()
    return _default_retriever


def search(query: str, k: int = 5) -> List[Passage]:
    """Module-level search function matching Retriever protocol."""
    return _get_default_retriever().search(query, k=k)


def get_clause(clause_id: str) -> Optional[Passage]:
    """Module-level get_clause function matching Retriever protocol."""
    return _get_default_retriever().get_clause(clause_id)


__all__ = [
    "ChromaRetriever",
    "Retriever",
    "create_retriever",
    "get_retriever",
    "search",
    "get_clause",
]
