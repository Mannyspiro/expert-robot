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
        self.assertIsNone(activation_reason("format-only transformation of research notes"))
        self.assertEqual(
            activation_reason("translate this", mode="always"),
            "explicit_runtime_mode",
        )
        enriched, status = prepare_research_task("Develop a research plan")
        self.assertTrue(status["active"])
        self.assertIn(digest, enriched)
        self.assertIn("authority", enriched)
        self.assertIn("math_method_registry", enriched)
        self.assertEqual(len(status["math_method_registry_sha256"]), 64)
        self.assertEqual(
            prepare_research_task("hello", mode="off"),
            ("hello", {"active": False, "reason": "not_research_scope"}),
        )

    def test_math_method_registry_distinguishes_capability_from_research(self):
        registry = self.load_json("config/research/math_method_registry_v1.json")
        self.assertEqual(registry["id"], "MERLIN-MATH-METHOD-REGISTRY-001")
        methods = {item["id"]: item for item in registry["methods"]}
        self.assertEqual(
            methods["formal_logic_and_type_theory"]["status"],
            "implemented_verified_boundary",
        )
        self.assertEqual(
            methods["probability_bayesian_inference"]["status"],
            "not_implemented_as_runtime_solver",
        )
        self.assertEqual(
            methods["cross_domain_lacuna_search"]["status"],
            "qualified_prompt_skill",
        )
        self.assertIn("not truth", methods["research_episode_lineage"]["limits"][0])

    def test_runtime_rejects_duplicate_method_registry_ids(self):
        import sys
        import tempfile

        sys.path.insert(0, str(ROOT / "python"))
        from research_protocol import prepare_research_task

        registry = self.load_json("config/research/math_method_registry_v1.json")
        registry["methods"].append(dict(registry["methods"][0]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate-registry.json"
            path.write_text(json.dumps(registry), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unique"):
                prepare_research_task(
                    "research a mathematical claim",
                    method_registry_path=path,
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

    def test_conversation_context_import_is_idempotent_and_append_only(self):
        import sqlite3
        import sys
        import tempfile

        sys.path.insert(0, str(ROOT / "python"))
        from conversation_context import (
            ContextRecordError,
            ConversationContextStore,
        )

        record = {
            "source_system": "chatgpt_export",
            "conversation_id": "conversation-001",
            "message_id": "message-001",
            "role": "user",
            "created_at": "2026-11-07T17:00:00Z",
            "privacy": "project",
            "content": "Continue the Merlin research protocol.",
            "project_tags": ["merlin", "research"],
            "attachments": [
                {"attachment_id": "attachment-001", "sha256": "a" * 64}
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            store = ConversationContextStore(Path(directory) / "context.sqlite3")
            try:
                self.assertEqual(store.ingest([record]), {"inserted": 1, "duplicates": 0})
                self.assertEqual(store.ingest([record]), {"inserted": 0, "duplicates": 1})
                self.assertEqual(store.coverage()["messages"], 1)
                self.assertEqual(store.coverage()["attachments"], 1)
                self.assertEqual(len(store.search("merlin")), 1)
                with self.assertRaises(sqlite3.IntegrityError):
                    store.db.execute("DELETE FROM context_messages")
                store.db.rollback()
                changed = dict(record, content="changed content")
                with self.assertRaisesRegex(ContextRecordError, "collision"):
                    store.ingest([changed])
                with self.assertRaisesRegex(ContextRecordError, "allow_personal"):
                    store.ingest([dict(record, message_id="personal-001", privacy="personal")])
            finally:
                store.close()

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
