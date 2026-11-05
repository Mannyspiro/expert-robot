import sqlite3
import tempfile
import unittest
from pathlib import Path

from merlin.project_registry import ArtifactConflict, MerlinRegistry


class MerlinRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = MerlinRegistry(self.temp.name)
        self.registry.register_project("p", "Project")

    def test_content_addressed_artifact_roundtrip_and_inventory(self):
        digest = self.registry.put_artifact("p", "notes/idea.md", b"research idea", "text/markdown")
        self.assertTrue(self.registry.verify_artifact(digest))
        inventory = self.registry.inventory("p")
        self.assertEqual(inventory["artifacts"][0]["digest"], digest)
        self.assertEqual(inventory["artifacts"][0]["logical_path"], "notes/idea.md")
        self.assertEqual(inventory["artifacts"][0]["generation"], 1)
        self.assertEqual(self.registry.get_artifact_bytes(digest), b"research idea")

    def test_blob_tampering_is_detected(self):
        digest = self.registry.put_artifact("p", "x.bin", b"original")
        blob = self.registry.blobs / digest[:2] / digest[2:]
        blob.write_bytes(b"changed")
        self.assertFalse(self.registry.verify_artifact(digest))

    def test_rejects_path_traversal_and_unknown_project(self):
        with self.assertRaises(ValueError):
            self.registry.put_artifact("missing", "../escape", b"x")
        with self.assertRaises(KeyError):
            self.registry.put_artifact("missing", "valid.bin", b"x")

    def test_put_is_idempotent_but_refuses_silent_overwrite(self):
        first = self.registry.put_artifact("p", "same.txt", b"v1")
        self.assertEqual(self.registry.put_artifact("p", "same.txt", b"v1"), first)
        with self.assertRaises(ArtifactConflict):
            self.registry.put_artifact("p", "same.txt", b"v2")
        self.assertEqual(self.registry.get_artifact_bytes(first), b"v1")
        self.assertEqual(len(self.registry.artifact_history("p", "same.txt")), 1)

    def test_replace_requires_exact_digest_and_generation_cas(self):
        first = self.registry.put_artifact("p", "same.txt", b"v1")
        head = self.registry.get_artifact_head("p", "same.txt")
        second = self.registry.replace_artifact(
            "p", "same.txt", b"v2", expected_digest=first,
            expected_generation=1, actor="test", operation_id="op-1")
        self.assertNotEqual(first, second)
        self.assertEqual(self.registry.get_artifact_bytes(first), b"v1")
        self.assertEqual(self.registry.get_artifact_bytes(second), b"v2")
        self.assertEqual(self.registry.get_artifact_head("p", "same.txt")["generation"], 2)
        history = self.registry.artifact_history("p", "same.txt")
        self.assertEqual(len(history), 2)
        recovery_id = history[1]["pre_change_recovery_id"]
        self.assertTrue(recovery_id)
        snapshot = self.registry.get_recovery_point(recovery_id)
        self.assertEqual(snapshot["manifest"]["artifacts"][0]["sha256"], first)
        with self.assertRaises(ArtifactConflict):
            self.registry.replace_artifact(
                "p", "same.txt", b"v3", expected_digest=head["digest"],
                expected_generation=head["generation"], actor="stale", operation_id="op-2")
        self.assertEqual(self.registry.get_artifact_bytes(second), b"v2")

    def test_database_triggers_block_history_blob_and_head_deletion(self):
        first = self.registry.put_artifact("p", "protected.txt", b"v1")
        self.registry.replace_artifact(
            "p", "protected.txt", b"v2", expected_digest=first,
            expected_generation=1, actor="test", operation_id="op-protected")
        history = self.registry.artifact_history("p", "protected.txt")
        recovery_id = history[1]["pre_change_recovery_id"]
        with self.registry._connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE artifact_versions SET actor='tampered'")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM artifact_versions")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM artifacts")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM recovery_points WHERE recovery_id=?", (recovery_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM project_artifacts WHERE project_id='p' AND logical_path='protected.txt'")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE project_artifacts SET digest=? WHERE project_id='p' AND logical_path='protected.txt'",
                           (first,))

    def test_replace_requires_existing_head(self):
        with self.assertRaises(ArtifactConflict):
            self.registry.replace_artifact(
                "p", "missing.txt", b"x", expected_digest="0" * 64,
                expected_generation=1, actor="test", operation_id="op")

    def test_recovery_point_manifest_is_integrity_checked(self):
        digest = self.registry.put_artifact("p", "a.txt", b"data")
        manifest = {"project_id": "p", "artifacts": [{"path": "a.txt", "sha256": digest}]}
        manifest_digest = self.registry.add_recovery_point("rp-1", "p", manifest)
        result = self.registry.get_recovery_point("rp-1")
        self.assertEqual(result["manifest_digest"], manifest_digest)
        self.assertEqual(result["manifest"], manifest)

    def test_relation_identity_is_idempotent_and_immutable(self):
        self.registry.relate("p", "contains", "artifact:x", {"scope": "v1"})
        self.registry.relate("p", "contains", "artifact:x", {"scope": "v1"})
        with self.assertRaisesRegex(ValueError, "different metadata"):
            self.registry.relate("p", "contains", "artifact:x", {"scope": "v2"})


if __name__ == "__main__":
    unittest.main()
