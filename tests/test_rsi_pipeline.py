import base64
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from merlin.rsi_pipeline import (
    AppendOnlyLedger, SignedReceipt, ingest_hermes_failure,
    optional_adapter_status, paired_adapter_gain, sha256_hex,
)


def receipt(issuer, claims, key_id="test-key"):
    return SignedReceipt(1, issuer, key_id, datetime.now(timezone.utc).isoformat(),
                         claims, base64.b64encode(b"ok").decode("ascii"))


def verifier(payload, signature, pem):
    return signature == b"ok" and pem == "test-public-key"


class RSIPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = AppendOnlyLedger(Path(self.tmp.name) / "rsi.sqlite")
        self.keys = {"test-key": "test-public-key"}
        self.artifact = "a" * 64
        self.suite = "b" * 64

    def test_hermes_failure_requires_authenticated_bound_receipt(self):
        record = {"event_id": "h-17", "failure_class": "lean-timeout",
                  "summary": "Proof search exceeded its budget",
                  "source_repo": "Mannyspiro/expert-robot",
                  "source_commit": "c" * 40, "artifact_sha256": self.artifact}
        claims = {"subject": "hermes-failure:h-17", "source_repo": record["source_repo"],
                  "source_commit": record["source_commit"], "artifact_sha256": self.artifact,
                  "failure_class": "lean-timeout"}
        bad = receipt("hermes", {**claims, "source_commit": "d" * 40})
        with self.assertRaises(PermissionError):
            ingest_hermes_failure(self.ledger, record, bad, self.keys, verifier=verifier)
        good = receipt("hermes", claims)
        result = ingest_hermes_failure(self.ledger, record, good, self.keys, verifier=verifier)
        self.assertEqual(result["seq"], 1)
        self.assertTrue(self.ledger.verify_chain()["valid"])

    def test_candidate_lineage_requires_signed_source_receipt(self):
        candidate = "candidate-1"
        source = receipt("merlin-source", {"candidate_id": candidate,
                            "artifact_sha256": self.artifact, "source_commit": "c" * 40})
        with self.assertRaises(PermissionError):
            self.ledger.record_candidate(candidate_id=candidate, parent_candidate_id=None,
                source_receipt=source, artifact_sha256=self.artifact, generator="hermes",
                mutation={}, trusted_keys={}, verifier=verifier)
        event = self.ledger.record_candidate(candidate_id=candidate, parent_candidate_id=None,
            source_receipt=source, artifact_sha256=self.artifact, generator="hermes",
            mutation={"failure_class": "lean-timeout"}, trusted_keys=self.keys, verifier=verifier)
        self.assertEqual(event["seq"], 1)

    def test_promotion_requires_cace_and_separate_human_approval(self):
        candidate = "candidate-2"
        source = receipt("merlin-source", {"candidate_id": candidate,
                            "artifact_sha256": self.artifact})
        self.ledger.record_candidate(candidate_id=candidate, parent_candidate_id=None,
            source_receipt=source, artifact_sha256=self.artifact, generator="hermes",
            mutation={}, trusted_keys=self.keys, verifier=verifier)
        self.ledger.record_evaluation(candidate_id=candidate, suite_sha256=self.suite,
            metrics={"score": 0.9}, passed=True, evaluator_receipt_digest="eval-receipt")
        cace_claims = {"candidate_id": candidate, "candidate_digest": self.artifact,
            "benchmark_manifest_sha256": self.suite, "status": "pass",
            "authority": "verification-only"}
        cace = receipt("cace", cace_claims)
        self.ledger.record_cace_verification(candidate_id=candidate, receipt=cace,
            trusted_keys=self.keys, artifact_sha256=self.artifact, suite_sha256=self.suite,
            verifier=verifier)
        approval = receipt("merlin-approver", {"candidate_id": candidate,
            "candidate_digest": self.artifact, "action": "promote", "target": "qualified"})
        result = self.ledger.record_promotion(candidate_id=candidate,
            artifact_sha256=self.artifact, cace_receipt=cace, approval_receipt=approval,
            cace_keys=self.keys, approval_keys=self.keys, suite_sha256=self.suite,
            verifier=verifier)
        self.assertEqual(result["seq"], 4)
        self.assertTrue(self.ledger.verify_chain()["valid"])

    def test_promotion_fails_without_prior_cace_event(self):
        candidate = "candidate-3"
        source = receipt("merlin-source", {"candidate_id": candidate,
                            "artifact_sha256": self.artifact})
        self.ledger.record_candidate(candidate_id=candidate, parent_candidate_id=None,
            source_receipt=source, artifact_sha256=self.artifact, generator="hermes",
            mutation={}, trusted_keys=self.keys, verifier=verifier)
        self.ledger.record_evaluation(candidate_id=candidate, suite_sha256=self.suite,
            metrics={"score": 0.9}, passed=True, evaluator_receipt_digest="eval")
        cace = receipt("cace", {"candidate_id": candidate, "candidate_digest": self.artifact,
            "benchmark_manifest_sha256": self.suite, "status": "pass",
            "authority": "verification-only"})
        approval = receipt("merlin-approver", {"candidate_id": candidate,
            "candidate_digest": self.artifact, "action": "promote", "target": "qualified"})
        with self.assertRaises(PermissionError):
            self.ledger.record_promotion(candidate_id=candidate, artifact_sha256=self.artifact,
                cace_receipt=cace, approval_receipt=approval, cace_keys=self.keys,
                approval_keys=self.keys, suite_sha256=self.suite, verifier=verifier)

    def test_sqlite_ledger_rejects_update_and_delete(self):
        self.ledger.append("test.event", "x", {"value": 1})
        with sqlite3.connect(self.ledger.database) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE rsi_events SET entity_id='tampered' WHERE seq=1")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM rsi_events WHERE seq=1")

    def test_fixed_paired_adapter_gate_rejects_small_sample(self):
        result = paired_adapter_gain([0.5] * 5, [0.8] * 5)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "insufficient_paired_cases")

    def test_paired_adapter_gate_requires_reliable_improvement(self):
        result = paired_adapter_gain([0.5] * 25, [0.6] * 25)
        self.assertTrue(result["eligible"])
        no_gain = paired_adapter_gain([0.5] * 25, [0.501] * 25)
        self.assertFalse(no_gain["eligible"])

    def test_optional_adapter_does_not_enable_without_measurement(self):
        result = optional_adapter_status("merlin_nonexistent_optional_adapter")
        self.assertFalse(result["enabled"])


if __name__ == "__main__":
    unittest.main()
