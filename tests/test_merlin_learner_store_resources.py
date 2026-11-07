import gc
import tempfile
import unittest
import warnings
from pathlib import Path

from python.merlin.learner_model import LearnerStore
from python.merlin.interaction_learning import InteractionLearningStore
from python.merlin.knowledge_graph import MerlinKnowledgeGraph, GraphNode, GraphEdge
from python.merlin.project_registry import MerlinRegistry
from python.merlin.event_outbox import MerlinEventOutbox


class LearnerStoreResourceTests(unittest.TestCase):
    def test_all_store_operations_close_sqlite_connections(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "learner.sqlite3"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", ResourceWarning)
                store = LearnerStore(database)
                result = store.record_attempt({
                    "attempt_id": "attempt-1",
                    "learner_id": "learner-1",
                    "idea_id": "idea-1",
                    "problem_id": "problem-1",
                    "problem_version": "1",
                    "dimension": "recognition",
                    "score": 1.0,
                    "session_id": "session-1",
                    "response": {"answer_kind": "multiple_choice"},
                })
                self.assertEqual(result["state"], "recorded")
                estimate = store.estimate("learner-1", "idea-1", "recognition")
                self.assertEqual(estimate.observations, 1)
                self.assertEqual(len(store.attempts("learner-1", "idea-1")), 1)
                del store
                gc.collect()
            leaks = [item for item in caught if issubclass(item.category, ResourceWarning)]
            self.assertEqual(leaks, [])

            reopened = LearnerStore(database)
            self.assertEqual(len(reopened.attempts("learner-1", "idea-1")), 1)


    def test_core_metadata_stores_close_connections(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", ResourceWarning)
                interactions = InteractionLearningStore(root / "interactions.sqlite3")
                interactions.record_feedback({
                    "event_id": "feedback-1", "session_id": "session-1",
                    "task_type": "api_call", "domain": "software", "outcome": "success",
                })
                self.assertEqual(interactions.feedback_summary()["count"], 1)

                graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
                graph.add_node(GraphNode("source", "source", "Source", {}))
                graph.add_node(GraphNode("claim", "claim", "Claim", {}))
                graph.add_edge(GraphEdge("claim", "derived_from", "source", {}))
                self.assertEqual(len(graph.export_snapshot()["edges"]), 1)

                registry = MerlinRegistry(root / "registry")
                registry.register_project("project-1", "Merlin")
                self.assertEqual(registry.inventory("project-1")["project_id"], "project-1")

                outbox = MerlinEventOutbox(root / "outbox.sqlite3")
                outbox.enqueue("idempotency-1", "merlin.test", {"value": 1})
                self.assertEqual(outbox.counts()["pending"], 1)

                del interactions, graph, registry, outbox
                gc.collect()
            leaks = [item for item in caught if issubclass(item.category, ResourceWarning)]
            self.assertEqual(leaks, [])



if __name__ == "__main__":
    unittest.main()
