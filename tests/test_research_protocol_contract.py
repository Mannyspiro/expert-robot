"""Contract tests for Merlin's versioned research protocol data."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ResearchProtocolContractTests(unittest.TestCase):
    def load_json(self, relative_path):
        with (ROOT / relative_path).open(encoding="utf-8") as handle:
            return json.load(handle)

    def test_protocol_has_complete_ordered_pipeline(self):
        protocol = self.load_json("config/research/reasoning_protocol_v1.json")
        self.assertEqual(protocol["id"], "MERLIN-RESEARCH-001")
        steps = [item["step"] for item in protocol["pipeline"]]
        self.assertEqual(
            steps,
            [
                "context_intake",
                "problem_formalization",
                "ideonomy_enumeration",
                "inductive_inference",
                "deductive_derivation",
                "skeptical_review",
                "implementation_plan",
                "execution_and_measurement",
                "plan_update",
            ],
        )
        self.assertTrue(protocol["ideonomy"]["separate_hypothesis_from_fact"])
        self.assertTrue(protocol["scientific_skepticism"]["require_falsifiable_predictions"])
        self.assertTrue(protocol["authority"]["generated_claims_are_untrusted_until_verified"])
        self.assertEqual(protocol["ideonomy"]["dedicated_imagination_lens"], "lacuna")
        self.assertIn("falsifiable_test_path", protocol["ideonomy"]["combination_filters"])
        self.assertIn("Lacuna", (ROOT / "cpp/include/expert_robot/imagination/idea.hpp").read_text(encoding="utf-8"))

    def test_runtime_adapter_activates_and_binds_protocol_digest(self):
        import sys

        sys.path.insert(0, str(ROOT / "python"))
        from research_protocol import (
            activation_reason,
            load_protocol,
            prepare_research_task,
        )

        protocol, digest = load_protocol()
        self.assertEqual(protocol["id"], "MERLIN-RESEARCH-001")
        self.assertEqual(len(digest), 64)
        self.assertEqual(activation_reason("Design a new research engine"), "relevant_task_trigger")
        self.assertIsNone(activation_reason("simple factual lookup: capital of France"))
        self.assertEqual(
            activation_reason("translate this", mode="always"),
            "explicit_runtime_mode",
        )
        enriched, status = prepare_research_task("Develop a research plan")
        self.assertTrue(status["active"])
        self.assertIn(digest, enriched)
        self.assertIn("authority", enriched)
        self.assertEqual(
            prepare_research_task("hello", mode="off"),
            ("hello", {"active": False, "reason": "not_research_scope"}),
        )

    def test_reasoning_taxonomy_has_unique_ids_and_review_prompts(self):
        taxonomy = self.load_json("config/research/reasoning_checks_v1.json")
        groups = [
            "logical_fallacies",
            "cognitive_biases",
            "research_and_statistical_errors",
            "engineering_and_ai_failure_modes",
        ]
        identifiers = []
        for group in groups:
            self.assertTrue(taxonomy[group])
            for entry in taxonomy[group]:
                self.assertEqual(len(entry), 2)
                self.assertTrue(entry[0])
                self.assertTrue(entry[1])
                identifiers.append(entry[0])
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertGreaterEqual(len(taxonomy["review_questions"]), 8)

    def test_context_contract_requires_source_traceability(self):
        text = (ROOT / "docs/conversation-context-ingestion-contract.md").read_text(
            encoding="utf-8"
        )
        for required in (
            "stable source conversation and message identifiers",
            "content hash",
            "Contradictory statements",
            "idempotent",
            "coverage",
        ):
            self.assertIn(required.lower(), text.lower())


if __name__ == "__main__":
    unittest.main()
