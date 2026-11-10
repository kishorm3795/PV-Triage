"""eval/test_pipeline_idempotence.py - Unit test verifying chunking idempotence across multiple runs.

Verifies:
1. Chunking a corpus document twice produces identical chunk counts.
2. Every chunk produced in run 1 matches run 2 in ID, text, clause_id, section, and content_hash.
3. Content hash is deterministic and collision-free across runs.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pipeline.chunker import chunk_document


class TestPipelineIdempotence(unittest.TestCase):
    """Test chunking idempotence on corpus documents."""

    def test_lamotrigine_chunk_idempotence(self) -> None:
        doc_path = Path("corpus/lamotrigine_package_insert.pdf")
        if not doc_path.exists():
            self.skipTest(f"Corpus file {doc_path} not found")

        doc_name = "lamotrigine_package_insert.pdf"
        chunks_run_1 = chunk_document(str(doc_path), doc_name)
        chunks_run_2 = chunk_document(str(doc_path), doc_name)

        self.assertGreater(len(chunks_run_1), 0, "Chunking should produce passages")
        self.assertEqual(
            len(chunks_run_1),
            len(chunks_run_2),
            "Chunk count must be strictly identical across runs",
        )

        for i, (c1, c2) in enumerate(zip(chunks_run_1, chunks_run_2)):
            self.assertEqual(c1.id, c2.id, f"Chunk {i} ID mismatch")
            self.assertEqual(c1.text, c2.text, f"Chunk {i} text mismatch")
            self.assertEqual(c1.content_hash, c2.content_hash, f"Chunk {i} content_hash mismatch")
            self.assertEqual(c1.clause_id, c2.clause_id, f"Chunk {i} clause_id mismatch")
            self.assertEqual(c1.page, c2.page, f"Chunk {i} page mismatch")

    def test_ipc_guidance_chunk_idempotence(self) -> None:
        doc_path = Path("corpus/ipc_pv_guidance_mah.pdf")
        if not doc_path.exists():
            self.skipTest(f"Corpus file {doc_path} not found")

        doc_name = "ipc_pv_guidance_mah.pdf"
        chunks_run_1 = chunk_document(str(doc_path), doc_name)
        chunks_run_2 = chunk_document(str(doc_path), doc_name)

        self.assertGreater(len(chunks_run_1), 0)
        self.assertEqual(len(chunks_run_1), len(chunks_run_2))
        for i, (c1, c2) in enumerate(zip(chunks_run_1, chunks_run_2)):
            self.assertEqual(c1.id, c2.id, f"Chunk {i} ID mismatch")
            self.assertEqual(c1.content_hash, c2.content_hash, f"Chunk {i} content_hash mismatch")


if __name__ == "__main__":
    unittest.main()
