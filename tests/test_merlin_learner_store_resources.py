import gc
import hashlib
import sqlite3
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from python.merlin.academic_graph import AcademicGraphStore
from python.merlin.academic_source_store import AcademicSourceStore
from python.merlin.engineering_project_store import EngineeringProjectStore
from python.merlin.event_outbox import MerlinEventOutbox
from python.merlin.knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph
from python.merlin.hypothesis_ledger import HypothesisLedger
from python.merlin.interaction_learning import InteractionLearningStore
from python.merlin.learner_model import LearnerStore
from python.merlin.project_registry import MerlinRegistry
from python.merlin.proof_observatory import ProofObservatory


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
                    registry.verify_artifact(hashlib.sha256(b"evidence").hexdigest())
                    registry.add_claim("claim-1", "A test claim", "unreviewed")
                    registry.relate("project-1", "contains", "claim-1")
                    registry.inventory("project-1")

                    academic_sources = AcademicSourceStore(root / "academic-sources.sqlite3")
                    academic_sources.add(
                        source_url="https://example.edu/research",
                        institution="Example University",
                        institution_domain="example.edu",
                        source_type="research_group",
                        discovered_from="https://example.edu",
                    )
                    academic_sources.list()

                    academic_graph = AcademicGraphStore(root / "academic-graph.sqlite3")
                    academic_graph.stats()

                    engineering = EngineeringProjectStore(root / "engineering.sqlite3")
                    engineering.history("project-1")

                    hypotheses = HypothesisLedger(root / "hypotheses.sqlite3")
                    hypotheses.create("hypothesis-1", "A testable claim")
                    hypotheses.add_evidence("hypothesis-1", "assumption", "Assumption recorded")
                    hypotheses.evidence("hypothesis-1")
                    hypotheses.list_hypotheses()

                    interactions = InteractionLearningStore(root / "interactions.sqlite3")
                    interactions.preferences()
                    interactions.record_feedback({
                        "session_id": "session-1",
                        "task_type": "research",
                        "domain": "research",
                        "outcome": "success",
                        "event_id": "feedback-1",
                    })
                    interactions.feedback_summary()

                    with ProofObservatory(root / "proof-observatory.sqlite3") as proof:
                        self.assertTrue(proof.verify_chain())

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
