"""Independent numerical invariants and evaluation-boundary regressions."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from merlin import parallax_calibration as core
from experimental_self_healing import EvidenceLedger
from merlin_loop_coordinator import Loop, LoopCoordinator
from merlin_loop_persistence import checkpoint
from merlin.research_window import ResearchWindow

spec = importlib.util.spec_from_file_location("parallax_runner", ROOT / "scripts/merlin/parallax_rsi.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ArithmeticTests(unittest.TestCase):
    def setUp(self):
        self.weights = np.array([0.03, 0.11, 0.86])
        self.a = np.array([1.25, -2.5, 0.75])
        self.values = np.array([[0.1, 0.2], [0.3, -0.4], [-0.7, 0.8]])

    def test_fp64_agrees_with_decimal_unequal_weights(self):
        expected = core.decimal_attention(self.weights, self.a, self.values)
        actual = core.attention(self.weights, self.a, self.values, core.CANDIDATES[-1])
        np.testing.assert_allclose(actual, expected, rtol=1e-13, atol=1e-13)

    def test_score_translation_and_weight_scale_invariance(self):
        expected = core.reference_attention(self.weights, self.a, self.values)
        actual = core.attention(self.weights * 7, self.a + 1024, self.values, core.CANDIDATES[-1])
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)

    def test_value_translation_equivariance(self):
        shift = np.array([16.0, -8.0])
        a = core.reference_attention(self.weights, self.a, self.values)
        b = core.reference_attention(self.weights, self.a, self.values + shift)
        np.testing.assert_allclose(a + shift, b, atol=1e-13)

    def test_positive_weights_do_not_imply_convex_output(self):
        actual = core.reference_attention([0.5, 0.5], [10, -10], [[1], [0]])
        self.assertEqual(float(actual[0]), -4.5)

    def test_block_partial_tail_and_zero_mass_block(self):
        p = np.concatenate([np.zeros(16), self.weights])
        a = np.resize(self.a, 19)
        v = np.resize(self.values, (19, 2))
        actual = core.attention(p, a, v, core.CANDIDATES[2])
        np.testing.assert_allclose(actual, core.decimal_attention(p, a, v), atol=2e-7)

    def test_unequal_positive_multiblock_merge_cross_term(self):
        n = np.arange(35)
        p, a, v = n + 1, (n % 7 - 3) / 4, np.column_stack((n % 5 - 2, n // 5 - 3))
        expected = core.decimal_attention(p, a, v)
        np.testing.assert_allclose(expected, [0.11728395061728394, 0.9728395061728395], atol=1e-15)
        for candidate in (core.CANDIDATES[2], core.CANDIDATES[3]):
            np.testing.assert_allclose(core.attention(p, a, v, candidate), expected, atol=1e-7)

    def test_nonfinite_negative_or_zero_mass_rejected(self):
        for p in ([0, 0, 0], [1, -1, 1], [1, float("nan"), 1]):
            with self.subTest(p=p), self.assertRaises(ValueError):
                core.attention(p, self.a, self.values, core.CANDIDATES[1])

    def test_unknown_candidate_rejected(self):
        with self.assertRaises(ValueError):
            core.attention(self.weights, self.a, self.values, core.Candidate("unreviewed", "float64", "raw"))

    def test_nll_stable_and_masked_by_scored_token(self):
        losses = core.token_losses([[10000, 9999], [0, 0], [0, 0]], [0, -1, 1], [True, False, True])
        np.testing.assert_allclose(losses, [np.log1p(np.exp(-1)), np.log(2)], atol=1e-12)
        self.assertEqual(core.summarize_losses(losses)["tokens"], 2)
        self.assertAlmostEqual(core.summarize_losses(losses)["perplexity"], np.exp(losses.sum() / 2))

    def test_nll_invalid_masks_labels_and_logits(self):
        cases = [([[0, 1]], [2], None), ([[0, np.inf]], [0], None),
                 ([[0, 1]], [0.5], None), ([[0, 1]], [0], [False]),
                 ([[0, 1]], [0], [1])]
        for logits, labels, mask in cases:
            with self.subTest(labels=labels, mask=mask), self.assertRaises(ValueError):
                core.token_losses(logits, labels, mask)

    def test_deadline_is_enforced_before_core_execution(self):
        fixture = {"p": [self.weights], "a": [self.a], "values": [self.values]}
        with self.assertRaises(TimeoutError):
            core.evaluate(fixture, core.CANDIDATES[0], deadline=time.monotonic() - 1)

    def test_split_ids_are_disjoint_and_reproducible(self):
        with patch.dict(core.SPLITS, {"validation": (27001, 3), "test": (37001, 3)}):
            a = core.make_fixture("validation")
            self.assertEqual(a["sha256"], core.make_fixture("validation")["sha256"])
            self.assertNotEqual(a["sha256"], core.make_fixture("test")["sha256"])
            result = core.evaluate(a, core.CANDIDATES[1], deadline=time.monotonic() + 10)
            self.assertLessEqual(result["max_abs_token_nll_delta"], result["nll_delta_bound_twice_max_logit_error"] + 1e-12)
            self.assertGreaterEqual(result["mean_teacher_kl"], -1e-14)
            self.assertIn("max_abs_input_quantization_error", result)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state, self.output = Path(self.tmp.name) / "state", Path(self.tmp.name) / "output"

    def test_finished_episode_is_returned_without_test_replay(self):
        # Test-only short splits; no production protocol result is taken from this run.
        with patch.dict(core.SPLITS, {"validation": (27001, 6), "test": (37001, 6)}):
            first = runner.execute(self.state, self.output, "unit-episode", "1" * 40)
            with patch.object(runner, "evaluate", side_effect=AssertionError("must not reevaluate")):
                second = runner.execute(self.state, self.output, "unit-episode", "1" * 40)
            self.assertEqual(first, second)
            self.assertEqual(first["test"]["episode_count"], 1)
            self.assertFalse(first["trained_language_model_evaluated"])

    def test_interrupted_execution_is_blocked_without_rerun(self):
        with patch.object(runner, "make_fixture", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                runner.execute(self.state, self.output, "interrupted", "1" * 40)
        with patch.object(runner, "make_fixture", side_effect=AssertionError("must not replay")):
            with self.assertRaisesRegex(RuntimeError, "requires review"):
                runner.execute(self.state, self.output, "interrupted", "1" * 40)

    def test_invalid_run_identity_has_no_side_effect(self):
        with self.assertRaises(ValueError):
            runner.execute(self.state, self.output, "../escape", "1" * 40)
        self.assertFalse(self.state.exists())

    def test_frozen_protocol_rejects_changed_source(self):
        with patch.dict(core.SPLITS, {"validation": (27001, 3), "test": (37001, 3)}):
            runner.execute(self.state, self.output, "unit-episode", "1" * 40)
            with self.assertRaisesRegex(ValueError, "source/protocol changed"):
                runner.execute(self.state, self.output, "unit-episode", "2" * 40)

    def test_later_registry_version_cannot_replace_checkpoint_evidence(self):
        with patch.dict(core.SPLITS, {"validation": (27001, 3), "test": (37001, 3)}):
            runner.execute(self.state, self.output, "unit-episode", "1" * 40)
            registry = ResearchWindow(self.state, project_id="parallax-rsi").registry
            registry.put_artifact("parallax-rsi", "research/parallax/unit-episode/evaluate-raw_fp32.json", b'{"changed":true}', "application/json")
            with self.assertRaisesRegex(RuntimeError, "superseded"):
                runner.execute(self.state, self.output, "unit-episode", "1" * 40)

    def test_clock_replacement_cannot_renew_budget(self):
        with patch.dict(core.SPLITS, {"validation": (27001, 3), "test": (37001, 3)}):
            runner.execute(self.state, self.output, "unit-episode", "1" * 40)
            registry = ResearchWindow(self.state, project_id="parallax-rsi").registry
            registry.put_artifact("parallax-rsi", "research/parallax/unit-episode/clock.json", b'{"started_unix_seconds":999999999999}', "application/json")
            with self.assertRaisesRegex(RuntimeError, "superseded"):
                runner.execute(self.state, self.output, "unit-episode", "1" * 40)

    def test_partial_initialization_cannot_be_overwritten(self):
        registry = ResearchWindow(self.state, project_id="parallax-rsi").registry
        registry.put_artifact("parallax-rsi", "research/parallax/partial/protocol.json", b'{}', "application/json")
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            runner.execute(self.state, self.output, "partial", "1" * 40)

    def test_exhausted_budget_stays_blocked_after_clock_rollback(self):
        clock = SimpleNamespace(time=Mock(side_effect=[1000.0, 1301.0]), monotonic=time.monotonic)
        with patch.object(runner, "time", clock):
            with self.assertRaisesRegex(TimeoutError, "exhausted"):
                runner.execute(self.state, self.output, "expired", "1" * 40)
        with patch.object(runner, "time", SimpleNamespace(time=lambda: 1001.0, monotonic=time.monotonic)):
            with self.assertRaisesRegex(RuntimeError, "requires review"):
                runner.execute(self.state, self.output, "expired", "1" * 40)

    def test_export_recovery_does_not_repeat_test_episode(self):
        with patch.dict(core.SPLITS, {"validation": (27001, 3), "test": (37001, 3)}):
            with patch.object(ResearchWindow, "register_artifact", side_effect=RuntimeError("export interrupted")):
                with self.assertRaisesRegex(RuntimeError, "export interrupted"):
                    runner.execute(self.state, self.output, "export-recovery", "1" * 40)
            with patch.object(runner, "evaluate", side_effect=AssertionError("must not reevaluate")):
                receipt = runner.execute(self.state, self.output, "export-recovery", "1" * 40)
            self.assertEqual(receipt["test"]["episode_count"], 1)
            self.assertTrue((self.output / "finalization.json").exists())


if __name__ == "__main__":
    unittest.main()
