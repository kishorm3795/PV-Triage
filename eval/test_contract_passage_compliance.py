"""eval/test_contract_passage_compliance.py - Assert that pipeline Passage matches shared/contracts.py."""

from __future__ import annotations

import unittest
from pipeline.models import Passage as PipelinePassage
from pipeline.retrieval import search, get_clause
from shared.contracts import Passage as ContractPassage


class TestContractPassageCompliance(unittest.TestCase):
    """Test that pipeline Passage model and all retrieved items strictly conform to shared/contracts.py:Passage."""

    def test_pipeline_passage_model_conversion(self):
        p = PipelinePassage(
            id="test-clause-001",
            text="Statutory test passage content.",
            source_doc="ipc_pv_guidance_mah.pdf",
            page=32,
            clause_id="test-clause-001",
            section="Section 2.5.3.6",
            score=0.95,
        )
        contract_p = p.to_contract()
        self.assertIsInstance(contract_p, ContractPassage)
        self.assertEqual(contract_p.id, p.id)
        self.assertEqual(contract_p.text, p.text)
        self.assertEqual(contract_p.source_doc, p.source_doc)
        self.assertEqual(contract_p.page, p.page)
        self.assertEqual(contract_p.clause_id, p.clause_id)
        self.assertEqual(contract_p.section, p.section)
        self.assertEqual(contract_p.score, p.score)

    def test_retrieved_passages_conform_to_contract(self):
        # Search query
        passages = search("Lamotrigine severe rash hospitalization", k=3)
        self.assertGreater(len(passages), 0)

        for p in passages:
            # Must either be ContractPassage or have to_contract() producing ContractPassage
            if isinstance(p, ContractPassage):
                cp = p
            elif hasattr(p, "to_contract"):
                cp = p.to_contract()
            else:
                cp = ContractPassage.model_validate(p.__dict__)

            self.assertIsInstance(cp, ContractPassage)
            self.assertTrue(isinstance(cp.id, str) and len(cp.id) > 0)
            self.assertTrue(isinstance(cp.text, str) and len(cp.text) > 0)
            self.assertTrue(isinstance(cp.source_doc, str) and len(cp.source_doc) > 0)

    def test_get_clause_conforms_to_contract(self):
        p = get_clause("ipc-pv-guidance-sec4-seriousness")
        self.assertIsNotNone(p)
        cp = p if isinstance(p, ContractPassage) else (p.to_contract() if hasattr(p, "to_contract") else ContractPassage.model_validate(p.__dict__))
        self.assertIsInstance(cp, ContractPassage)
        self.assertEqual(cp.id, "ipc-pv-guidance-sec4-seriousness")
        self.assertIn("serious adverse event", cp.text.lower())


if __name__ == "__main__":
    unittest.main()
