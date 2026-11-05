import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_registry import initialize, register_project
from geometry_receipt_registry import register_geometry_receipt
from cad_geometry_backend import canonical_sha


class GeometryReceiptRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / "merlin.sqlite3"
        initialize(self.database)
        register_project(self.database, "merlin-fixture", "Merlin fixture")
        with sqlite3.connect(self.database) as db:
            db.execute(
                "INSERT INTO intakes VALUES(?,?,?,?,?,?,?,?)",
                ("intake-1", "a"*64, "fixture.zip", 10, "b"*64,
                 "2026-11-04T00:00:00+00:00", 1, 10),
            )
            db.execute(
                "INSERT INTO artifacts VALUES(?,?,?,?,?)",
                ("intake-1", "part.step", "c"*64, 10, "cad_step"),
            )
            db.execute(
                "INSERT INTO project_intakes VALUES(?,?,?)",
                ("merlin-fixture", "intake-1", "2026-11-04T00:00:00+00:00"),
            )

    def tearDown(self):
        self.temp.cleanup()

    def _receipt(self):
        receipt = {
            "contract_version": "1.0",
            "job_id": "fixture-001",
            "input_sha256": "c"*64,
            "backend_id": "freecad",
            "backend_version": "0.20.2",
            "status": "completed",
            "artifacts": [{"path": "topology-report.json", "sha256": "d"*64, "size_bytes": 20}],
            "metrics": {},
            "limitations": ["geometry correctness not independently verified"],
            "verification": "artifact_hashes_checked;geometry_correctness_not_independently_verified",
        }
        receipt["receipt_sha256"] = canonical_sha(receipt)
        return receipt

    def test_registers_project_bound_execution_receipt_idempotently(self):
        receipt = self._receipt()
        first = register_geometry_receipt(self.database, "merlin-fixture", receipt)
        second = register_geometry_receipt(self.database, "merlin-fixture", receipt)
        self.assertEqual(first["status"] if "status" in first else first["result"], "completed")
        self.assertEqual(second["status"], "already_registered")
        self.assertFalse(first["engineering_correctness_asserted"])
        with sqlite3.connect(self.database) as db:
            row = db.execute(
                "SELECT result,evidence_class FROM verification_receipts"
            ).fetchone()
        self.assertEqual(row, ("completed", "geometry_execution"))

    def test_rejects_unregistered_input_artifact(self):
        receipt = self._receipt()
        receipt["input_sha256"] = "e"*64
        receipt["receipt_sha256"] = canonical_sha(receipt)
        with self.assertRaisesRegex(ValueError, "not registered"):
            register_geometry_receipt(self.database, "merlin-fixture", receipt)

    def test_rejects_tampered_receipt_digest(self):
        receipt = self._receipt()
        receipt["backend_version"] = "tampered"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            register_geometry_receipt(self.database, "merlin-fixture", receipt)


if __name__ == "__main__":
    unittest.main()
