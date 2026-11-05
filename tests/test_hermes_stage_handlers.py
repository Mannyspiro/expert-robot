import tempfile
import unittest
from pathlib import Path

from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.research_evidence import ResearchEvidenceRecorder
from merlin.hermes_stage_handlers import build_hermes_stage_handlers


def fake_cace_verifier(**request):
    return {
        "verification_status": "verified",
        "artifact_sha256": request["artifact_sha256"],
        "receipt_artifact_sha256": "d" * 64,
        "promotion_authority": False,
    }


class Context:
    task_id = "task-17"
    hypothesis_id = "H-17"

    def __init__(self):
        self.events = []

    def emit_progress(self, summary, details=None):
        self.events.append(("progress", summary, details))

    def emit_tool_event(self, kind, name, details):
        self.events.append((kind, name, details))


class HermesStageHandlerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        registry = MerlinRegistry(root / "registry")
        registry.register_project("merlin", "Merlin")
        ledger = HypothesisLedger(root / "hypotheses.sqlite3")
        ledger.create("H-17", "The candidate invariant is preserved.")
        graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
        self.graph = graph
        self.ledger = ledger
        self.recorder = ResearchEvidenceRecorder(registry, ledger, graph)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_stage_handlers_record_verified_artifacts_and_graph_edges(self):
        outputs = {
            "research": (b"source evidence", "Source review complete."),
            "numerical_experiment": (b'{"samples":[1,2,3]}', "Numerical run complete."),
            "proof_search": (b"theorem candidate : True := True", "Proof candidate emitted."),
        }

        def executor_for(stage):
            def execute(task, context):
                return {
                    "artifact_bytes": outputs[stage][0],
                    "media_type": "application/octet-stream",
                    "summary": outputs[stage][1],
                    "metadata": {"engine": "test-injected:" + stage},
                }
            return execute

        handlers = build_hermes_stage_handlers(
            evidence_recorder=self.recorder,
            project_id="merlin",
            research_executor=executor_for("research"),
            numerical_experiment_executor=executor_for("numerical_experiment"),
            proof_search_executor=executor_for("proof_search"),
            artifact_verifier=fake_cace_verifier,
            repository="owner/repo",
            commit_sha="a" * 40,
            requester_id="merlin-worker",
        )
        self.assertEqual(set(handlers), {"research", "numerical_experiment", "proof_search"})
        expected_relations = {
            "research": "derived_from",
            "numerical_experiment": "tests",
            "proof_search": "formalizes",
        }
        for stage, handler in handlers.items():
            context = Context()
            result = handler({"stage": stage}, context)
            self.assertTrue(result["artifact"]["registry_verified"])
            self.assertEqual(result["evidence_refs"][0], "sha256:" + result["artifact"]["sha256"])
            self.assertEqual(result["graph_edge"]["relation"], expected_relations[stage])
            self.assertEqual(result["cace_verification"]["verification_status"], "verified")
            self.assertEqual(len(result["evidence_refs"]), 2)
            self.assertFalse(result["promotion_authority"])
            self.assertEqual(result["hypothesis_status_unchanged"], True)
            self.assertTrue(any(event[0] == "agent.tool.started" for event in context.events))
            self.assertTrue(any(event[0] == "agent.tool.completed" for event in context.events))

        snapshot = self.graph.export_snapshot()
        self.assertEqual(len(snapshot["nodes"]), 4)
        self.assertEqual(len(snapshot["edges"]), 3)
        self.assertEqual(self.ledger.get("H-17").status, "proposed")

    def test_registration_fails_closed_when_an_engine_is_missing(self):
        with self.assertRaisesRegex(ValueError, "callable"):
            build_hermes_stage_handlers(
                evidence_recorder=self.recorder,
                project_id="merlin",
                research_executor=lambda task, context: {},
                numerical_experiment_executor=None,
                proof_search_executor=lambda task, context: {},
                artifact_verifier=fake_cace_verifier,
                repository="owner/repo",
                commit_sha="a" * 40,
                requester_id="merlin-worker",
            )

    def test_handler_rejects_untyped_or_empty_executor_output(self):
        handlers = build_hermes_stage_handlers(
            evidence_recorder=self.recorder,
            project_id="merlin",
            research_executor=lambda task, context: {"artifact_bytes": b"", "summary": "ok"},
            numerical_experiment_executor=lambda task, context: {"artifact_bytes": b"x", "summary": "ok"},
            proof_search_executor=lambda task, context: {"artifact_bytes": b"x", "summary": "ok"},
            artifact_verifier=fake_cace_verifier,
            repository="owner/repo",
            commit_sha="a" * 40,
            requester_id="merlin-worker",
        )
        with self.assertRaisesRegex(ValueError, "non-empty immutable artifact_bytes"):
            handlers["research"]({"stage": "research"}, Context())


if __name__ == "__main__":
    unittest.main()
