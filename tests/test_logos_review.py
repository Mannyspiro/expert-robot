from __future__ import annotations

import hashlib
import unittest

from merlin.knowledge_compression import canonical_json
from merlin.logos_review import (
    validate_logos_review, validate_reviewer_provenance,
)


class LogosReviewContractTests(unittest.TestCase):
    def setUp(self):
        self.generator = {
            "id": "test.ideonomy", "version": "1.0",
            "provider_revision": "provider-build-2026-11-16.1",
            "prompt_digest": "1" * 64, "config_digest": "2" * 64,
            "adapter_digest": "3" * 64,
        }
        self.source_ref = {
            "schema": "merlin-artifact-ref/1", "project_id": "merlin",
            "logical_path": "sources/source.md", "version": 1, "sha256": "a" * 64,
        }
        self.binding = {
            "artifact_ref": self.source_ref, "locator_type": "byte_range",
            "locator": {"start": 0, "end": 24},
        }
        self.source_representation_id = "b" * 64
        candidate_body = {
            "source_representation_id": self.source_representation_id,
            "generator": self.generator, "kind": "claim",
            "content": "A candidate statement.", "rationale": "Generated from source.",
            "source_bindings": [self.binding], "confidence_estimate": None,
        }
        candidate_id = hashlib.sha256(canonical_json(candidate_body)).hexdigest()
        candidate = {
            "candidate_id": candidate_id, "kind": "claim",
            "content": candidate_body["content"], "rationale": candidate_body["rationale"],
            "source_bindings": [self.binding], "confidence_estimate": None,
            "confidence_semantics": "model_estimate_not_truth_probability",
            "epistemic_status": "unverified", "authority": "candidate_generation_only",
        }
        body = {
            "schema": "merlin-ideonomy-candidate-set/1",
            "source_representation_ref": {
                "schema": "merlin-artifact-ref/1", "project_id": "merlin",
                "logical_path": "knowledge/representations/" + "c" * 64 + ".json",
                "version": 1, "sha256": "d" * 64,
            },
            "source_representation_id": self.source_representation_id,
            "source_artifact_refs": [self.source_ref], "generator": self.generator,
            "candidate_count": 1, "relation_count": 0, "candidates": [candidate],
            "relations": [], "authority": "candidate_generation_only",
            "epistemic_status": "unverified", "semantic_verification": "not_assessed",
            "qualification": False,
        }
        self.candidate_set = {
            **body, "candidate_set_id": hashlib.sha256(canonical_json(body)).hexdigest(),
        }
        self.candidate_id = candidate_id
        self.valid_output = {
            "candidate_reviews": [{
                "candidate_id": candidate_id, "disposition": "retain_for_testing",
                "rationale": "The source locator is relevant, but does not establish the claim.",
                "findings": [{
                    "kind": "interpretation", "text": "This is an interpretation, not a quotation.",
                    "source_binding_indexes": [0],
                }],
            }],
            "counter_hypotheses": [{
                "candidate_id": candidate_id, "statement": "An alternative explanation may fit.",
                "source_binding_indexes": [0],
            }],
            "falsifiability_questions": [{
                "candidate_id": candidate_id, "statement": "What observation would falsify this claim?",
                "source_binding_indexes": [],
            }],
            "limitations": ["Only one source was inspected."],
        }

    def test_valid_review_covers_candidate_and_remains_non_authoritative(self):
        result = validate_logos_review(self.candidate_set, self.valid_output)
        self.assertEqual(result["candidate_set_id"], self.candidate_set["candidate_set_id"])
        self.assertEqual(result["candidate_reviews"][0]["disposition"], "retain_for_testing")
        self.assertEqual(result["authority"], "skeptical_review_only")
        self.assertEqual(result["epistemic_status"], "unverified")
        self.assertFalse(result["qualification"])
        self.assertFalse(result["promotion_authority"])
        self.assertEqual(result["candidate_reviews"][0]["findings"][0]["source_bindings"], [self.binding])

    def test_omitted_candidate_is_rejected(self):
        output = dict(self.valid_output)
        output["candidate_reviews"] = []
        with self.assertRaisesRegex(ValueError, "every candidate"):
            validate_logos_review(self.candidate_set, output)

    def test_direct_quotation_requires_exact_source_binding(self):
        output = dict(self.valid_output)
        output["candidate_reviews"] = [dict(self.valid_output["candidate_reviews"][0])]
        output["candidate_reviews"][0]["findings"] = [{
            "kind": "quotation", "text": "An alleged quotation.",
            "source_binding_indexes": [],
        }]
        with self.assertRaisesRegex(ValueError, "direct quotations"):
            validate_logos_review(self.candidate_set, output)

    def test_model_cannot_promote_candidate(self):
        output = dict(self.valid_output)
        output["candidate_reviews"] = [dict(self.valid_output["candidate_reviews"][0])]
        output["candidate_reviews"][0]["disposition"] = "verified"
        with self.assertRaisesRegex(ValueError, "disposition"):
            validate_logos_review(self.candidate_set, output)

    def test_candidate_identity_tampering_is_detected_even_if_set_hash_is_recomputed(self):
        import copy
        candidate_set = copy.deepcopy(self.candidate_set)
        candidate_set["candidates"][0]["content"] = "Tampered candidate."
        body = {k: v for k, v in candidate_set.items() if k != "candidate_set_id"}
        candidate_set["candidate_set_id"] = hashlib.sha256(canonical_json(body)).hexdigest()
        with self.assertRaisesRegex(ValueError, "candidate identity"):
            validate_logos_review(candidate_set, self.valid_output)

    def test_reviewer_provenance_rejects_mutable_provider_alias(self):
        provenance = {
            "id": "logos", "version": "1",
            "provider_revision": "latest",
            "prompt_digest": "1" * 64, "config_digest": "2" * 64,
            "adapter_digest": "3" * 64,
        }
        with self.assertRaisesRegex(ValueError, "immutable"):
            validate_reviewer_provenance(provenance)


if __name__ == "__main__":
    unittest.main()
