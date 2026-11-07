import tempfile
import unittest
from pathlib import Path

from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.research_evidence import ResearchEvidenceRecorder
from merlin.hermes_stage_handlers import build_hermes_stage_handlers, build_merlin_hermes_handlers


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
                    "metadata": {"engine": "test-injected:" + stage, "tool_identity": "test-injected:" + stage + "@1.0"},
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

    def test_standard_composition_registers_builtin_numerical_and_electrical_engines(self):
        handlers = build_merlin_hermes_handlers(
            evidence_recorder=self.recorder,
            project_id="merlin",
            research_executor=lambda task, context: {},
            proof_search_executor=lambda task, context: {},
            artifact_verifier=fake_cace_verifier,
            repository="owner/repo",
            commit_sha="a" * 40,
            requester_id="merlin-worker",
        )
        self.assertEqual(set(handlers), {
            "research", "numerical_experiment", "proof_search", "electrical_analysis"
        })

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


    def test_proof_search_routes_exact_claim_source_through_lean_then_cace(self):
        source = "theorem target : True := by trivial"
        claim = {
            "claim_id": "theorem-target",
            "formal_statement": source,
            "lean_source": source,
            "assumptions": ["none"],
            "falsifiability": ["Lean rejects malformed source"],
            "source_ids": ["paper:target"],
            "compilation_status": "compile_failed",
        }
        lean_calls = []
        cace_calls = []

        def proof_executor(task, context):
            return {
                "artifact_bytes": b"proof-search transcript",
                "summary": "Proof candidate emitted.",
                "metadata": {"theorem_claims": [claim], "tool_identity": "lean-proof-search@1.0"},
            }

        def lean_dispatcher(**request):
            lean_calls.append(request)
            return {"compilation_status": "compiled"}

        def theorem_verifier(**request):
            cace_calls.append(request)
            return {
                "verification_status": "verified",
                "artifact_sha256": request["artifact_sha256"],
                "receipt_artifact_sha256": "e" * 64,
                "promotion_authority": False,
            }

        handlers = build_hermes_stage_handlers(
            evidence_recorder=self.recorder,
            project_id="merlin",
            research_executor=lambda task, context: {
                "artifact_bytes": b"research", "summary": "Research complete.", "metadata": {"tool_identity": "research-engine@1.0"}, "metadata": {"tool_identity": "research-engine@1.0"}
            },
            numerical_experiment_executor=lambda task, context: {
                "artifact_bytes": b"experiment", "summary": "Experiment complete.", "metadata": {"tool_identity": "numerical-engine@1.0"}, "metadata": {"tool_identity": "numerical-engine@1.0"}
            },
            proof_search_executor=proof_executor,
            artifact_verifier=fake_cace_verifier,
            repository="owner/repo",
            commit_sha="a" * 40,
            requester_id="merlin-worker",
            lean_dispatcher=lean_dispatcher,
            lean_tool_version="Lean 4.34.0",
            theorem_verifier=theorem_verifier,
        )
        result = handlers["proof_search"]({"stage": "proof_search"}, Context())

        self.assertEqual(len(lean_calls), 1)
        self.assertEqual(lean_calls[0]["source"], source)
        self.assertEqual(lean_calls[0]["tool_version"], "Lean 4.34.0")
        dispatch_receipt = result["metadata"]["lean_dispatch_receipts"][0]
        self.assertEqual(dispatch_receipt["compilation_status"], "compiled")
        self.assertEqual(dispatch_receipt["verification_status"], "verified")
        self.assertEqual(lean_calls[0]["source_sha256"], dispatch_receipt["source_sha256"])
        self.assertTrue(self.recorder.registry.verify_artifact(dispatch_receipt["source_sha256"]))
        self.assertEqual(len(cace_calls), 1)
        self.assertEqual(cace_calls[0]["artifact_sha256"], dispatch_receipt["source_sha256"])
        self.assertEqual(result["cace_theorem_receipts"][0]["verification_status"], "verified")
        self.assertIn("sha256:" + dispatch_receipt["source_sha256"], result["evidence_refs"])
        self.assertFalse(result["promotion_authority"])

    def test_unconfigured_lean_dispatch_ignores_executor_compilation_claim(self):
        claim = {
            "claim_id": "blocked-claim",
            "formal_statement": "theorem blocked : True := by trivial",
            "lean_source": "theorem blocked : True := by sorry",
            "assumptions": ["none"],
            "falsifiability": ["Lean rejects unfinished proof"],
            "source_ids": ["paper:blocked"],
            "compilation_status": "compiled",
        }
        theorem_calls = []
        handlers = build_hermes_stage_handlers(
            evidence_recorder=self.recorder,
            project_id="merlin",
            research_executor=lambda task, context: {
                "artifact_bytes": b"research", "summary": "Research complete."
            },
            numerical_experiment_executor=lambda task, context: {
                "artifact_bytes": b"experiment", "summary": "Experiment complete."
            },
            proof_search_executor=lambda task, context: {
                "artifact_bytes": b"proof-search transcript",
                "summary": "Unfinished proof candidate emitted.",
                "metadata": {"theorem_claims": [claim], "tool_identity": "lean-proof-search@1.0"},
            },
            artifact_verifier=fake_cace_verifier,
            repository="owner/repo",
            commit_sha="a" * 40,
            requester_id="merlin-worker",
            theorem_verifier=lambda **request: theorem_calls.append(request),
        )
        result = handlers["proof_search"]({"stage": "proof_search"}, Context())
        receipt = result["metadata"]["lean_dispatch_receipts"][0]
        self.assertEqual(receipt["compilation_status"], "not_dispatched")
        self.assertEqual(receipt["verification_status"], "blocked_missing_lean_dispatcher")
        self.assertEqual(theorem_calls, [])


if __name__ == "__main__":
    unittest.main()
