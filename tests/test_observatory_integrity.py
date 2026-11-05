import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from merlin.proof_observatory import ProofObservatory, canonical_json, sha256_text
from merlin.observatory_integrity import verify_database, verify_theorem_dag


def make_receipt():
    payload = {"schema": "merlin-cross-domain-benchmark-receipt-v1",
               "source_commit": "a" * 40, "domains": {"geometry": {"passed": True}},
               "all_passed": True}
    payload["receipt_sha256"] = sha256_text(canonical_json(payload))
    return payload


def make_dag():
    payload = {"schema": "merlin-theorem-dependency-dag-v1",
               "node_count": 2, "edge_count": 1,
               "nodes": [{"id": "A", "dependencies": []}, {"id": "B", "dependencies": ["A"]}],
               "edges": [{"theorem": "B", "depends_on": "A"}],
               "topological_order_dependencies_first": ["A", "B"]}
    payload["dag_sha256"] = sha256_text(canonical_json(payload))
    return payload


class ObservatoryIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "observatory.sqlite3"
        self.store = ProofObservatory(self.path)
        self.receipt = make_receipt()
        self.store.record_benchmark_receipt(self.receipt)
        self.dag = make_dag()
        self.store.record_link(__import__("merlin.proof_observatory", fromlist=["CrossDomainLink"]).CrossDomainLink(
            "B", "frame:1", "project:1", "b" * 64, "supports", self.receipt["receipt_sha256"]))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_valid_store_and_dag_pass(self):
        report = verify_database(self.path, self.dag)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["counts"]["benchmark_receipts"], 1)
        self.assertTrue(report["theorem_dag_checked"])

    def test_receipt_payload_tamper_is_detected(self):
        self.store.db.execute("UPDATE benchmark_receipts SET payload=?",
                              (canonical_json({**self.receipt, "all_passed": False}),))
        self.store.db.commit()
        report = verify_database(self.path)
        self.assertFalse(report["ok"])
        self.assertTrue(any("benchmark receipt" in item and "digest mismatch" in item for item in report["errors"]))

    def test_link_tamper_is_detected(self):
        self.store.db.execute("UPDATE cross_domain_links SET payload=?",
                              (canonical_json({"theorem_id": "tampered"}),))
        self.store.db.commit()
        report = verify_database(self.path)
        self.assertFalse(report["ok"])
        self.assertTrue(any("cross-domain link" in item and "digest mismatch" in item for item in report["errors"]))

    def test_dangling_receipt_reference_is_detected(self):
        self.store.db.execute("DELETE FROM benchmark_receipts")
        self.store.db.commit()
        report = verify_database(self.path)
        self.assertFalse(report["ok"])
        self.assertTrue(any("dangling benchmark receipt" in item for item in report["errors"]))

    def test_dag_dependency_and_hash_tampering_is_detected(self):
        broken = make_dag()
        broken["nodes"][1]["dependencies"] = ["missing"]
        report = verify_theorem_dag(broken)
        self.assertTrue(any("digest mismatch" in item for item in report))
        self.assertTrue(any("dangling theorem dependency" in item for item in report))

    def test_engineering_revision_is_reported_as_external_reference(self):
        report = verify_database(self.path)
        self.assertIn("preimages not stored", report["engineering_revision_hashes"])


if __name__ == "__main__":
    unittest.main()
