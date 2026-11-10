"""eval/test_synonym_expansion.py - Test that new lay phrases map to expected clinical terms."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent


class TestSynonymExpansion(unittest.TestCase):
    """Test that lay phrases expand to expected clinical MedDRA terms in pipeline/synonyms.json."""

    def setUp(self):
        syn_path = ROOT / "pipeline" / "synonyms.json"
        self.assertTrue(syn_path.exists(), "pipeline/synonyms.json must exist")
        self.synonyms = json.loads(syn_path.read_text(encoding="utf-8"))

    def test_swollen_throat_expansion(self):
        terms = self.synonyms.get("swollen throat", [])
        self.assertIn("angioedema", terms)

    def test_lips_cracked_open_expansion(self):
        terms = self.synonyms.get("lips cracked open", [])
        self.assertIn("mucosal erosions", terms)

    def test_low_white_blood_cells_expansion(self):
        terms = self.synonyms.get("low white blood cells", [])
        self.assertIn("neutropenia", terms)

    def test_severe_belly_pain_expansion(self):
        terms = self.synonyms.get("severe belly pain", [])
        self.assertIn("acute pancreatitis", terms)


if __name__ == "__main__":
    unittest.main()
