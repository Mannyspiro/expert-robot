from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from merlin.ideonomy import (
    IdeonomyUnavailableError,
    enumerate_ideonomy_candidates,
    ideonomy_capability,
    store_ideonomy_candidate_set,
)
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.knowledge_reconstruction import inspect_knowledge_representation
from merlin.project_registry import MerlinRegistry
from merlin.registry_queries import MerlinReadAPI
from merlin.text_extractor import store_text_extraction


class IdeonomyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = MerlinRegistry(self.root / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.graph = MerlinKnowledgeGraph(self.root / "graph.sqlite3")
        source = (
            "# Finite triangulation of RP2\n\n"
            "The source describes a finite triangulation.\n"
            "It identifies vertices, edges and facets.\n"
        ).encode("utf-8")
        self.registry.put_artifact("merlin", "sources/rp2.md", source, "text/markdown")
        self.source_ref = self.registry.artifact_ref("merlin", "sources/rp2.md")
        stored = store_text_extraction(
            self.registry, self.graph, self.source_ref,
            project_id="merlin",
            source_repo="Mannyspiro/expert-robot",
            source_commit="a" * 40,
        )
        self.extraction_ref = stored["stored_representation"]["representation_ref"]
        self.inspection = inspect_knowledge_representation(self.registry, self.extraction_ref)

    def tearDown(self):
        self.temp.cleanup()

    def _generator(self, request):
        self.request = request
        return {
            "generator": {"id": "test.ideonomy", "version": "1.0.0"},
            "candidates": [
                {
                    "local_id": "concept-1",
                    "kind": "concept",
                    "content": "finite triangulation",
                    "rationale": "A recurring mathematical object in the source.",
                    "source_binding_indexes": [0],
                    "confidence_estimate": 0.8,
                },
                {
                    "local_id": "claim-1",
                    "kind": "claim",
                    "content": "The source describes a finite triangulation.",
                    "rationale": "Directly grounded in the paragraph.",
                    "source_binding_indexes": [1],
                    "confidence_estimate": None,
                },
            ],
            "relations": [
                {
                    "subject_local_id": "claim-1",
                    "predicate": "depends_on",
                    "object_local_id": "concept-1",
                    "rationale": "The claim uses the named mathematical object.",
                }
            ],
        }

    def test_enumeration_is_source_bound_and_never_claims_verification(self):
        result = enumerate_ideonomy_candidates(
            self.registry, self.extraction_ref, self._generator,
        )
        self.assertEqual(result["schema"], "merlin-ideonomy-candidate-set/1")
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["relation_count"], 1)
        self.assertEqual(result["authority"], "candidate_generation_only")
        self.assertEqual(result["epistemic_status"], "unverified")
        self.assertEqual(result["semantic_verification"], "not_assessed")
        self.assertFalse(result["qualification"])
        self.assertTrue(all(c["epistemic_status"] == "unverified" for c in result["candidates"]))
        self.assertTrue(all(c["authority"] == "candidate_generation_only" for c in result["candidates"]))
        self.assertEqual(
            self.request["source_representation_ref"], self.extraction_ref,
        )
        self.assertTrue(self.request["source_bindings"])
        self.assertTrue(all(b["binding"]["locator_type"] == "byte_range" for b in self.request["source_bindings"]))
        self.assertTrue(all(b["segment_id"] for b in self.request["source_bindings"]))
        self.assertIn("counter-hypotheses", self.request["instructions"])

    def test_enumeration_and_candidate_ids_are_deterministic(self):
        first = enumerate_ideonomy_candidates(self.registry, self.extraction_ref, self._generator)
        second = enumerate_ideonomy_candidates(self.registry, self.extraction_ref, self._generator)
        self.assertEqual(first["candidate_set_id"], second["candidate_set_id"])
        self.assertEqual(first["candidates"], second["candidates"])
        self.assertEqual(first["relations"], second["relations"])

    def test_missing_generator_is_unavailable_not_silently_simulated(self):
        self.assertEqual(ideonomy_capability(None)["state"], "unavailable")
        self.assertFalse(ideonomy_capability(self._generator)["qualified"])
        with self.assertRaises(IdeonomyUnavailableError):
            enumerate_ideonomy_candidates(self.registry, self.extraction_ref, None)

    def test_rejects_unbound_source_indexes_and_authority_escalation(self):
        def unbound(request):
            return {
                "generator": {"id": "test", "version": "1"},
                "candidates": [{
                    "local_id": "bad", "kind": "claim", "content": "unsupported",
                    "source_binding_indexes": [999999],
                }],
                "relations": [],
            }
        with self.assertRaisesRegex(ValueError, "outside the inspected manifest"):
            enumerate_ideonomy_candidates(self.registry, self.extraction_ref, unbound)

        def escalated(request):
            return {
                "generator": {"id": "test", "version": "1"},
                "candidates": [{
                    "local_id": "bad", "kind": "claim", "content": "verified",
                    "source_binding_indexes": [0], "epistemic_status": "verified",
                }],
                "relations": [],
            }
        with self.assertRaisesRegex(ValueError, "unsupported authority or fields"):
            enumerate_ideonomy_candidates(self.registry, self.extraction_ref, escalated)

    def test_rejects_unsupported_graph_relations_and_input_budget_excess(self):
        def unsupported_relation(request):
            return {
                "generator": {"id": "test", "version": "1"},
                "candidates": [
                    {"local_id": "a", "kind": "claim", "content": "A", "source_binding_indexes": [0]},
                    {"local_id": "b", "kind": "claim", "content": "B", "source_binding_indexes": [1]},
                ],
                "relations": [{
                    "subject_local_id": "a", "predicate": "is_true",
                    "object_local_id": "b", "rationale": "not a supported graph predicate",
                }],
            }
        with self.assertRaisesRegex(ValueError, "not supported by the canonical graph"):
            enumerate_ideonomy_candidates(self.registry, self.extraction_ref, unsupported_relation)
        with self.assertRaisesRegex(ValueError, "character budget"):
            enumerate_ideonomy_candidates(
                self.registry, self.extraction_ref, self._generator,
                max_input_characters=10,
            )

    def test_store_projects_candidates_and_relations_idempotently(self):
        candidate_set = enumerate_ideonomy_candidates(
            self.registry, self.extraction_ref, self._generator,
        )
        before = self.registry.inventory("merlin")
        first = store_ideonomy_candidate_set(
            self.registry, self.graph, candidate_set,
            project_id="merlin",
            source_repo="Mannyspiro/expert-robot",
            source_commit="b" * 40,
        )
        snapshot_after_first = self.graph.export_snapshot()
        second = store_ideonomy_candidate_set(
            self.registry, self.graph, candidate_set,
            project_id="merlin",
            source_repo="Mannyspiro/expert-robot",
            source_commit="b" * 40,
        )
        snapshot_after_second = self.graph.export_snapshot()
        self.assertEqual(
            first["stored_representation"]["representation_ref"],
            second["stored_representation"]["representation_ref"],
        )
        self.assertEqual(snapshot_after_first, snapshot_after_second)
        self.assertEqual(len(first["candidate_graph_node_ids"]), 2)
        self.assertFalse(first["qualification"])
        self.assertEqual(first["authority"], "candidate_generation_only")
        self.assertGreater(
            len(self.registry.inventory("merlin")["artifacts"]),
            len(before["artifacts"]),
        )

        api = MerlinReadAPI(self.registry, graph=self.graph)
        query = api.knowledge_representation(
            first["stored_representation"]["representation_ref"]
        )
        self.assertEqual(query["manifest"]["representation_type"], "ideonomy_candidates")
        self.assertEqual(query["manifest"]["payload"]["candidate_set_id"], candidate_set["candidate_set_id"])
        self.assertFalse(query["source_bytes_included"])
        candidate_nodes = [
            node for node in snapshot_after_second["nodes"]
            if node["node_id"].startswith("ideonomy-candidate:")
        ]
        self.assertEqual(len(candidate_nodes), 2)
        self.assertTrue(all(node["evidence_class"] == "unverified_candidate" for node in candidate_nodes))

    def test_store_rejects_tampered_candidate_set(self):
        candidate_set = enumerate_ideonomy_candidates(
            self.registry, self.extraction_ref, self._generator,
        )
        tampered = dict(candidate_set)
        tampered["candidates"] = [dict(candidate_set["candidates"][0])]
        tampered["candidates"][0]["content"] = "Changed after enumeration."
        with self.assertRaisesRegex(ValueError, "candidate identity is invalid"):
            store_ideonomy_candidate_set(
                self.registry, self.graph, tampered,
                project_id="merlin",
                source_repo="Mannyspiro/expert-robot",
                source_commit="b" * 40,
            )


if __name__ == "__main__":
    unittest.main()
