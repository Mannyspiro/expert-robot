import tempfile
import unittest
from pathlib import Path

from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import GraphNode, MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.research_evidence import ResearchEvidenceRecorder


class ResearchEvidenceRecorderTests(unittest.TestCase):
    def test_result_links_artifact_hypothesis_and_graph_without_promoting_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = MerlinRegistry(root / "registry")
            registry.register_project("merlin", "Merlin")
            ledger = HypothesisLedger(root / "hypotheses.sqlite3")
            ledger.create("H-1", "A spectral invariant is preserved.")
            graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
            recorder = ResearchEvidenceRecorder(registry, ledger, graph)
            result = recorder.record(
                project_id="merlin", hypothesis_id="H-1",
                logical_path="experiments/run-1.json", content=b'{"result": 0.5}',
                evidence_kind="experiment", description="Deterministic synthetic experiment.",
            )
            self.assertTrue(result["artifact_verified"])
            self.assertEqual(result["artifact_ref"]["schema"], "merlin-artifact-ref/1")
            self.assertEqual(result["artifact_ref"]["version"], 1)
            self.assertEqual(result["artifact_ref"]["sha256"], result["artifact_sha256"])
            self.assertTrue(result["hypothesis_status_unchanged"])
            self.assertEqual(ledger.get("H-1").status, "proposed")
            snapshot = graph.export_snapshot()
            self.assertEqual(len(snapshot["nodes"]), 2)
            self.assertEqual(snapshot["edges"][0]["relation"], "tests")

    def test_record_replay_is_idempotent_for_the_same_exact_artifact_ref(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = MerlinRegistry(root / "registry")
            registry.register_project("p", "Project")
            ledger = HypothesisLedger(root / "hypotheses.sqlite3")
            ledger.create("H-10", "A replayed evidence claim.")
            graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
            recorder = ResearchEvidenceRecorder(registry, ledger, graph)
            first = recorder.record(
                project_id="p", hypothesis_id="H-10",
                logical_path="evidence/result.txt", content=b"same bytes",
                evidence_kind="source", description="Same exact source.",
            )
            second = recorder.record(
                project_id="p", hypothesis_id="H-10",
                logical_path="evidence/result.txt", content=b"same bytes",
                evidence_kind="source", description="Same exact source.",
            )
            self.assertEqual(first["artifact_ref"], second["artifact_ref"])
            self.assertEqual(first["evidence_id"], second["evidence_id"])
            self.assertEqual(len(ledger.evidence("H-10")), 1)
            self.assertEqual(len(registry.artifact_history("p", "evidence/result.txt")), 1)
            self.assertEqual(len(graph.export_snapshot()["edges"]), 1)

    def test_same_bytes_at_distinct_artifact_refs_remain_distinct_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = MerlinRegistry(root / "registry")
            registry.register_project("p", "Project")
            ledger = HypothesisLedger(root / "hypotheses.sqlite3")
            ledger.create("H-11", "Distinct source identities.")
            graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
            recorder = ResearchEvidenceRecorder(registry, ledger, graph)
            first = recorder.record(
                project_id="p", hypothesis_id="H-11",
                logical_path="evidence/one.txt", content=b"identical bytes",
                evidence_kind="source", description="Same words.",
            )
            second = recorder.record(
                project_id="p", hypothesis_id="H-11",
                logical_path="evidence/two.txt", content=b"identical bytes",
                evidence_kind="source", description="Same words.",
            )
            self.assertEqual(first["artifact_sha256"], second["artifact_sha256"])
            self.assertNotEqual(first["artifact_ref"], second["artifact_ref"])
            self.assertNotEqual(first["evidence_id"], second["evidence_id"])
            self.assertEqual(len(ledger.evidence("H-11")), 2)

    def test_existing_artifact_is_linked_without_copy_and_reuses_existing_graph_node(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = MerlinRegistry(root / "registry")
            registry.register_project("p", "Project")
            ledger = HypothesisLedger(root / "hypotheses.sqlite3")
            ledger.create("H-12", "Existing derived artifact.")
            graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
            recorder = ResearchEvidenceRecorder(registry, ledger, graph)
            registry.put_artifact("p", "knowledge/representation.json", b'{"derived":true}')
            ref = registry.artifact_ref("p", "knowledge/representation.json")
            graph.add_node(GraphNode(
                "existing-representation", "object_view", "representation",
                {"artifact_ref": ref}, evidence_class="derived_unverified",
            ))
            inventory_before = registry.inventory("p")
            first = recorder.record_existing_artifact(
                project_id="p", hypothesis_id="H-12", artifact_ref=ref,
                evidence_kind="source", description="Attach existing representation.",
                graph_node_id="existing-representation",
            )
            second = recorder.record_existing_artifact(
                project_id="p", hypothesis_id="H-12", artifact_ref=ref,
                evidence_kind="source", description="Attach existing representation.",
                graph_node_id="existing-representation",
            )
            self.assertEqual(inventory_before, registry.inventory("p"))
            self.assertEqual(first["artifact_ref"], ref)
            self.assertEqual(first["evidence_id"], second["evidence_id"])
            snapshot = graph.export_snapshot()
            self.assertEqual(len(snapshot["nodes"]), 2)
            self.assertEqual(len(snapshot["edges"]), 1)
            self.assertEqual(snapshot["edges"][0]["source_id"], "existing-representation")

    def test_counterexample_creates_contradiction_edge(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = MerlinRegistry(root / "registry")
            registry.register_project("p", "Project")
            ledger = HypothesisLedger(root / "hypotheses.sqlite3")
            ledger.create("H-2", "Every finite graph is regular.")
            graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
            recorder = ResearchEvidenceRecorder(registry, ledger, graph)
            result = recorder.record(project_id="p", hypothesis_id="H-2",
                                     logical_path="counterexample.json", content=b"{}",
                                     evidence_kind="counterexample",
                                     description="A non-regular finite graph.")
            self.assertEqual(result["graph_edge"]["relation"], "contradicts")

    def test_graph_identity_and_evidence_reference_distinguish_reversions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = MerlinRegistry(root / "registry")
            registry.register_project("p", "Project")
            ledger = HypothesisLedger(root / "hypotheses.sqlite3")
            ledger.create("H-3", "A measured invariant has value A.")
            graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
            recorder = ResearchEvidenceRecorder(registry, ledger, graph)
            first = recorder.record(project_id="p", hypothesis_id="H-3",
                                    logical_path="result.json", content=b"A",
                                    evidence_kind="experiment", description="first")
            registry.put_artifact("p", "result.json", b"B")
            third = recorder.record(project_id="p", hypothesis_id="H-3",
                                    logical_path="result.json", content=b"A",
                                    evidence_kind="experiment", description="reversion")
            self.assertEqual(first["artifact_sha256"], third["artifact_sha256"])
            self.assertEqual(first["artifact_ref"]["version"], 1)
            self.assertEqual(third["artifact_ref"]["version"], 3)
            self.assertNotEqual(first["graph_edge"]["source_id"],
                                third["graph_edge"]["source_id"])
            self.assertFalse(registry.resolve_artifact_ref(first["artifact_ref"])["is_current"])
            self.assertTrue(registry.resolve_artifact_ref(third["artifact_ref"])["is_current"])


if __name__ == "__main__":
    unittest.main()
