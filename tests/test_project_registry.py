import sqlite3
import tempfile
import unittest
from pathlib import Path
from merlin.project_registry import MerlinRegistry


class MerlinRegistryTests(unittest.TestCase):
    def test_content_addressed_artifact_roundtrip_and_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("merlin", "Merlin", metadata={"domain": "research"})
            digest = registry.put_artifact("merlin", "notes/idea.md", b"research idea", "text/markdown")
            self.assertTrue(registry.verify_artifact(digest))
            inventory = registry.inventory("merlin")
            self.assertEqual(inventory["artifacts"][0]["digest"], digest)
            self.assertEqual(inventory["artifacts"][0]["logical_path"], "notes/idea.md")

    def test_blob_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            digest = registry.put_artifact("p", "x.bin", b"original")
            blob = registry.blobs / digest[:2] / digest[2:]
            blob.write_bytes(b"changed")
            self.assertFalse(registry.verify_artifact(digest))

    def test_rejects_path_traversal_and_unknown_project(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            with self.assertRaises(ValueError):
                registry.put_artifact("missing", "../escape", b"x")
            with self.assertRaises(KeyError):
                registry.put_artifact("missing", "valid.bin", b"x")


    def test_artifact_versions_are_append_only_and_reversion_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            first = registry.put_artifact("p", "math/result.json", b'{"value":1}', "application/json")
            second = registry.put_artifact("p", "math/result.json", b'{"value":2}', "application/json")
            self.assertEqual(registry.put_artifact(
                "p", "math/result.json", b'{"value":2}', "application/json"), second)
            third = registry.put_artifact("p", "math/result.json", b'{"value":1}', "application/json")
            history = registry.artifact_history("p", "math/result.json")
            self.assertEqual([item["version"] for item in history], [1, 2, 3])
            self.assertEqual([item["digest"] for item in history], [first, second, third])
            self.assertEqual([item["previous_digest"] for item in history],
                             [None, first, second])
            inventory = registry.inventory("p")
            self.assertEqual(inventory["artifacts"][0]["version"], 3)
            self.assertEqual(inventory["artifacts"][0]["digest"], third)

    def test_artifact_version_rows_reject_update_and_delete(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            digest = registry.put_artifact("p", "result.bin", b"v1")
            with self.assertRaises(sqlite3.IntegrityError):
                with sqlite3.connect(registry.db_path) as db:
                    db.execute(
                        "UPDATE artifact_versions SET digest=? "
                        "WHERE project_id=? AND logical_path=? AND version=1",
                        ("0" * 64, "p", "result.bin"),
                    )
            with self.assertRaises(sqlite3.IntegrityError):
                with sqlite3.connect(registry.db_path) as db:
                    db.execute(
                        "DELETE FROM artifact_versions WHERE project_id=? "
                        "AND logical_path=? AND version=1", ("p", "result.bin")
                    )
            self.assertEqual(registry.artifact_history("p", "result.bin")[0]["digest"], digest)

    def test_legacy_current_artifact_is_backfilled_as_version_one(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            digest = registry.put_artifact("p", "legacy.txt", b"legacy")
            with sqlite3.connect(registry.db_path) as db:
                db.execute("DROP TABLE artifact_versions")
            registry._initialize()
            history = registry.artifact_history("p", "legacy.txt")
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["version"], 1)
            self.assertEqual(history[0]["digest"], digest)
            self.assertIsNone(history[0]["previous_digest"])

    def test_artifact_history_rejects_unknown_project_and_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            with self.assertRaises(KeyError):
                registry.artifact_history("missing", "result.bin")
            registry.register_project("p", "Project")
            with self.assertRaises(ValueError):
                registry.artifact_history("p", "../outside")

    def test_relation_identity_is_idempotent_and_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            registry.relate("p", "contains", "artifact:x", {"scope": "v1"})
            registry.relate("p", "contains", "artifact:x", {"scope": "v1"})
            with self.assertRaisesRegex(ValueError, "different metadata"):
                registry.relate("p", "contains", "artifact:x", {"scope": "v2"})


if __name__ == "__main__":
    unittest.main()
