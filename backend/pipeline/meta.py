"""pipeline/meta.py - Index metadata and Prometheus metrics for freshness tracking."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from prometheus_client import Gauge, CollectorRegistry

CHROMA_DIR = os.getenv("CHROMA_DIR", "./data/chroma")


# Prometheus metrics
INDEX_BUILD_TIMESTAMP = Gauge(
    "pv_index_build_timestamp_seconds",
    "Unix timestamp of last successful index build",
    ["index_name"]
)
INDEX_SOURCE_DOC_VERSION = Gauge(
    "pv_index_source_doc_version",
    "Version/hash of source document in index",
    ["index_name", "source_doc"]
)
INDEX_CHUNK_COUNT = Gauge(
    "pv_index_chunk_count",
    "Total number of chunks in the index",
    ["index_name"]
)
INDEX_CHUNKS_PER_SECOND = Gauge(
    "pv_index_chunks_per_second",
    "Chunks processed per second during last build",
    ["index_name"]
)
INDEX_EMBED_MODEL = Gauge(
    "pv_index_embed_model",
    "Embedding model used (encoded as hash)",
    ["index_name", "model_name"]
)


@dataclass
class SourceDocMeta:
    """Metadata for a source document."""
    name: str
    path: str
    size_bytes: int
    modified_time: float
    content_hash: str
    chunk_count: int = 0


@dataclass
class IndexMeta:
    """Metadata for the entire index."""
    build_time: float
    embed_model: str
    total_chunks: int
    chunks_per_second: float
    source_docs: List[SourceDocMeta]
    index_dir: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IndexMeta:
        """Parse index metadata supporting both old and new schema."""
        # Handle build_time (could be ISO string or float)
        build_time = data.get("build_time")
        if isinstance(build_time, str):
            from datetime import datetime
            build_time = datetime.fromisoformat(build_time.replace("Z", "+00:00")).timestamp()

        # Handle source_docs (new schema) or source_doc_versions (old schema)
        source_docs = []
        if "source_docs" in data:
            source_docs = [SourceDocMeta(**sd) for sd in data.get("source_docs", [])]
        elif "source_doc_versions" in data:
            # Old schema: convert source_doc_versions to SourceDocMeta
            for name, version in data.get("source_doc_versions", {}).items():
                # Extract hash from "sha256:xxx" format
                content_hash = version.split(":")[-1] if ":" in version else version
                source_docs.append(SourceDocMeta(
                    name=name,
                    path=f"corpus/{name}",
                    size_bytes=0,
                    modified_time=build_time or time.time(),
                    content_hash=content_hash,
                ))

        return cls(
            build_time=build_time or time.time(),
            embed_model=data.get("embed_model", "unknown"),
            total_chunks=data.get("total_chunks", data.get("chunk_count", 0)),
            chunks_per_second=data.get("chunks_per_second", data.get("chunks_per_sec", 0.0)),
            source_docs=source_docs,
            index_dir=data.get("index_dir", data.get("chroma_dir", CHROMA_DIR)),
        )


def compute_file_hash(filepath: str) -> str:
    """Compute SHA-256 hash of file content."""
    import hashlib
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def get_source_doc_meta(doc_path: str, doc_name: str) -> SourceDocMeta:
    """Get metadata for a source document."""
    stat = os.stat(doc_path)
    return SourceDocMeta(
        name=doc_name,
        path=doc_path,
        size_bytes=stat.st_size,
        modified_time=stat.st_mtime,
        content_hash=compute_file_hash(doc_path),
    )


def load_index_meta(index_dir: str) -> Optional[IndexMeta]:
    """Load index metadata from index_meta.json."""
    meta_path = Path(index_dir) / "index_meta.json"
    if not meta_path.exists():
        return None
    with open(meta_path, "r") as f:
        data = json.load(f)
    return IndexMeta.from_dict(data)


def save_index_meta(meta: IndexMeta) -> None:
    """Save index metadata to index_meta.json."""
    meta_path = Path(meta.index_dir) / "index_meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w") as f:
        json.dump(meta.to_dict(), f, indent=2)


def update_prometheus_metrics(meta: IndexMeta, registry: Optional[CollectorRegistry] = None) -> None:
    """Update Prometheus gauges with index metadata."""
    index_name = Path(meta.index_dir).name

    INDEX_BUILD_TIMESTAMP.labels(index_name=index_name).set(meta.build_time)
    INDEX_CHUNK_COUNT.labels(index_name=index_name).set(meta.total_chunks)
    INDEX_CHUNKS_PER_SECOND.labels(index_name=index_name).set(meta.chunks_per_second)
    INDEX_EMBED_MODEL.labels(index_name=index_name, model_name=meta.embed_model).set(1)

    for src in meta.source_docs:
        INDEX_SOURCE_DOC_VERSION.labels(
            index_name=index_name,
            source_doc=src.name
        ).set(float(src.modified_time))


def get_index_freshness(index_dir: str) -> Dict[str, Any]:
    """Get freshness info for the index."""
    meta = load_index_meta(index_dir)
    if not meta:
        return {"exists": False}

    return {
        "exists": True,
        "build_time": meta.build_time,
        "embed_model": meta.embed_model,
        "total_chunks": meta.total_chunks,
        "chunks_per_second": meta.chunks_per_second,
        "source_docs": [
            {
                "name": src.name,
                "modified_time": src.modified_time,
                "content_hash": src.content_hash,
                "chunk_count": src.chunk_count,
            }
            for src in meta.source_docs
        ],
    }