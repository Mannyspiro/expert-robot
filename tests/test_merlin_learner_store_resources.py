import gc
import sqlite3
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from python.merlin.event_outbox import MerlinEventOutbox
from python.merlin.knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph
from python.merlin.learner_model import LearnerStore
from python.merlin.project_registry import MerlinRegistry


class TrackingConnection(sqlite3.Connection):
    closed_by_test = False

    def close(self):
        self.closed_by_test = True
        return super().close()


class MerlinSQLiteLifecycleTests(unittest.TestCase):
    def test_all_persistent_stores_close_every_sqlite_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_connect = sqlite3.connect
            connections = []

            def tracked_connect(*args, **kwargs):
                kwargs["factory"] = TrackingConnection
                connection = real_connect(*args, **kwargs)
                connections.append(connection)
                return connection

            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always", ResourceWarning)
                with patch("sqlite3.connect", side_effect=tracked_connect):
                    learner = LearnerStore(root / "learner.sqlite3")
                    learner.record_attempt({
                        "attempt_id": "attempt-1",
                        "learner_id": "learner-1",
                        "idea_id": "idea-1",
                        "problem_id": "problem-1",
                        "dimension": "recognition",
                        "score": 1.0,
                        "session_id": "session-1",
                        "response": {"answer": "correct"},
                    })
                    learner.estimate("learner-1", "idea-1", "recognition")
                    learner.attempts("learner-1")

                    graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
                    graph.add_node(GraphNode("project-1", "project", "Project", {}))
                    graph.add_node(GraphNode("claim-1", "claim", "Claim", {}))
                    graph.add_edge(GraphEdge("project-1", "supports", "claim-1", {}))
                    graph.get_node("project-1")
                    graph.neighbors("project-1")
                    graph.export_snapshot()

                    registry = MerlinRegistry(root / "registry")
                    registry.register_project("project-1", "Project")
                    registry.put_artifact("project-1", "notes.txt", b"evidence")
                    registry.verify_artifact(
                        __import__("hashlib").sha256(b"evidence").hexdigest()
                    )
                    registry.add_claim("claim-1", "A test claim", "unreviewed")
                    registry.relate("project-1", "contains", "claim-1")
                    registry.inventory("project-1")

                    outbox = MerlinEventOutbox(root / "outbox.sqlite3")
                    event = outbox.enqueue("key-1", "merlin.test", {"value": 1})
                    lease = outbox.claim_next("worker-1", topics=["merlin.test"])
                    outbox.acknowledge(
                        event["event_id"], "worker-1", lease["lease_token"],
                        result={"accepted": True},
                    )
                    outbox.get(event["event_id"])
                    outbox.counts()
                    outbox.recover_expired()

                gc.collect()

            leaked = [
                str(item.message) for item in captured
                if "unclosed database" in str(item.message).lower()
            ]
            self.assertEqual(leaked, [])
            self.assertGreater(len(connections), 0)
            unclosed = [index for index, connection in enumerate(connections)
                        if not connection.closed_by_test]
            self.assertEqual(unclosed, [], f"SQLite connections not closed: {unclosed}")


if __name__ == "__main__":
    unittest.main()
