from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from merlin.knowledge_compression import store_knowledge_representation
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.registry_queries import MerlinReadAPI


class KnowledgeRepresentationReadAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = MerlinRegistry(self.root / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.graph = MerlinKnowledgeGraph(self.root / "knowledge-graph.sqlite3")
        self.source_bytes = b"Source bytes stay in the canonical artifact store."
        self.registry.put_artifact(
            "merlin", "sources/readme.txt", self.source_bytes, "text/plain",
        )
        self.source_ref = self.registry.artifact_ref("merlin", "sources/readme.txt")
        self.representation = store_knowledge_representation(
            self.registry,
            self.graph,
            project_id="merlin",
            representation_type="summary",
            payload={"summary": "A read-only query example."},
            source_refs=[self.source_ref],
            source_bindings=[{
                "artifact_ref": self.source_ref,
                "locator_type": "whole_artifact",
                "locator": "entire source",
            }],
            tool_id="read-api-test",
            tool_version="1.0",
            loss_character="lossy",
            source_repo="Mannyspiro/expert-robot",
            source_commit="c" * 40,
        )
        self.api = MerlinReadAPI(self.registry, graph=self.graph)

    def tearDown(self):
        self.temp.cleanup()

    def test_returns_verified_manifest_and_source_provenance_without_bytes(self):
        inventory_before = self.registry.inventory("merlin")
        graph_before = self.graph.export_snapshot()
        result = self.api.knowledge_representation(self.representation["representation_ref"])
        inventory_after = self.registry.inventory("merlin")
        graph_after = self.graph.export_snapshot()

        self.assertEqual(result["schema"], "merlin-knowledge-representation-query/1")
        self.assertTrue(result["verified"])
        self.assertEqual(result["verification_scope"], "artifact-integrity-only")
        self.assertEqual(result["authority"], "derived-representation-only")
        self.assertFalse(result["qualification"])
        self.assertFalse(result["source_bytes_included"])
        self.assertEqual(result["manifest"]["representation_id"], self.representation["representation_id"])
        self.assertEqual(result["producer_provenance"]["source_commit"], "c" * 40)
        self.assertEqual(len(result["sources"]), 1)
        source = result["sources"][0]
        self.assertTrue(source["resolution"]["verified"])
        self.assertEqual(source["artifact_ref"], self.source_ref)
        self.assertEqual(source["source_bindings"][0]["locator"], "entire source")
        self.assertNotIn("content", source)
        self.assertEqual(inventory_before, inventory_after)
        self.assertEqual(graph_before, graph_after)

    def test_rejects_tampered_representation_artifact_ref(self):
        bad_ref = dict(self.representation["representation_ref"])
        bad_ref["sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            self.api.knowledge_representation(bad_ref)

    def test_rejects_unknown_representation_reference(self):
        bad_ref = dict(self.representation["representation_ref"])
        bad_ref["logical_path"] = "knowledge/representations/" + "0" * 64 + ".json"
        with self.assertRaises(KeyError):
            self.api.knowledge_representation(bad_ref)


if __name__ == "__main__":
    unittest.main()
