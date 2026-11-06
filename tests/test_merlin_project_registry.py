import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from python.merlin.project_registry import MerlinRegistry


class CapabilityQualificationReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = MerlinRegistry(Path(self.temp.name) / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.artifact = b"pinned provider qualification evidence"
        self.artifact_digest = self.registry.put_artifact(
            "merlin", "evidence/provider-qualification.json", self.artifact,
            "application/json",
        )
        self.receipt = {
            "receipt_id": "qual-provider-v1",
            "capability_id": "model.local",
            "capability_version": "1.0.0",
            "provider": "local-llm",
            "model_revision": "sha256:provider-model-revision",
            "heldout_suite": "merlin-model-heldout-v1",
            "environment_sha256": hashlib.sha256(b"environment").hexdigest(),
            "artifact_digest": self.artifact_digest,
            "result": "passed",
            "signer_id": "runner-test-identity",
            "signed_at": 1800000000,
            "metrics": {"cases": 40, "passed": 40},
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_receipt_is_persisted_but_never_self_qualifies(self):
        result = self.registry.record_capability_qualification(self.receipt)
        self.assertEqual(result["status"], "pending_independent_verification")
        self.assertFalse(result["qualified"])
        self.assertFalse(result["idempotent_replay"])
        records = self.registry.capability_qualification_receipts("model.local")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["receipt"], self.receipt)
        self.assertFalse(records[0]["qualified"])
        self.assertEqual(records[0]["receipt_sha256"], result["receipt_sha256"])

    def test_same_receipt_replay_is_idempotent_and_content_reuse_conflicts(self):
        first = self.registry.record_capability_qualification(self.receipt)
        replay = self.registry.record_capability_qualification(self.receipt)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(first["receipt_sha256"], replay["receipt_sha256"])
        changed = dict(self.receipt, model_revision="different-revision")
        with self.assertRaisesRegex(ValueError, "reused"):
            self.registry.record_capability_qualification(changed)

    def test_artifact_must_exist_and_match_digest(self):
        missing = dict(self.receipt, artifact_digest="0" * 64)
        with self.assertRaisesRegex(ValueError, "artifact"):
            self.registry.record_capability_qualification(missing)
        path = self.registry.blobs / self.artifact_digest[:2] / self.artifact_digest[2:]
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "artifact"):
            self.registry.record_capability_qualification(self.receipt)

    def test_receipt_contract_rejects_bad_digest_result_and_timestamp(self):
        for changed in (
            dict(self.receipt, environment_sha256="not-a-digest"),
            dict(self.receipt, result="qualified"),
            dict(self.receipt, signed_at=True),
            dict(self.receipt, signer_id=""),
        ):
            with self.assertRaises(ValueError):
                self.registry.record_capability_qualification(changed)

    def test_receipt_rows_are_append_only(self):
        self.registry.record_capability_qualification(self.receipt)
        with self.registry._connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    "UPDATE capability_qualification_receipts SET capability_id=? WHERE receipt_id=?",
                    ("other.capability", "qual-provider-v1"),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    "DELETE FROM capability_qualification_receipts WHERE receipt_id=?",
                    ("qual-provider-v1",),
                )


if __name__ == "__main__":
    unittest.main()
