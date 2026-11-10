"""eval/test_citation.py - Unit tests for pipeline/citation.py."""

from __future__ import annotations

import unittest
from pipeline.citation import resolve_citation, resolve_all_citations
from shared.contracts import Citation, Passage


class TestCitationResolution(unittest.TestCase):
    """Test citation resolution against retrieved passages."""

    def setUp(self):
        self.passage1 = Passage(
            id="ipc-pv-guidance-sec4-seriousness",
            text="A serious adverse event (SAE) or reaction is any untoward medical occurrence that results in death or hospitalization.",
            source_doc="ipc_pv_guidance_mah.pdf",
            page=32,
            clause_id="ipc-pv-guidance-sec4-seriousness",
        )
        self.passage2 = Passage(
            id="ndct-2019-second-sched-table1",
            text="Any serious unexpected adverse event shall be reported to the CLA within fifteen calendar days.",
            source_doc="ndct_rules_2019.pdf",
            page=229,
            clause_id="ndct-2019-second-sched-table1",
        )
        self.retrieved = [self.passage1, self.passage2]

    def test_valid_citation_resolves(self):
        c = Citation(
            passage_id="ipc-pv-guidance-sec4-seriousness",
            quote="results in death or hospitalization.",
        )
        ok, err = resolve_citation(c, self.retrieved)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_unretrieved_passage_id_fails(self):
        c = Citation(
            passage_id="non-existent-clause",
            quote="some quote",
        )
        ok, err = resolve_citation(c, self.retrieved)
        self.assertFalse(ok)
        self.assertIn("was not retrieved", err)

    def test_non_verbatim_quote_fails(self):
        c = Citation(
            passage_id="ipc-pv-guidance-sec4-seriousness",
            quote="This quote was fabricated and not in text.",
        )
        ok, err = resolve_citation(c, self.retrieved)
        self.assertFalse(ok)
        self.assertIn("not a verbatim match", err)

    def test_resolve_all_citations_success(self):
        c1 = Citation(
            passage_id="ipc-pv-guidance-sec4-seriousness",
            quote="A serious adverse event",
        )
        c2 = Citation(
            passage_id="ndct-2019-second-sched-table1",
            quote="within fifteen calendar days.",
        )
        passed, errors = resolve_all_citations([c1, c2], self.retrieved)
        self.assertTrue(passed)
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
