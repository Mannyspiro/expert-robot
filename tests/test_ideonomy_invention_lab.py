import json
import tempfile
import unittest
from pathlib import Path

from merlin.ideonomy_invention_lab import (build_ideonomy_report, enumerate_simplex_combinations, register_ideonomy_report)
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry


class IdeonomyInventionLabTests(unittest.TestCase):
    def test_report_is_deterministic_and_contains_falsifiable_prototypes(self):
        first = build_ideonomy_report()
        second = build_ideonomy_report()
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], "merlin-ideonomy-invention-report/1")
        self.assertGreaterEqual(len(first["candidates"]), 5)
        for candidate in first["candidates"]:
            self.assertTrue(candidate["prototype"])
            self.assertTrue(candidate["unknowns"])
            self.assertTrue(candidate["evidence"])
            self.assertGreaterEqual(candidate["weighted_score"], 0)
            self.assertLessEqual(candidate["weighted_score"], 10)

    def test_simplex_enumerator_only_returns_explicit_cross_domain_compatible_sets(self):
        combinations = enumerate_simplex_combinations(3)
        self.assertGreater(len(combinations), 0)
        self.assertTrue(all(2 <= len(item["primitive_ids"]) <= 3 for item in combinations))
        self.assertTrue(all(len(item["domains"]) >= 2 for item in combinations))
        self.assertTrue(all(item["epistemic_status"] == "hypothesis_combination" for item in combinations))
        with self.assertRaises(ValueError):
            enumerate_simplex_combinations(4)

    def test_titan_is_top_level_research_context_and_candidate(self):
        report = build_ideonomy_report()
        self.assertIn("Cryptographic", report["titan_context"]["role"])
        self.assertIn("AES-256-GCM-SIV", report["titan_context"]["baseline"])
        self.assertIn("not replacement ciphers", report["titan_context"]["boundary"])
        titan = next(c for c in report["candidates"] if c["candidate_id"] == "titan-adaptive-compute-loom")
        self.assertIn("CPU-based", titan["real_world_translation"])
        self.assertNotEqual(titan["candidate_id"], "titan-cryptographic-envelope")
        self.assertIn("12 V", " ".join(titan["electrical_scope"]))

    def test_report_registers_canonical_artifact_and_graph_nodes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = MerlinRegistry(root / "registry")
            registry.register_project("merlin", "Merlin")
            graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
            result = register_ideonomy_report(
                registry=registry, graph=graph, project_id="merlin"
            )
            self.assertTrue(result["artifact_verified"])
            self.assertTrue(registry.verify_artifact(result["artifact_sha256"]))
            titan = graph.get_node(result["titan_node_id"])
            self.assertEqual(titan.node_type, "module")
            self.assertEqual(len(result["candidate_node_ids"]), 5)
            self.assertEqual(len(graph.neighbors(result["titan_node_id"])), 2)


if __name__ == "__main__":
    unittest.main()
