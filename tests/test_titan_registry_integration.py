import tempfile
import unittest
from pathlib import Path

from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.titan_crypto_lab import register_titan_research


class TitanRegistryIntegrationTests(unittest.TestCase):
    def test_research_matrix_is_registered_and_digest_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = MerlinRegistry(root / "registry")
            registry.register_project("merlin", "Merlin")
            graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
            result = register_titan_research(registry, graph, "merlin")
            self.assertTrue(result["artifact_verified"])
            self.assertTrue(registry.verify_artifact(result["artifact_sha256"]))
            self.assertEqual(result["scenario_count"], 5)
            self.assertEqual(result["research_track_count"], 4)
            self.assertEqual(result["evidence_class"], "unreviewed")
            artifact = graph.get_node(result["artifact_node_id"])
            self.assertEqual(artifact.node_type, "artifact")
            self.assertEqual(artifact.payload["sha256"], result["artifact_sha256"])
            self.assertEqual(len(graph.neighbors(result["module_node_id"])), 1)


if __name__ == "__main__":
    unittest.main()
