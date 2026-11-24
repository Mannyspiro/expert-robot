"""Transport fixture tests; no native model or packaged executable runs."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/merlin"))
import offline_delivery as delivery


class OfflineDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "Merlin-fixture.zip"
        self.data = bytes(range(145))
        self.archive.write_bytes(self.data)
        self.parts = self.root / "parts"
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        for name in delivery.EVIDENCE:
            (self.evidence / name).write_text("synthetic transport fixture\n")
        (self.evidence / "native-smoke.json").write_text(json.dumps({"result": "pass"}))
        (self.evidence / "studio-ui-live-trace.json").write_text(json.dumps({
            "result": "pass", "source_commit": "a" * 40, "source_tree": "b" * 40}))
        (self.evidence / "ZIP_SHA256SUMS.txt").write_text(
            hashlib.sha256(self.data).hexdigest() + "  " + str(self.archive) + "\n")
        self.manifest = self.evidence / delivery.MANIFEST
        self.output = self.root / "joined.zip"

    def split(self):
        return delivery.split(self.archive, self.parts, self.evidence, "a" * 40, "b" * 40, part_bytes=64)

    def assemble(self):
        return delivery.assemble(self.manifest, self.parts, self.output, part_bytes=64)

    def test_three_part_round_trip_keeps_every_original_byte_and_evidence_digest(self):
        value = self.split()
        self.assertEqual([row["bytes"] for row in value["parts"]], [64, 64, 17])
        self.assertEqual({row["name"] for row in value["evidence"]}, delivery.EVIDENCE)
        result = self.assemble()
        self.assertEqual(self.output.read_bytes(), self.data)
        self.assertEqual(result["sha256"], hashlib.sha256(self.data).hexdigest())
        self.assertFalse(result["application_executed"])
        self.assertLess(delivery.PART_BYTES, delivery.ARTIFACT_BYTES)
        self.assertLessEqual(delivery.ARTIFACT_BYTES, 400 * 1024**2)

    def test_tampered_part_rejects_and_cleans_unpublished_output(self):
        value = self.split()
        path = self.parts / value["parts"][1]["name"]
        path.write_bytes(b"x" * path.stat().st_size)
        with self.assertRaisesRegex(ValueError, "part digest differs"):
            self.assemble()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob(".merlin-reassembly-*")), [])

    def test_modified_evidence_rejects_before_reassembly(self):
        self.split()
        (self.evidence / "native-smoke.json").write_text('{"result":"fail"}')
        with self.assertRaisesRegex(ValueError, "delivery evidence changed"):
            self.assemble()
        self.assertFalse(self.output.exists())

    def test_wrong_full_digest_and_unsafe_part_name_reject(self):
        value = self.split()
        value["archive"]["sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "full ZIP digest differs"):
            self.assemble()
        self.assertFalse(self.output.exists())
        value["parts"][0]["name"] = "../outside"
        self.manifest.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "invalid part identity"):
            self.assemble()

    def test_symlink_or_missing_part_rejects(self):
        value = self.split()
        first = self.parts / value["parts"][0]["name"]
        first.unlink()
        with self.assertRaisesRegex(ValueError, "missing or unknown delivery part"):
            self.assemble()
        first.symlink_to(self.archive)
        with self.assertRaisesRegex(ValueError, "non-regular or oversized"):
            self.assemble()

    def test_acceptance_failure_and_changed_original_zip_leave_no_parts(self):
        (self.evidence / "native-smoke.json").write_text('{"result":"fail"}')
        with self.assertRaisesRegex(ValueError, "must pass before splitting"):
            self.split()
        self.assertFalse(self.parts.exists())
        (self.evidence / "native-smoke.json").write_text('{"result":"pass"}')
        self.archive.write_bytes(b"x" * len(self.data))
        with self.assertRaisesRegex(ValueError, "original verified ZIP changed"):
            self.split()
        self.assertFalse(self.parts.exists())
        self.assertFalse(self.manifest.exists())

    def test_existing_output_or_parts_are_never_overwritten(self):
        self.split()
        self.output.write_bytes(b"keep")
        with self.assertRaisesRegex(ValueError, "output must be new"):
            self.assemble()
        self.assertEqual(self.output.read_bytes(), b"keep")
        with self.assertRaisesRegex(ValueError, "parts directory must be new"):
            self.split()

    def test_oversized_unknown_evidence_and_invalid_boundaries_reject(self):
        (self.evidence / "unknown.txt").write_text("not allowlisted")
        with self.assertRaisesRegex(ValueError, "unknown or missing evidence"):
            self.split()
        (self.evidence / "unknown.txt").unlink()
        (self.evidence / "native-studio-server.log").write_bytes(b"x" * (delivery.BLOCK_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "oversized delivery"):
            self.split()
        self.archive.write_bytes(b"x" * 128)
        with self.assertRaisesRegex(ValueError, "exactly three bounded parts"):
            self.split()


if __name__ == "__main__":
    unittest.main()
