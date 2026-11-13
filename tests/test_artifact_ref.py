import tempfile
import unittest
from pathlib import Path

from merlin.artifact_ref import ArtifactRef
from merlin.project_registry import MerlinRegistry


class ArtifactRefTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = MerlinRegistry(Path(self.temp.name) / "registry")
        self.registry.register_project("merlin", "Merlin")

    def tearDown(self):
        self.temp.cleanup()

    def test_reference_pins_exact_version_after_path_advances(self):
        first = self.registry.put_artifact("merlin", "research/result.json", b'{"n":1}')
        ref1 = self.registry.artifact_ref("merlin", "research/result.json")
        second = self.registry.put_artifact("merlin", "research/result.json", b'{"n":2}')
        ref2 = self.registry.artifact_ref("merlin", "research/result.json")
        self.assertEqual(ref1["version"], 1)
        self.assertEqual(ref1["sha256"], first)
        self.assertEqual(ref2["version"], 2)
        self.assertEqual(ref2["sha256"], second)
        old = self.registry.resolve_artifact_ref(ref1)
        latest = self.registry.resolve_artifact_ref(ref2)
        self.assertTrue(old["verified"])
        self.assertFalse(old["is_current"])
        self.assertTrue(latest["is_current"])

    def test_same_digest_in_a_later_reversion_has_distinct_version_identity(self):
        digest_a = self.registry.put_artifact("merlin", "x.bin", b"A")
        self.registry.put_artifact("merlin", "x.bin", b"B")
        digest_a_again = self.registry.put_artifact("merlin", "x.bin", b"A")
        ref1 = self.registry.artifact_ref("merlin", "x.bin", 1)
        ref3 = self.registry.artifact_ref("merlin", "x.bin", 3)
        self.assertEqual(digest_a, digest_a_again)
        self.assertEqual(ref1["sha256"], ref3["sha256"])
        self.assertNotEqual(ref1["version"], ref3["version"])
        self.assertEqual(self.registry.resolve_artifact_ref(ref3)["artifact_ref"], ref3)

    def test_wrong_version_or_digest_is_rejected(self):
        self.registry.put_artifact("merlin", "x.bin", b"A")
        self.registry.put_artifact("merlin", "x.bin", b"B")
        ref = self.registry.artifact_ref("merlin", "x.bin", 1)
        forged = dict(ref, sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.registry.resolve_artifact_ref(forged)
        wrong_version = dict(ref, version=2)
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.registry.resolve_artifact_ref(wrong_version)

    def test_unknown_version_and_tampered_blob_fail_closed(self):
        digest = self.registry.put_artifact("merlin", "x.bin", b"A")
        with self.assertRaises(KeyError):
            self.registry.artifact_ref("merlin", "x.bin", 2)
        ref = self.registry.artifact_ref("merlin", "x.bin")
        blob = self.registry.blobs / digest[:2] / digest[2:]
        blob.write_bytes(b"tampered")
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            self.registry.resolve_artifact_ref(ref)

    def test_reference_schema_and_path_validation_are_strict(self):
        with self.assertRaisesRegex(ValueError, "exactly"):
            ArtifactRef.from_mapping({"schema": ArtifactRef.SCHEMA, "project_id": "p"})
        for path in ("../escape", "/absolute", "a/../b", "a\\b", "a//b"):
            with self.assertRaises(ValueError):
                ArtifactRef("p", path, 1, "a" * 64)
        with self.assertRaises(ValueError):
            ArtifactRef("p", "ok.bin", True, "a" * 64)
        with self.assertRaises(ValueError):
            ArtifactRef("p", "ok.bin", 1, "A" * 64)


if __name__ == "__main__":
    unittest.main()
