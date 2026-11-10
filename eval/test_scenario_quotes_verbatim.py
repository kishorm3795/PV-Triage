"""eval/test_scenario_quotes_verbatim.py - Test that every supporting_quote in scenarios.jsonl exists verbatim in corpus text."""

from __future__ import annotations

import json
from pathlib import Path
import unittest
import pypdf

ROOT = Path(__file__).resolve().parent.parent


class TestScenarioQuotesVerbatim(unittest.TestCase):
    """Ensure every supporting_quote in eval/scenarios.jsonl is a verbatim substring of corpus text."""

    @classmethod
    def setUpClass(cls):
        corpus_dir = ROOT / "corpus"
        combined_text = []
        for pdf_file in sorted(corpus_dir.glob("*.pdf")):
            reader = pypdf.PdfReader(str(pdf_file))
            for page in reader.pages:
                text = page.extract_text() or ""
                if text:
                    combined_text.append(text)
        cls.normalized_corpus_text = " ".join(" ".join(combined_text).split()).lower()

    def test_all_scenario_quotes_exist_verbatim(self):
        scenarios_path = ROOT / "eval" / "scenarios.jsonl"
        self.assertTrue(scenarios_path.exists(), "eval/scenarios.jsonl must exist")

        lines = [line.strip() for line in scenarios_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(lines), 20)

        for idx, line in enumerate(lines, 1):
            scen = json.loads(line)
            quote = scen.get("supporting_quote", "")
            scen_id = scen.get("id", f"#{idx}")
            self.assertTrue(quote and len(quote) > 0, f"Scenario {scen_id} must have a non-empty supporting_quote")
            norm_quote = " ".join(quote.split()).lower()
            self.assertIn(
                norm_quote,
                self.normalized_corpus_text,
                f"Supporting quote for {scen_id} is not an exact verbatim substring of the corpus text: {quote[:60]}...",
            )


if __name__ == "__main__":
    unittest.main()
