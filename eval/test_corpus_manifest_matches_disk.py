"""eval/test_corpus_manifest_matches_disk.py - Verify docs/corpus.md manifest against disk."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent


class TestCorpusManifestMatchesDisk(unittest.TestCase):
    """Test that all files listed in docs/corpus.md exist with matching sha256 and size."""

    def test_corpus_manifest(self):
        corpus_md = ROOT / "docs" / "corpus.md"
        self.assertTrue(corpus_md.exists(), "docs/corpus.md must exist")

        content = corpus_md.read_text(encoding="utf-8")
        # Match table rows with corpus files
        pattern = r"`(corpus/[\w\.\-]+)`\s*\|\s*[^|]+\|\s*[^|]+\|\s*(\d+)\s*\|\s*([\d,]+)\s*\|\s*`([a-f0-9]{64})`"
        matches = re.findall(pattern, content)

        self.assertGreaterEqual(len(matches), 3, "docs/corpus.md must list at least 3 corpus files")

        for rel_path, pages_str, size_str, expected_sha in matches:
            file_path = ROOT / rel_path
            self.assertTrue(file_path.exists(), f"Corpus file {rel_path} must exist on disk")

            actual_size = file_path.stat().st_size
            expected_size = int(size_str.replace(",", ""))
            self.assertEqual(actual_size, expected_size, f"Size mismatch for {rel_path}")

            actual_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
            self.assertEqual(actual_sha, expected_sha, f"SHA256 mismatch for {rel_path}")


if __name__ == "__main__":
    unittest.main()
