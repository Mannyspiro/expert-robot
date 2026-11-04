"""Tests for content-addressed Merlin evidence receipts."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from merlin.equation_atlas.receipts import sha256

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/research/real-world-equation-atlas/evidence-receipt.schema.json"

class EvidenceReceiptTests(unittest.TestCase):
    def test_sha256_matches_standard_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.txt"
            path.write_text("Merlin evidence", encoding="utf-8")
            expected = hashlib.sha256(b"Merlin evidence").hexdigest()
            self.assertEqual(sha256(path), expected)

    def test_receipt_schema_accepts_well_formed_provenance(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        digest = "a" * 64
        receipt = {
            "receipt_schema": "merlin-evidence-receipt/0.1",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "claim_scope": "synthetic reproducibility only",
            "git_commit": "local-unpinned",
            "git_ref": "local",
            "command": "python -m merlin.equation_atlas.experiments.baseline",
            "runtime": {"python": "3.x", "platform": "test"},
            "source_sha256": {"source.py": digest},
            "artifact": {"path": "baseline.json", "sha256": digest, "bytes": 12},
            "verification_boundary": ["Does not establish empirical validity."],
        }
        errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(receipt))
        self.assertEqual(errors, [])

    def test_receipt_schema_rejects_invalid_digest(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        digest = "not-a-hash"
        receipt = {
            "receipt_schema": "merlin-evidence-receipt/0.1",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "claim_scope": "test",
            "git_commit": "local",
            "git_ref": "local",
            "command": "test",
            "runtime": {"python": "3", "platform": "test"},
            "source_sha256": {},
            "artifact": {"path": "x", "sha256": digest, "bytes": 1},
            "verification_boundary": ["test"],
        }
        errors = list(Draft202012Validator(schema).iter_errors(receipt))
        self.assertTrue(errors)

if __name__ == "__main__":
    unittest.main()
