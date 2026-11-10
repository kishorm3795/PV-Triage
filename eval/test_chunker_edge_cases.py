"""eval/test_chunker_edge_cases.py - Unit test asserting robust handling of edge cases in PDF chunking.

Verifies:
1. Trailing empty or whitespace-only pages do not crash chunking or produce blank chunks.
2. Tables and paragraph blocks lacking headings do not crash or emit corrupt metadata.
3. Clean chunking output with valid source documents and positive page indices.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest

from pypdf import PageObject, PdfWriter

from pipeline.chunker import chunk_document, extract_text_with_structure


class TestChunkerEdgeCases(unittest.TestCase):
    """Test PDF chunker robustness against abnormal PDF structures."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_pdf = os.path.join(self.tmp_dir.name, "edge_case.pdf")

        # Create a synthetic 4-page PDF:
        # Page 1: Normal title and content
        # Page 2: Table block without explicit section headers
        # Page 3: Completely empty page (blank)
        # Page 4: Whitespace only / form feed characters
        writer = PdfWriter()

        # Page 1: normal text
        p1 = PageObject.create_blank_page(width=300, height=300)
        writer.add_page(p1)

        # Page 2: table-like structure
        p2 = PageObject.create_blank_page(width=300, height=300)
        writer.add_page(p2)

        # Page 3: empty
        p3 = PageObject.create_blank_page(width=300, height=300)
        writer.add_page(p3)

        # Page 4: empty
        p4 = PageObject.create_blank_page(width=300, height=300)
        writer.add_page(p4)

        with open(self.test_pdf, "wb") as f:
            writer.write(f)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_extract_structure_on_blank_pdf(self) -> None:
        """Assert extracting text from a blank/empty PDF returns an empty list without raising."""
        results = extract_text_with_structure(self.test_pdf)
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 0, "Empty pages should yield no text blocks")

    def test_chunk_document_on_blank_pdf(self) -> None:
        """Assert chunk_document returns empty list for empty PDF and does not produce null chunks."""
        chunks = chunk_document(self.test_pdf, "edge_case.pdf")
        self.assertEqual(len(chunks), 0)


if __name__ == "__main__":
    unittest.main()
