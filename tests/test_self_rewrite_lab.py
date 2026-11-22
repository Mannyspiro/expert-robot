"""Tests for actual numerical-weight edits and fail-closed candidate evaluation."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from merlin.self_rewrite_lab import (
    PROPOSAL_SCHEMA, apply_projection, digest, gate, matrix, predict,
    propose_self_repair, score, synthetic_repair, validate_proposal,
)


class SelfRewriteLabTests(unittest.TestCase):
    def setUp(self):
        self.base = [[1.0, 0.0], [0.0, 2.0]]
        self.practice = [([0, 1], [0, 1]), ([1, 0], [1, 0])]
        self.holdout = [([.5, .5], [.5, .5]),
                        ([1, 1], [1, 1]), ([.25, .75], [.25, .75])]

    def test_real_numeric_weights_changed_and_heldout_improves(self):
        proposal = propose_self_repair(self.base, self.practice)
        self.assertEqual(proposal["schema"], PROPOSAL_SCHEMA)
        self.assertEqual(proposal["weight_sha256"], digest(self.base))
        candidate = validate_proposal(proposal, self.base)
        self.assertEqual(candidate, [[1.0, 0.0], [0.0, 1.0]])
        self.assertNotEqual(candidate, self.base)
        self.assertEqual(self.base, [[1.0, 0.0], [0.0, 2.0]])
        self.assertEqual(predict(candidate, [.5, .5]), [.5, .5])
        outcome = gate(self.base, candidate, self.practice, self.holdout)
        self.assertTrue(outcome["accepted_as_research_candidate"])
        self.assertEqual(outcome["baseline_holdout_correct"], 0)
        self.assertEqual(outcome["candidate_holdout_correct"], 3)
        self.assertEqual(outcome["improved"], 3)
        self.assertEqual(outcome["regressed"], 0)
        self.assertFalse(outcome["production_qualified"])

    def test_persist_base_candidate_and_identity_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            receipt = synthetic_repair(out)
            base = json.loads((out / "synthetic-base-weights.json").read_text())
            candidate = json.loads((out / "synthetic-candidate-weights.json").read_text())
            self.assertEqual(receipt["original_sha256"], digest(base))
            self.assertEqual(receipt["candidate_sha256"], digest(candidate))
            self.assertNotEqual(base, candidate)
            self.assertTrue(receipt["actual_numeric_weights_rewritten"])
            self.assertFalse(receipt["merlin_gguf_weights_changed"])
            self.assertFalse(receipt["model_editor_was_language_model"])
            self.assertFalse(receipt["model_weights_fine_tuned"])
            self.assertTrue(receipt["operator_promotion_required"])
            with self.assertRaises(FileExistsError):
                synthetic_repair(out)

    def test_typed_proposals_reject_stale_weights_and_code_fields(self):
        correct = propose_self_repair(self.base, self.practice)
        for fake in (
            {**correct, "weight_sha256": "a" * 64},
            {**correct, "target": "production.gguf"},
            {**correct, "code": "__import__('os').system('true')"},
            {**correct, "direction": [2, 0]},
            {**correct, "direction": [float("nan"), 0]},
            {**correct, "fraction": 1.0},
            {**correct, "fraction": 0.0},
        ):
            with self.subTest(fake=str(fake)[:60]):
                with self.assertRaises(ValueError):
                    validate_proposal(fake, self.base)

    def test_regressions_block_candidate_even_with_improvements(self):
        # A damaged first axis destroys existing correct answers.
        candidate = [[.5, 0.0], [0.0, 1.0]]
        mixed = [([1, 0], [1, 0]), ([0, 1], [0, 1])]
        outcome = gate(self.base, candidate, self.practice, mixed)
        self.assertGreater(outcome["regressed"], 0)
        self.assertFalse(outcome["accepted_as_research_candidate"])

    def test_failed_or_unbounded_inputs_never_change_original(self):
        base = [[1., 0.], [0., 2.]]
        original = digest(base)
        for direction, alpha in (
            ([0., 0.], .5), ([1., 1.], .5),
            ([0., 1.], float("nan")), ([0., 1.], -.1),
        ):
            with self.subTest(direction=direction, alpha=alpha):
                with self.assertRaises(ValueError):
                    apply_projection(base, direction, alpha)
        with self.assertRaises(ValueError):
            matrix([[1.], [1., 2.]])
        with self.assertRaises(ValueError):
            score(base, [])
        self.assertEqual(digest(base), original)

    def test_a_no_op_cannot_be_claimed_as_improvement(self):
        identical = gate(self.base, self.base, self.practice, self.holdout)
        self.assertFalse(identical["accepted_as_research_candidate"])
        self.assertEqual(identical["improved"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
