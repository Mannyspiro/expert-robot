from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.research_evidence import ResearchEvidenceRecorder
from merlin.text_extractor import store_text_extraction
from merlin.hermes_stage_handlers import (
    build_ideonomy_stage_handler,
    build_merlin_hermes_handlers,
)


class Context:
    task_id = "ideonomy-task-1"
    hypothesis_id = "H-IDEONOMY"
    idempotency_key = "hermes-task-handler:ideonomy-task-1"

    def __init__(self):
        self.events = []

    def emit_progress(self, summary, details=None):
        self.events.append(("progress", summary, details))

    def emit_tool_event(self, kind, name, details):
        self.events.append((kind, name, details))


class HermesIdeonomyStageTests(unittest.TestCase):
    GENERATOR_PROVENANCE = {
        "id": "test.ideonomy",
        "version": "1.0",
        "provider_revision": "test-provider-build-2026-11-16.1",
        "prompt_digest": "1" * 64,
        "config_digest": "2" * 64,
        "adapter_digest": "3" * 64,
    }
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = MerlinRegistry(root / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
        self.ledger = HypothesisLedger(root / "hypotheses.sqlite3")
        self.ledger.create("H-IDEONOMY", "A candidate invariant may hold.")
        self.recorder = ResearchEvidenceRecorder(
            self.registry, self.ledger, self.graph,
        )
        source = (
            "# RP2 notes\n\n"
            "The source describes a finite triangulation of the projective plane.\n"
            "It lists vertices, edges and facets.\n"
        ).encode("utf-8")
        self.registry.put_artifact(
            "merlin", "sources/rp2.md", source, "text/markdown",
        )
        self.source_ref = self.registry.artifact_ref("merlin", "sources/rp2.md")
        extracted = store_text_extraction(
            self.registry, self.graph, self.source_ref,
            project_id="merlin",
            source_repo="Mannyspiro/expert-robot",
            source_commit="a" * 40,
        )
        self.extraction_ref = extracted["stored_representation"]["representation_ref"]

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def generator(request):
        assert request["source_representation_ref"]["sha256"]
        assert request["source_bindings"]
        return {
            "candidates": [{
                "local_id": "candidate-1",
                "kind": "claim",
                "content": "The source describes a finite triangulation.",
                "rationale": "Directly grounded in the source text.",
                "source_binding_indexes": [0],
            }],
            "relations": [],
        }

    def _handler(self):
        return build_ideonomy_stage_handler(
            evidence_recorder=self.recorder,
            project_id="merlin",
            repository="Mannyspiro/expert-robot",
            commit_sha="b" * 40,
            candidate_generator=self.generator,
            candidate_generator_provenance=self.GENERATOR_PROVENANCE,
        )

    def _task(self):
        return {
            "stage": "ideonomy_enumeration",
            "artifact_refs": [self.extraction_ref],
            "experiment_spec": {
                "max_candidates": 20,
                "max_relations": 40,
                "max_input_characters": 10_000,
            },
            "resource_budget": {"memory_bytes": 1_000_000},
        }

    def test_candidate_stage_stores_representation_without_creating_evidence(self):
        before_status = self.ledger.get("H-IDEONOMY").status
        result = self._handler()(self._task(), Context())

        self.assertEqual(result["schema"], "merlin-hermes-ideonomy-result/1")
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["authority"], "candidate_generation_only")
        self.assertEqual(result["epistemic_status"], "unverified")
        self.assertEqual(result["semantic_verification"], "not_assessed")
        self.assertFalse(result["qualification"])
        self.assertFalse(result["promotion_authority"])
        self.assertEqual(result["evidence_refs"], [])
        self.assertTrue(result["artifact"]["registry_verified"])
        self.assertEqual(result["graph_edge"]["relation"], "uses")
        self.assertEqual(result["hypothesis_status_unchanged"], True)
        self.assertEqual(self.ledger.get("H-IDEONOMY").status, before_status)
        self.assertEqual(self.ledger.evidence("H-IDEONOMY"), [])

        edge = self.graph.neighbors(result["graph_edge"]["source_id"], "out")
        self.assertEqual(len(edge), 1)
        self.assertEqual(edge[0]["relation"], "uses")
        self.assertEqual(
            edge[0]["payload"]["relationship_class"], "candidate_discovery",
        )
        self.assertEqual(edge[0]["payload"]["authority"], "candidate_generation_only")

    def test_stage_requires_exact_source_ref_and_valid_budget(self):
        handler = self._handler()
        with self.assertRaisesRegex(ValueError, "exactly one"):
            handler({**self._task(), "artifact_refs": []}, Context())
        with self.assertRaisesRegex(ValueError, "memory budget"):
            handler({
                **self._task(),
                "resource_budget": {"memory_bytes": 3},
            }, Context())
        with self.assertRaisesRegex(ValueError, "mismatched task"):
            handler({**self._task(), "stage": "research"}, Context())

    def test_memory_budget_conservatively_caps_generator_input(self):
        observed = []
        def generator(request):
            observed.append(request["limits"]["max_input_characters"])
            return self.generator(request)

        handler = build_ideonomy_stage_handler(
            evidence_recorder=self.recorder,
            project_id="merlin",
            repository="Mannyspiro/expert-robot",
            commit_sha="b" * 40,
            candidate_generator=generator,
            candidate_generator_provenance=self.GENERATOR_PROVENANCE,
        )
        task = self._task()
        task["resource_budget"] = {"memory_bytes": 8192}
        result = handler(task, Context())
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(observed, [256])

    def test_standard_hermes_composition_registers_injected_ideonomy_stage(self):
        handlers = build_merlin_hermes_handlers(
            evidence_recorder=self.recorder,
            project_id="merlin",
            research_executor=lambda task, context: {},
            proof_search_executor=lambda task, context: {},
            artifact_verifier=None,
            repository="Mannyspiro/expert-robot",
            commit_sha="b" * 40,
            requester_id="merlin-worker",
            include_ngspice=False,
            ideonomy_candidate_generator=self.generator,
            ideonomy_candidate_generator_provenance=self.GENERATOR_PROVENANCE,
        )
        self.assertIn("ideonomy_enumeration", handlers)
        self.assertNotIn("ideonomy_enumeration", build_merlin_hermes_handlers(
            evidence_recorder=self.recorder,
            project_id="merlin",
            research_executor=lambda task, context: {},
            proof_search_executor=lambda task, context: {},
            artifact_verifier=None,
            repository="Mannyspiro/expert-robot",
            commit_sha="b" * 40,
            requester_id="merlin-worker",
            include_ngspice=False,
        ))

    def test_replay_uses_durable_generated_checkpoint_after_projection_failure(self):
        from unittest.mock import patch
        import merlin.hermes_stage_handlers as stage_module
        calls = []
        def counted(request):
            calls.append(request.get("idempotency_key"))
            return self.generator(request)
        handler = build_ideonomy_stage_handler(
            evidence_recorder=self.recorder,
            project_id="merlin",
            repository="Mannyspiro/expert-robot",
            commit_sha="b" * 40,
            candidate_generator=counted,
            candidate_generator_provenance=self.GENERATOR_PROVENANCE,
        )
        original = stage_module.store_ideonomy_candidate_set
        with patch.object(stage_module, "store_ideonomy_candidate_set",
                          side_effect=RuntimeError("simulated crash before projection")):
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                handler(self._task(), Context())
        first_checkpoint = handler.__closure__
        result = handler(self._task(), Context())
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(calls, ["hermes-task-handler:ideonomy-task-1"])
        self.assertEqual(result["authority"], "candidate_generation_only")

    def test_completed_stage_replay_returns_cached_result_without_regeneration(self):
        calls = []
        def counted(request):
            calls.append(True)
            return self.generator(request)
        handler = build_ideonomy_stage_handler(
            evidence_recorder=self.recorder,
            project_id="merlin",
            repository="Mannyspiro/expert-robot",
            commit_sha="b" * 40,
            candidate_generator=counted,
            candidate_generator_provenance=self.GENERATOR_PROVENANCE,
        )
        first = handler(self._task(), Context())
        replay = handler(self._task(), Context())
        self.assertEqual(first, replay)
        self.assertEqual(len(calls), 1)

    def test_model_cannot_assert_its_own_generator_provenance(self):
        def forged(request):
            return {
                "generator": self.GENERATOR_PROVENANCE,
                "candidates": [],
                "relations": [],
            }
        handler = build_ideonomy_stage_handler(
            evidence_recorder=self.recorder,
            project_id="merlin",
            repository="Mannyspiro/expert-robot",
            commit_sha="b" * 40,
            candidate_generator=forged,
            candidate_generator_provenance=self.GENERATOR_PROVENANCE,
        )
        with self.assertRaisesRegex(ValueError, "provenance is runtime-owned"):
            handler(self._task(), Context())

    def test_unknown_hypothesis_is_rejected_before_generation(self):
        called = []
        handler = build_ideonomy_stage_handler(
            evidence_recorder=self.recorder,
            project_id="merlin",
            repository="Mannyspiro/expert-robot",
            commit_sha="b" * 40,
            candidate_generator=lambda request: called.append(request) or {},
            candidate_generator_provenance=self.GENERATOR_PROVENANCE,
        )
        class UnknownHypothesis(Context):
            hypothesis_id = "DOES-NOT-EXIST"
        with self.assertRaises(KeyError):
            handler(self._task(), UnknownHypothesis())
        self.assertEqual(called, [])

    def test_cancellation_is_checked_before_generation(self):
        called = []
        class Cancelled(Context):
            def check_cancelled(self):
                raise RuntimeError("cancelled")

        handler = build_ideonomy_stage_handler(
            evidence_recorder=self.recorder,
            project_id="merlin",
            repository="Mannyspiro/expert-robot",
            commit_sha="b" * 40,
            candidate_generator=lambda request: called.append(request) or {},
            candidate_generator_provenance=self.GENERATOR_PROVENANCE,
        )
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            handler(self._task(), Cancelled())
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
