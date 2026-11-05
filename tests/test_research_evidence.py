import tempfile
import unittest
from pathlib import Path

from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
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
            self.assertTrue(result["hypothesis_status_unchanged"])
            self.assertEqual(ledger.get("H-1").status, "proposed")
            snapshot = graph.export_snapshot()
            self.assertEqual(len(snapshot["nodes"]), 2)
            self.assertEqual(snapshot["edges"][0]["relation"], "tests")

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


if __name__ == "__main__":
    unittest.main()
