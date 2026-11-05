import tempfile
import unittest
from pathlib import Path

from merlin.event_outbox import MerlinEventOutbox
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import GraphNode, MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.registry_queries import MerlinReadAPI


class MerlinReadAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = MerlinRegistry(root / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.registry.put_artifact("merlin", "math/example.txt", b"proof candidate", "text/plain")
        self.hypotheses = HypothesisLedger(root / "hypotheses.sqlite3")
        self.hypotheses.create("H-1", "A test proposition.")
        self.graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
        self.graph.add_node(GraphNode("claim:H-1", "claim", "A test proposition", {}))
        self.outbox = MerlinEventOutbox(root / "outbox.sqlite3")
        self.api = MerlinReadAPI(self.registry, hypotheses=self.hypotheses,
                                 graph=self.graph, outbox=self.outbox)

    def tearDown(self):
        self.temp.cleanup()

    def test_project_and_artifact_queries_verify_content_address(self):
        project = self.api.project("merlin")
        self.assertEqual(project["project_id"], "merlin")
        artifact = self.api.artifact("merlin", "math/example.txt")
        self.assertTrue(artifact["verified"])
        self.assertEqual(artifact["content_bytes"], len(b"proof candidate"))

    def test_project_index_is_bounded_and_uses_canonical_registry(self):
        self.registry.register_project("other", "Other project")
        page = self.api.projects(limit=1, offset=0)
        self.assertEqual(page["schema"], "merlin-project-index/1")
        self.assertEqual(page["total"], 2)
        self.assertEqual(len(page["items"]), 1)
        self.assertEqual(len(page["items"]), 1)
        all_projects = self.api.projects(limit=10)["items"]
        self.assertEqual({item["project_id"] for item in all_projects}, {"merlin", "other"})

    def test_hypothesis_and_graph_queries_are_read_only_views(self):
        self.assertEqual(self.api.hypothesis("H-1")["status"], "proposed")
        page = self.api.list_hypotheses(limit=1, offset=0)
        self.assertEqual(page["total"], 1)
        self.assertEqual(len(self.api.graph()["nodes"]), 1)
        self.assertEqual(self.hypotheses.get("H-1").status, "proposed")

    def test_outbox_status_and_project_snapshot(self):
        self.outbox.enqueue("task:1", "merlin.task", {"task_id": "1"})
        self.assertEqual(self.api.outbox_status()["counts"]["pending"], 1)
        snapshot = self.api.project_snapshot("merlin")
        self.assertEqual(snapshot["schema"], "merlin-project-query/1")
        self.assertEqual(snapshot["outbox"]["counts"]["pending"], 1)

    def test_pagination_bounds(self):
        with self.assertRaises(ValueError):
            self.api.list_hypotheses(limit=0)
        with self.assertRaises(ValueError):
            self.api.list_hypotheses(offset=-1)


if __name__ == "__main__":
    unittest.main()
