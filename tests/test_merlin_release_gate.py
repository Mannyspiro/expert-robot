"""Negative and positive controls for release evidence reporting."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python"))
from merlin_release_gate import REQUIRED, assess

DIGEST = "a" * 64
COMMIT = "b" * 64


class ReleaseGateTests(unittest.TestCase):
    def entry(self):
        return {"status": "passed", "evidence_sha256": DIGEST,
                "evidence_locator": "docs/evidence/native/receipt.json",
                "source_commit": COMMIT}

    def test_missing_gates_fail_closed(self):
        result = assess({"gates": {}})
        self.assertFalse(result["ready_for_independent_review"])
        self.assertTrue(all(v == "missing" for v in result["gate_status"].values()))

    def test_all_reported_is_review_only(self):
        result = assess({"gates": {name: self.entry() for name in REQUIRED}})
        self.assertTrue(result["ready_for_independent_review"])
        self.assertIn("not independently verified", result["warning"])

    def test_missing_identity_rejects_pass(self):
        for field in ("evidence_sha256", "evidence_locator", "source_commit"):
            with self.subTest(field=field):
                item = self.entry()
                item.pop(field)
                result = assess({"gates": {name: item for name in REQUIRED}})
                self.assertFalse(result["ready_for_independent_review"])

    def test_claimed_pass_without_valid_hash_rejects(self):
        item = self.entry()
        item["evidence_sha256"] = "not-a-hash"
        self.assertEqual(assess({"gates": {REQUIRED[0]: item}})["gate_status"][REQUIRED[0]], "unqualified")

    def test_malformed_manifest_rejected(self):
        for value in (None, [], {"gates": []}):
            with self.assertRaises(ValueError):
                assess(value)


if __name__ == "__main__":
    unittest.main()
