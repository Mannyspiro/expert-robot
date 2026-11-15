from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from merlin.knowledge_compression import (
    SCHEMA,
    canonical_json,
    store_knowledge_representation,
)
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry


class KnowledgeCompressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = MerlinRegistry(self.root / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.graph = MerlinKnowledgeGraph(self.root / "knowledge-graph.sqlite3")
        self.source_bytes = b"Primary source passage: a bounded example."
        self.source_digest = self.registry.put_artifact(
            "merlin", "research/source.txt", self.source_bytes, "text/plain",
        )
        self.source_ref = self.registry.artifact_ref("merlin", "research/source.txt")

    def tearDown(self):
        self.temp.cleanup()

    def _store(self, **overrides):
        args = {
            "registry": self.registry,
            "graph": self.graph,
            "project_id": "merlin",
            "representation_type": "summary",
            "payload": {"summary": "A bounded example.", "claims": []},
            "source_refs": [self.source_ref],
            "source_bindings": [{
                "artifact_ref": self.source_ref,
                "locator_type": "page",
                "locator": "1",
            }],
            "tool_id": "test-compressor",
            "tool_version": "0.1.0",
            "loss_character": "lossy",
            "source_repo": "Mannyspiro/expert-robot",
            "source_commit": "a" * 40,
        }
        args.update(overrides)
        return store_knowledge_representation(**args)

    def test_representation_is_stored_in_canonical_registry_and_graph(self):
        result = self._store()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["verification"], "not-verified")
        self.assertEqual(result["authority"], "derived-representation-only")
        stored = self.registry.read_artifact_ref(result["representation_ref"])
        manifest = json.loads(stored["content"])
        self.assertEqual(manifest["representation_id"], result["representation_id"])
        self.assertEqual(manifest["source_artifacts"], [self.source_ref])
        self.assertEqual(
            stored["resolution"]["provenance"]["artifact_schema"], SCHEMA,
        )

        node = self.graph.get_node(result["graph_node_id"])
        self.assertEqual(node.node_type, "object_view")
        self.assertEqual(node.evidence_class, "derived_unverified")
        edges = self.graph.neighbors(result["graph_node_id"], "out")
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["relation"], "derived_from")
        self.assertEqual(edges[0]["target_id"], result["source_graph_node_ids"][0])

    def test_exact_replay_is_idempotent(self):
        first = self._store()
        second = self._store()
        self.assertEqual(first["representation_id"], second["representation_id"])
        self.assertEqual(first["representation_ref"], second["representation_ref"])
        self.assertEqual(first["representation_digest"], second["representation_digest"])
        self.assertEqual(len(self.graph.export_snapshot()["nodes"]), 2)
        self.assertEqual(len(self.graph.export_snapshot()["edges"]), 1)

    def test_changed_payload_creates_a_distinct_immutable_representation(self):
        first = self._store()
        second = self._store(payload={"summary": "A different summary.", "claims": []})
        self.assertNotEqual(first["representation_id"], second["representation_id"])
        history = self.registry.artifact_history(
            "merlin",
            first["representation_ref"]["logical_path"],
        )
        self.assertEqual(len(history), 1)

    def test_source_digest_mismatch_fails_before_representation_write(self):
        tampered = dict(self.source_ref)
        tampered["sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            self._store(source_refs=[tampered], source_bindings=[{
                "artifact_ref": tampered,
                "locator_type": "page",
                "locator": "1",
            }])
        inventory = self.registry.inventory("merlin")
        self.assertEqual(len(inventory["artifacts"]), 1)

    def test_binding_must_point_to_declared_source_artifact(self):
        other_bytes = b"unrelated source"
        self.registry.put_artifact("merlin", "research/other.txt", other_bytes, "text/plain")
        other_ref = self.registry.artifact_ref("merlin", "research/other.txt")
        with self.assertRaisesRegex(ValueError, "outside source_artifacts"):
            self._store(source_bindings=[{
                "artifact_ref": other_ref,
                "locator_type": "section",
                "locator": "Methods",
            }])

    def test_rejects_unassessed_or_malformed_contract_fields(self):
        with self.assertRaises(ValueError):
            self._store(loss_character="lossless")
        with self.assertRaises(ValueError):
            self._store(source_commit="not-a-commit")
        with self.assertRaises(ValueError):
            self._store(source_bindings=[])
        with self.assertRaises(ValueError):
            canonical_json({"not-finite": float("nan")})

    def test_same_digest_different_artifact_refs_get_distinct_graph_nodes(self):
        self.registry.put_artifact("merlin", "research/alias.txt", self.source_bytes, "text/plain")
        alias_ref = self.registry.artifact_ref("merlin", "research/alias.txt")
        first = self._store()
        second = self._store(
            source_refs=[alias_ref],
            source_bindings=[{
                "artifact_ref": alias_ref,
                "locator_type": "whole_artifact",
                "locator": "entire source",
            }],
        )
        self.assertNotEqual(first["source_graph_node_ids"], second["source_graph_node_ids"])
        self.assertEqual(first["source_artifact_refs"][0]["sha256"], second["source_artifact_refs"][0]["sha256"])


if __name__ == "__main__":
    unittest.main()
