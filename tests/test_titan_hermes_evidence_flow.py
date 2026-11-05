import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from merlin.cace_adapter import CaceVerificationAdapter
from merlin.event_outbox import MerlinEventOutbox
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.research_evidence import ResearchEvidenceRecorder
from merlin.hermes_stage_handlers import build_hermes_stage_handlers
from merlin.titan_crypto_lab import hermes_titan_research_executor


def signed_artifact_receipt(request):
    receipt = {
        "schema": "cace-artifact-verification/1",
        "repository": request["repository"],
        "commit_sha": request["commit_sha"],
        "artifact_sha256": request["artifact_sha256"],
        "artifact_kind": request["artifact_kind"],
        "artifact_schema": request["artifact_schema"],
        "logical_path": request["logical_path"],
        "verifier_id": "cace:independent-artifact-checker",
        "source_commit_verified": True,
        "artifact_digest_verified": True,
        "artifact_schema_validated": True,
        "artifact_content_verified": True,
        "verification_status": "verified",
    }
    body = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    receipt["receipt_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return receipt


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
    def test_exact_bundle_bytes_flow_through_registry_graph_and_cace_adapter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = MerlinRegistry(root / "registry")
            registry.register_project("merlin", "Merlin")
            ledger = HypothesisLedger(root / "hypotheses.sqlite3")
            ledger.create("H-TITAN-01", "Titan envelope structure is versioned and context-bound.")
            graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
            outbox = MerlinEventOutbox(root / "outbox.sqlite3")
            recorder = ResearchEvidenceRecorder(registry, ledger, graph)
            adapter = CaceVerificationAdapter(
                verify_transport=signed_artifact_receipt,
                registry=registry, outbox=outbox, graph=graph,
            )
            handlers = build_hermes_stage_handlers(
                evidence_recorder=recorder,
                project_id="merlin",
                research_executor=hermes_titan_research_executor,
                numerical_experiment_executor=lambda task, context: {},
                proof_search_executor=lambda task, context: {},
                artifact_verifier=adapter.verify_artifact,
                repository="Mannyspiro/expert-robot",
                commit_sha="a" * 40,
                requester_id="merlin-hermes",
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
            self.assertEqual(result["cace_verification"]["artifact_sha256"], artifact["sha256"])
            self.assertEqual(result["cace_verification"]["verification_status"], "verified")
            self.assertTrue(registry.verify_artifact(result["cace_verification"]["receipt_artifact_sha256"]))
            self.assertFalse(result["promotion_authority"])
            self.assertEqual(ledger.get("H-TITAN-01").status, "proposed")
            snapshot = graph.export_snapshot()
            self.assertEqual(len(snapshot["edges"]), 2)
            self.assertTrue(any(node["node_type"] == "proof_receipt" for node in snapshot["nodes"]))
            self.assertGreaterEqual(outbox.counts()["pending"], 1)


if __name__ == "__main__":
    unittest.main()
