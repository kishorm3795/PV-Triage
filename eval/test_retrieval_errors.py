"""eval/test_retrieval_errors.py - Test clean informative errors when Chroma directory or collection is missing."""

from __future__ import annotations

import unittest
from pathlib import Path
import tempfile
from pipeline.retrieval import ChromaRetriever


class TestRetrievalErrors(unittest.TestCase):
    """Test that ChromaRetriever raises clean informative errors when Chroma storage is invalid."""

    def test_missing_chroma_dir_raises_filenotfound(self):
        non_existent_dir = "/tmp/non_existent_chroma_dir_12345678"
        retriever = ChromaRetriever(chroma_dir=non_existent_dir)
        with self.assertRaises(FileNotFoundError) as ctx:
            _ = retriever.client
        self.assertIn("Chroma storage directory does not exist", str(ctx.exception))
        self.assertIn("python -m pipeline.ingest", str(ctx.exception))

    def test_empty_collection_raises_lookuperror(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            retriever = ChromaRetriever(chroma_dir=tmp_dir, collection_name="missing_pv_corpus")
            with self.assertRaises(LookupError) as ctx:
                _ = retriever.collection
            self.assertIn("not found in Chroma directory", str(ctx.exception))
            self.assertIn("missing_pv_corpus", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
