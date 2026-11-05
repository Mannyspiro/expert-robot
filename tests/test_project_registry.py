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

    def test_bounded_read_only_project_index(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("a", "Alpha")
            registry.register_project("b", "Beta")
            registry.put_artifact("b", "notes.txt", b"hello")
            page = registry.list_projects(limit=1, offset=0)
            self.assertEqual(page["schema"], "merlin-project-index/1")
            self.assertEqual(page["total"], 2)
            self.assertEqual(page["items"][0]["project_id"], "b")
            self.assertEqual(page["items"][0]["artifact_count"], 1)
            self.assertEqual(registry.list_projects(limit=1, offset=1)["items"][0]["project_id"], "a")
            with self.assertRaises(ValueError):
                registry.list_projects(limit=0)

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
