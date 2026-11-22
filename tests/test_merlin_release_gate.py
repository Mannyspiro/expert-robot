"""Real filesystem positive and adversarial controls for Merlin release reporting."""
import hashlib
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python"))
from merlin_release_gate import REQUIRED, assess

COMMIT = "b" * 40


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.file = self.root / "receipt.json"
        self.file.write_bytes(b'{"test":"passed"}')

    def entry(self):
        return {"status": "passed", "evidence_sha256": hashlib.sha256(self.file.read_bytes()).hexdigest(),
                "evidence_locator": "receipt.json", "source_commit": COMMIT}

    def manifest(self):
        gates = {}
        for name in REQUIRED:
            receipt = self.root / (name + ".json")
            receipt.write_bytes(self.file.read_bytes())
            item = self.entry()
            item["evidence_locator"] = receipt.name
            gates[name] = item
        return {"gates": gates}

    def test_missing_gates_fail_closed(self):
        result = assess({"gates": {}}, self.root)
        self.assertFalse(result["ready_for_independent_review"])
        self.assertTrue(all(v == "missing" for v in result["gate_status"].values()))

    def test_all_bytes_verified_is_review_only(self):
        result = assess(self.manifest(), self.root)
        self.assertTrue(result["ready_for_independent_review"])
        self.assertIn("NOT verified", result["warning"])

    def test_missing_identity_rejects_pass(self):
        for field in ("evidence_sha256", "evidence_locator", "source_commit"):
            with self.subTest(field=field):
                manifest = self.manifest()
                manifest["gates"][REQUIRED[0]].pop(field)
                self.assertFalse(assess(manifest, self.root)["ready_for_independent_review"])

    def test_tampered_file_rejected(self):
        manifest = self.manifest()
        (self.root / (REQUIRED[0] + ".json")).write_bytes(b'{"test":"failed"}')
        self.assertEqual(assess(manifest, self.root)["gate_status"][REQUIRED[0]], "digest_mismatch")

    def test_absent_file_rejected(self):
        manifest = self.manifest()
        (self.root / (REQUIRED[0] + ".json")).unlink()
        self.assertEqual(assess(manifest, self.root)["gate_status"][REQUIRED[0]], "evidence_unavailable")

    def test_path_traversal_rejected(self):
        manifest = self.manifest()
        manifest["gates"][REQUIRED[0]]["evidence_locator"] = "../receipt.json"
        self.assertFalse(assess(manifest, self.root)["ready_for_independent_review"])

    def test_absolute_path_rejected(self):
        manifest = self.manifest()
        manifest["gates"][REQUIRED[0]]["evidence_locator"] = str(self.file)
        self.assertFalse(assess(manifest, self.root)["ready_for_independent_review"])

    def test_symlink_rejected(self):
        manifest = self.manifest()
        link = self.root / "link.json"
        link.symlink_to(self.file)
        manifest["gates"][REQUIRED[0]]["evidence_locator"] = "link.json"
        self.assertFalse(assess(manifest, self.root)["ready_for_independent_review"])

    def test_symlink_parent_rejected(self):
        manifest = self.manifest()
        folder = self.root / "receipts"
        folder.mkdir()
        (folder / "receipt.json").write_bytes(self.file.read_bytes())
        (self.root / "shortcut").symlink_to(folder, target_is_directory=True)
        manifest["gates"][REQUIRED[0]]["evidence_locator"] = "shortcut/receipt.json"
        self.assertEqual(assess(manifest, self.root)["gate_status"][REQUIRED[0]], "evidence_unavailable")

    def test_regular_nested_receipt_accepted(self):
        manifest = self.manifest()
        folder = self.root / "receipts"
        folder.mkdir()
        (folder / "receipt.json").write_bytes(self.file.read_bytes())
        manifest["gates"][REQUIRED[0]]["evidence_locator"] = "receipts/receipt.json"
        self.assertTrue(assess(manifest, self.root)["ready_for_independent_review"])

    def test_commit_mismatch_rejected(self):
        manifest = self.manifest()
        manifest["gates"][REQUIRED[0]]["source_commit"] = "c" * 40
        self.assertFalse(assess(manifest, self.root)["ready_for_independent_review"])

    def test_digest_cannot_substitute_for_git_commit(self):
        # GitHub source repository uses 40-character Git object IDs, not 64-byte SHA-256 evidence IDs.
        for bad in ("e" * 64, "f" * 39, "G" * 40, "g" * 40, ""):
            with self.subTest(source_commit=bad):
                manifest = self.manifest()
                manifest["gates"][REQUIRED[0]]["source_commit"] = bad
                self.assertEqual(
                    assess(manifest, self.root)["gate_status"][REQUIRED[0]],
                    "unqualified",
                )

    def test_git_sha1_revision_review_only(self):
        manifest = self.manifest()
        self.assertEqual(len(COMMIT), 40)
        result = assess(manifest, self.root)
        self.assertTrue(result["ready_for_independent_review"])
        self.assertIn("NOT verified", result["warning"])

    def test_reused_receipt_rejected(self):
        manifest = self.manifest()
        manifest["gates"][REQUIRED[1]]["evidence_locator"] = manifest["gates"][REQUIRED[0]]["evidence_locator"]
        self.assertFalse(assess(manifest, self.root)["ready_for_independent_review"])

    def test_bad_hash_rejected(self):
        manifest = self.manifest()
        manifest["gates"][REQUIRED[0]]["evidence_sha256"] = "not-a-hash"
        self.assertFalse(assess(manifest, self.root)["ready_for_independent_review"])

    def test_malformed_manifest_rejected(self):
        for value in (None, [], {"gates": []}):
            with self.assertRaises(ValueError):
                assess(value, self.root)


    def test_oversized_evidence_rejected(self):
        from merlin_release_gate import MAX_EVIDENCE_BYTES
        manifest = self.manifest()
        oversized = self.root / (REQUIRED[0] + ".json")
        with oversized.open("wb") as stream:
            stream.truncate(MAX_EVIDENCE_BYTES + 1)
        self.assertEqual(
            assess(manifest, self.root)["gate_status"][REQUIRED[0]],
            "evidence_unavailable",
        )

    def test_nonregular_fifo_rejected(self):
        import os
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO unsupported on this host")
        manifest = self.manifest()
        fifo = self.root / "receipt.pipe"
        os.mkfifo(fifo)
        manifest["gates"][REQUIRED[0]]["evidence_locator"] = fifo.name
        self.assertEqual(
            assess(manifest, self.root)["gate_status"][REQUIRED[0]],
            "evidence_unavailable",
        )

    def test_windows_style_traversal_rejected(self):
        manifest = self.manifest()
        manifest["gates"][REQUIRED[0]]["evidence_locator"] = r"..\\receipt.json"
        self.assertEqual(
            assess(manifest, self.root)["gate_status"][REQUIRED[0]],
            "evidence_unavailable",
        )


if __name__ == "__main__":
    unittest.main()
