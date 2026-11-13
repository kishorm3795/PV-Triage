"""pipeline/embedder.py - Local embedding with sentence-transformers.

Uses the model specified by EMBED_MODEL environment variable (default: all-MiniLM-L6-v2).
Embeddings are computed locally, no external API calls.
"""

from __future__ import annotations

import os
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from pipeline.chunker import Chunk


class Embedder:
    """Local text embedder using sentence-transformers."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
        self._model: Optional[SentenceTransformer] = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the model."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: List[str]) -> np.ndarray:
        """Embed a list of texts, returning numpy array of shape (n, dim)."""
        return self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

    def embed_chunk(self, chunk: Chunk) -> np.ndarray:
        """Embed a single chunk."""
        return self.embed([chunk.text])[0]

    def embed_chunks(self, chunks: List[Chunk]) -> List[np.ndarray]:
        """Embed multiple chunks efficiently in batch."""
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embed(texts)
        return [embeddings[i] for i in range(len(chunks))]

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        dim_fn = getattr(self.model, "get_embedding_dimension", None) or getattr(
            self.model, "get_sentence_embedding_dimension", None
        )
        if callable(dim_fn):
            return int(dim_fn())
        return 384
