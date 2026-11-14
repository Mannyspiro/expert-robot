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
        self.assertFalse(self.registry.resolve_artifact_ref(ref1)["is_current"])
        self.assertTrue(self.registry.resolve_artifact_ref(ref3)["is_current"])
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


class ArtifactProvenanceTests(unittest.TestCase):
    def test_exact_version_carries_immutable_source_and_artifact_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(Path(temp) / "registry")
            registry.register_project("merlin", "Merlin")
            provenance = {
                "schema": "merlin-artifact-provenance/1",
                "source_repo": "Mannyspiro/expert-robot",
                "source_commit": "a" * 40,
                "artifact_id": "directive-123",
                "artifact_kind": "directive-bundle",
                "artifact_schema": "merlin-directive-bundle/1",
            }
            raw = b'{"directive":"verified"}'
            registry.put_artifact(
                "merlin", "intents/directive-123.json", raw,
                "application/json", provenance=provenance,
            )
            ref = registry.artifact_ref("merlin", "intents/directive-123.json")
            resolution = registry.resolve_artifact_ref(ref)
            self.assertEqual(resolution["provenance"], provenance)
            self.assertTrue(resolution["verified"])

    def test_provenance_cannot_be_backfilled_or_changed_on_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(Path(temp) / "registry")
            registry.register_project("merlin", "Merlin")
            raw = b"same bytes"
            registry.put_artifact("merlin", "result.bin", raw)
            provenance = {
                "schema": "merlin-artifact-provenance/1",
                "source_repo": "Mannyspiro/expert-robot",
                "source_commit": "a" * 40,
                "artifact_id": "result-1",
                "artifact_kind": "research-result",
                "artifact_schema": "research-result/1",
            }
            with self.assertRaisesRegex(ValueError, "cannot attach or alter"):
                registry.put_artifact("merlin", "result.bin", raw, provenance=provenance)
            registry.put_artifact("merlin", "next.bin", raw, provenance=provenance)
            altered = dict(provenance, source_commit="b" * 40)
            with self.assertRaisesRegex(ValueError, "cannot attach or alter"):
                registry.put_artifact("merlin", "next.bin", raw, provenance=altered)

    def test_provenance_fields_and_digest_are_immutable(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(Path(temp) / "registry")
            registry.register_project("merlin", "Merlin")
            provenance = {
                "schema": "merlin-artifact-provenance/1",
                "source_repo": "Mannyspiro/expert-robot",
                "source_commit": "a" * 40,
                "artifact_id": "result-1",
                "artifact_kind": "research-result",
                "artifact_schema": "research-result/1",
            }
            registry.put_artifact("merlin", "result.bin", b"result", provenance=provenance)
            with self.assertRaises(sqlite3.IntegrityError):
                with sqlite3.connect(registry.db_path) as db:
                    db.execute(
                        "UPDATE artifact_version_provenance SET provenance_sha256=? "
                        "WHERE project_id=? AND logical_path=? AND version=1",
                        ("0" * 64, "merlin", "result.bin"),
                    )
            with self.assertRaises(sqlite3.IntegrityError):
                with sqlite3.connect(registry.db_path) as db:
                    db.execute(
                        "DELETE FROM artifact_version_provenance "
                        "WHERE project_id=? AND logical_path=? AND version=1",
                        ("merlin", "result.bin"),
                    )
