import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.research_evidence import ResearchEvidenceRecorder
from merlin.hermes_stage_handlers import build_hermes_stage_handlers
from merlin.titan_crypto_lab import hermes_titan_research_executor


class Context:
    task_id = "titan-protocol-task-01"
    hypothesis_id = "H-TITAN-01"

    def __init__(self):
        self.events = []

    def emit_progress(self, summary, details=None):
        self.events.append(("progress", summary, details))

    def emit_tool_event(self, kind, name, details):
        self.events.append((kind, name, details))


class TitanHermesEvidenceFlowTests(unittest.TestCase):
    def test_exact_bundle_bytes_flow_through_registry_graph_and_cace_request(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = MerlinRegistry(root / "registry")
            registry.register_project("merlin", "Merlin")
            ledger = HypothesisLedger(root / "hypotheses.sqlite3")
            ledger.create("H-TITAN-01", "Titan envelope structure is versioned and context-bound.")
            graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
            recorder = ResearchEvidenceRecorder(registry, ledger, graph)
            cace_requests = []

            def cace_verifier(**request):
                cace_requests.append(request)
                return {
                    "verification_status": "verified",
                    "artifact_sha256": request["artifact_sha256"],
                    "receipt_artifact_sha256": "e" * 64,
                    "verification_scope": "test double: request identity binding only",
                    "promotion_authority": False,
                }

            handlers = build_hermes_stage_handlers(
                evidence_recorder=recorder,
                project_id="merlin",
                research_executor=hermes_titan_research_executor,
                numerical_experiment_executor=lambda task, context: {},
                proof_search_executor=lambda task, context: {},
                artifact_verifier=cace_verifier,
                repository="Mannyspiro/expert-robot",
                commit_sha="a" * 40,
                requester_id="merlin-test",
            )
            context = Context()
            result = handlers["research"](
                {"stage": "research", "objective": "Build Titan formal protocol model and vectors"},
                context,
            )
            artifact = result["artifact"]
            blob = registry.blobs / artifact["sha256"][:2] / artifact["sha256"][2:]
            raw = blob.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), artifact["sha256"])
            report = json.loads(raw.decode("utf-8"))
            self.assertEqual(report["bundle"]["schema"], "titan-protocol-bundle/1")
            self.assertEqual(report["deterministic_model_verification"]["vectors_passed"], 5)
            self.assertEqual(cace_requests[0]["artifact_sha256"], artifact["sha256"])
            self.assertEqual(cace_requests[0]["logical_path"], artifact["logical_path"])
            self.assertEqual(result["cace_verification"]["artifact_sha256"], artifact["sha256"])
            self.assertFalse(result["promotion_authority"])
            self.assertEqual(ledger.get("H-TITAN-01").status, "proposed")
            self.assertEqual(len(graph.export_snapshot()["edges"]), 1)


if __name__ == "__main__":
    unittest.main()
