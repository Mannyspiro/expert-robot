import tempfile
import unittest
from pathlib import Path

from merlin.hypothesis_ledger import HypothesisLedger
from merlin.lean_proof_receipt import LeanProofReceipt, record_lean_proof


def valid_receipt(**overrides):
    data = {
        "repository": "Mannyspiro/expert-robot",
        "commit_sha": "a" * 40,
        "workflow_run_id": 41761258888,
        "workflow_run_url": "https://github.com/Mannyspiro/expert-robot/actions/runs/41761258888",
        "workflow_name": "Formal Qualification",
        "conclusion": "success",
        "theorem": "THTGConditionalTheorems.continuous_attains_finite_maximum",
        "theorem_compiled": True,
        "axiom_audit_passed": True,
        "axioms": ["propext", "Classical.choice", "Quot.sound"],
        "source_sha256": "b" * 64,
    }
    data.update(overrides)
    return LeanProofReceipt.from_mapping(data)


class LeanProofReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = HypothesisLedger(Path(self.temp.name) / "hypotheses.sqlite3")
        self.ledger.create(
            "THTG-COND-MAX",
            "A continuous real-valued function on a nonempty closed interval attains a maximum.",
            assumptions=("a <= b", "S is continuous on [a,b]"),
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_receipt_records_proof_without_automatic_promotion(self):
        receipt = valid_receipt()
        evidence = record_lean_proof(self.ledger, "THTG-COND-MAX", receipt)
        self.assertEqual(evidence.kind, "proof")
        self.assertEqual(len(evidence.artifact_hash), 64)
        self.assertEqual(evidence.source_url, receipt.workflow_run_url)
        self.assertEqual(self.ledger.get("THTG-COND-MAX").status, "proposed")

    def test_successful_receipt_can_satisfy_explicit_formal_status_gate(self):
        record_lean_proof(self.ledger, "THTG-COND-MAX", valid_receipt())
        self.assertEqual(
            self.ledger.set_status("THTG-COND-MAX", "formally_verified").status,
            "formally_verified",
        )

    def test_rejects_failed_or_incomplete_workflow(self):
        for overrides in (
            {"conclusion": "failure"},
            {"theorem_compiled": False},
            {"axiom_audit_passed": False},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    valid_receipt(**overrides).validate()

    def test_rejects_unapproved_axioms_and_proof_escape(self):
        for axiom in ("sorryAx", "Classical.choice.someOtherAxiom", "Lean.ofReduceBool"):
            with self.subTest(axiom=axiom):
                with self.assertRaises(ValueError):
                    valid_receipt(axioms=["propext", axiom]).validate()

    def test_rejects_mismatched_run_url_and_run_id(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            valid_receipt(
                workflow_run_url="https://github.com/Mannyspiro/expert-robot/actions/runs/123"
            ).validate()

    def test_rejects_bad_commit_and_source_hash(self):
        with self.assertRaises(ValueError):
            valid_receipt(commit_sha="not-a-sha").validate()
        with self.assertRaises(ValueError):
            valid_receipt(source_sha256="not-a-hash").validate()

    def test_rejects_malformed_mapping(self):
        with self.assertRaises(ValueError):
            LeanProofReceipt.from_mapping({"theorem": "missing fields"})


if __name__ == "__main__":
    unittest.main()
