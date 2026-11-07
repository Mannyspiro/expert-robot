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
