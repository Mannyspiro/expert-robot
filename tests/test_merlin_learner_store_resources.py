import gc
import sqlite3
import tempfile
import unittest
import warnings
from pathlib import Path

from python.merlin.learner_model import LearnerStore
from python.merlin.interaction_learning import InteractionLearningStore
from python.merlin.knowledge_graph import MerlinKnowledgeGraph, GraphNode, GraphEdge
from python.merlin.project_registry import MerlinRegistry
from python.merlin.event_outbox import MerlinEventOutbox


class TrackingConnection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.was_closed = False

    def close(self):
        self.was_closed = True
        super().close()


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



    def test_storage_contexts_explicitly_close_every_connection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            opened = []

            def tracked(path, **kwargs):
                connection = sqlite3.connect(path, factory=TrackingConnection, **kwargs)
                opened.append(connection)
                return connection

            learner = LearnerStore(root / "learner-tracked.sqlite3")
            def learner_connect():
                db = tracked(learner.path, timeout=30)
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA busy_timeout=30000")
                db.execute("PRAGMA journal_mode=WAL")
                return db
            learner._connect = learner_connect
            learner.record_attempt({
                "attempt_id": "a1", "learner_id": "l1", "idea_id": "i1",
                "problem_id": "p1", "dimension": "recognition", "score": 1,
                "session_id": "s1",
            })
            learner.estimate("l1", "i1", "recognition")
            learner.attempts("l1", "i1")

            interactions = InteractionLearningStore(root / "interactions-tracked.sqlite3")
            def interaction_connect():
                db = tracked(interactions.path, timeout=30)
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA busy_timeout=30000")
                db.execute("PRAGMA journal_mode=WAL")
                return db
            interactions._connect = interaction_connect
            interactions.record_feedback({
                "event_id": "f1", "session_id": "s1",
                "task_type": "api_call", "domain": "software", "outcome": "success",
            })
            interactions.feedback_summary()

            graph = MerlinKnowledgeGraph(root / "graph-tracked.sqlite3")
            def graph_connect():
                db = tracked(graph.path)
                db.execute("PRAGMA foreign_keys=ON")
                return db
            graph._connect = graph_connect
            graph.add_node(GraphNode("node-1", "source", "Source", {}))
            graph.export_snapshot()

            registry = MerlinRegistry(root / "registry-tracked")
            def registry_connect():
                db = tracked(registry.db_path)
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA foreign_keys=ON")
                return db
            registry._connect = registry_connect
            registry.register_project("project-1", "Merlin")
            registry.inventory("project-1")

            outbox = MerlinEventOutbox(root / "outbox-tracked.sqlite3")
            def outbox_connect():
                db = tracked(outbox.path, timeout=30)
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA busy_timeout=30000")
                return db
            outbox._connect = outbox_connect
            outbox.enqueue("key-1", "merlin.test", {"value": 1})
            outbox.counts()

            self.assertGreater(len(opened), 10)
            self.assertTrue(all(connection.was_closed for connection in opened))



if __name__ == "__main__":
    unittest.main()
