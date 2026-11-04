import tempfile
import unittest
from pathlib import Path

from merlin.hypothesis_ledger import HypothesisLedger


class HypothesisLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = HypothesisLedger(Path(self.temp.name) / "hypotheses.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_new_hypothesis_starts_proposed_and_persists(self):
        h = self.ledger.create(
            "H-001", "A spectral invariant is preserved under this transform.",
            mathematical_objects=("graph Laplacian", "linear operator"),
            relation="invariant_under",
            assumptions=("The graph is finite and undirected.",),
        )
        self.assertEqual(h.status, "proposed")
        self.assertEqual(self.ledger.get("H-001").mathematical_objects[0], "graph Laplacian")

    def test_status_requires_matching_evidence(self):
        self.ledger.create("H-002", "A conjectured bound holds.")
        with self.assertRaises(ValueError):
            self.ledger.set_status("H-002", "literature_checked")
        self.ledger.add_evidence("H-002", "source", "A public paper discusses the bound.",
                                 source_url="https://example.org/paper")
        self.assertEqual(self.ledger.set_status("H-002", "literature_checked").status,
                         "literature_checked")

    def test_formal_verification_requires_proof_hash(self):
        self.ledger.create("H-003", "A lemma follows from stated assumptions.")
        self.ledger.add_evidence("H-003", "proof", "Lean theorem checked.")
        with self.assertRaises(ValueError):
            self.ledger.set_status("H-003", "formally_verified")
        self.ledger.add_evidence("H-003", "proof", "Lean build artifact.",
                                 artifact_hash="0123456789abcdef0123456789abcdef")
        self.assertEqual(self.ledger.set_status("H-003", "formally_verified").status,
                         "formally_verified")

    def test_refutation_requires_counterexample(self):
        self.ledger.create("H-004", "Every tested graph has this property.")
        with self.assertRaises(ValueError):
            self.ledger.set_status("H-004", "refuted")
        self.ledger.add_evidence("H-004", "counterexample",
                                 "A finite graph violates the universal claim.")
        self.assertEqual(self.ledger.set_status("H-004", "refuted").status, "refuted")

    def test_conditional_status_requires_assumptions(self):
        self.ledger.create("H-005", "A result holds conditionally.")
        self.ledger.add_evidence("H-005", "assumption", "Compactness is assumed.")
        self.assertEqual(self.ledger.set_status("H-005", "conditional").status, "conditional")

    def test_rejects_non_https_source(self):
        self.ledger.create("H-006", "Claim.")
        with self.assertRaises(ValueError):
            self.ledger.add_evidence("H-006", "source", "Private or unsafe link.",
                                     source_url="http://example.org")


if __name__ == "__main__":
    unittest.main()
