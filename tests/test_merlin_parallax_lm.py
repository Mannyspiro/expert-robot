"""Scoring and durable replay regressions; no model or corpus is accessed."""
import builtins
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from merlin_loop_coordinator import Loop, LoopCoordinator

spec = importlib.util.spec_from_file_location("parallax_lm_runner_tests", ROOT / "scripts/merlin/parallax_lm_rsi.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class LoadingInfoTests(unittest.TestCase):
    def test_empty_sets_lists_and_tuples_normalize_to_json_arrays(self):
        keys = ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")
        for empty in (set(), [], ()):
            info = {key: deepcopy(empty) for key in keys}
            normalized = runner.normalize_loading_info(info)
            self.assertEqual(normalized, {key: [] for key in keys})
            self.assertEqual(json.loads(runner.canonical(normalized)), normalized)

    def test_loading_defects_unknown_fields_and_non_collection_values_rejected(self):
        keys = ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")
        for key in keys:
            for value in (["defect"], {"defect"}, ("defect",), None, "", {}, 0):
                info = {field: [] for field in keys}
                info[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    runner.normalize_loading_info(info)
        for info in ({}, {key: [] for key in keys[:-1]}, {**{key: [] for key in keys}, "unknown": []}):
            with self.subTest(info=info), self.assertRaises(ValueError):
                runner.normalize_loading_info(info)


class LossSummaryTests(unittest.TestCase):
    def test_shifted_targets_use_exactly_128_matching_logit_rows(self):
        # Row i assigns exp(logit)=8 to ID i+1 and 1 to the two others.
        ids = [i % 3 for i in range(129)]
        logits = np.zeros((128, 3), dtype=np.float32)
        high = np.float32(math.log(8))
        for row in range(128):
            logits[row, ids[row + 1]] = high
        result = runner.loss_summary(logits, ids)
        expected = math.log1p(2 * math.exp(-float(high)))
        self.assertEqual(result["scored_tokens"], 128)
        np.testing.assert_allclose(result["per_token_losses"], expected, rtol=0, atol=1e-14)
        self.assertAlmostEqual(result["sum_nll"], 128 * expected, places=12)
        self.assertAlmostEqual(result["perplexity"], math.exp(expected), places=14)
        changed_first = [2, *ids[1:]]  # The context's initial ID is not a target.
        self.assertEqual(runner.loss_summary(logits, changed_first), result)

    def test_large_common_logit_offset_preserves_uniform_nll(self):
        ids = [i % 3 for i in range(129)]
        for offset in (0, 1e4, 1e20, -1e20):
            with self.subTest(offset=offset):
                logits = np.full((128, 3), offset, dtype=np.float32)
                result = runner.loss_summary(logits, ids)
                np.testing.assert_allclose(result["per_token_losses"], math.log(3), rtol=0, atol=1e-12)
                self.assertAlmostEqual(result["perplexity"], 3.0, places=12)

    def test_invalid_logits_lengths_and_vocabulary_bounds_are_rejected(self):
        good = np.zeros((128, 3), dtype=np.float32)
        ids = [i % 3 for i in range(129)]
        cases = [(good.astype(np.float64), ids), (good[:127], ids), (good[None], ids),
                 (good, ids[:-1]), (good, [0, -1, *ids[2:]]), (good, [0, 3, *ids[2:]]),
                 (good[:, :0], ids)]
        for invalid in (np.nan, np.inf, -np.inf):
            nonfinite = good.copy()
            nonfinite[9, 1] = invalid
            cases.append((nonfinite, ids))
        for index, (logits, targets) in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                runner.loss_summary(logits, targets)


class FrozenEpisodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state, self.output = self.root / "state", self.root / "output"
        self.output.mkdir()
        self.protocol_path, self.lock_path = self.root / "protocol.json", self.root / "lock.json"
        self.lock_path.write_bytes(b'{"fixture":"no checkpoint files or model"}\n')
        self.run_id, self.commit = "synthetic-runner-regression", "a" * 40
        self.prefix = "research/parallax-lm/" + self.run_id + "/"
        self.sources = {"scripts/merlin/parallax_lm_rsi.py": "1" * 64,
                        "python/merlin/parallax_torch_centered.py": "2" * 64}
        self.protocol = {
            "schema": "merlin-parallax-lm-protocol/1", "model_id": runner.MODEL_ID,
            "revision": runner.REVISION, "cpu_threads": 2, "interop_threads": 1,
            "max_wall_seconds": 300, "model_dtype": "float32", "input_positions": 128,
            "scored_targets": 128, "total_token_ids": 129,
            "input_rule": "token_ids[:-1]", "target_rule": "token_ids[1:]",
            "add_special_tokens": False, "padding": False, "chat_template": False,
            "use_cache": False, "attention_implementation": "eager",
            "inference_mode": True, "autocast": False, "test_episodes": 1,
            "test_forward_passes_max": 2, "candidates": [runner.BASELINE, runner.CANDIDATE],
            "candidate_description": "centered covariance with explicit softmax-mass normalization",
            "candidate_admission": {"finite_logits": True, "max_abs_logit_difference": 0.001},
            "selection": "lowest validation mean NLL among eligible; baseline on exact tie",
            "loss": "float64 stable logsumexp minus target logit; mean over all 128 targets",
            "perplexity": "exp(mean_nll)", "loss_chunk_positions": 16,
            "interval": None, "interval_reason": "tokens within one text window are correlated",
            "pretraining_exposure": "unknown; split held out only from this candidate selection",
            "hardware_scope": "local CPU reference; no calibrated Parallax chip simulator",
            "model_downloads": False, "model_updates": False, "production_promotion": False,
            "full_logits_retained": True, "max_logit_artifacts": 4,
            "max_logit_artifact_bytes": 128 * 1024 * 1024,
            "budget_scope": "Model load, validation, selection, test and persistence; external timeout also bounds imports and finalization",
            "required_supervisor": "GNU timeout --signal=KILL 300s",
            "source_sha256": self.sources, "checkpoint_lock_sha256": sha256(self.lock_path.read_bytes()).hexdigest(),
            "checkpoint_files": [], "runtime": {"fixture": "never queried"}, "splits": {}}
        for split, offset in (("validation", 0), ("test", 1)):
            ids = [(i + offset) % 3 for i in range(129)]
            self.protocol["splits"][split] = {"token_ids": ids, "token_ids_sha256": sha256(runner.canonical(ids)).hexdigest()}
        self.write_protocol(self.protocol)
        self.window = runner.ResearchWindow(self.state, project_id="parallax-rsi")
        self.registry = self.window.registry
        self.ledger = runner.EvidenceLedger(self.state / "parallax-lm-evidence.jsonl")

    def write_protocol(self, protocol):
        self.protocol_path.write_bytes(runner.canonical(protocol) + b"\n")

    def put_record(self, name, record):
        content = runner.canonical(record)
        self.registry.put_artifact(self.window.project_id, self.prefix + name, content, "application/json")
        (self.output / name).write_bytes(content + b"\n")
        return "sha256:" + sha256(content).hexdigest()

    def payload(self, name):
        memory = io.BytesIO()
        np.save(memory, np.zeros((128, 3), dtype=np.float32), allow_pickle=False)
        content = memory.getvalue()
        (self.output / name).write_bytes(content)
        digest = self.registry.put_artifact(self.window.project_id, self.prefix + name, content, "application/octet-stream")
        return {"filename": name, "bytes": len(content), "sha256": digest, "shape": [128, 3],
                "dtype": "float32", "artifact_ref": self.registry.artifact_ref(self.window.project_id, self.prefix + name)}

    def seed_episode(self, *, complete=False, anchor=None, separate_equal_payload=False):
        self.put_record("protocol.json", self.protocol)
        initial = {"source_commit": self.commit,
                   "protocol_sha256": anchor or sha256(runner.canonical(self.protocol)).hexdigest(),
                   "clock": {"started_unix_seconds": 123.0, "last_seen_unix_seconds": 124.0, "consumed_seconds": 1.0}}
        coordinator = LoopCoordinator()
        coordinator.add(Loop("initialization", "research"))
        coordinator.start("initialization")
        coordinator.finish("initialization", passed=True, evidence=self.put_record("initialization.json", initial))
        previous = "initialization"
        names = ("load", "validation-baseline", "validation-candidate", "selection", "test")
        for name in names:
            coordinator.add(Loop(name, "research", dependencies=(previous,)))
            previous = name
        receipt = None
        if complete:
            base = {"candidate": runner.BASELINE, "perplexity": 3.0, "mean_nll": math.log(3),
                    "logits": self.payload("synthetic-baseline-logits.npy")}
            candidate = {"candidate": runner.CANDIDATE, "logit_gate_passed": False, "rejected_reason": "synthetic fixture"}
            if separate_equal_payload:
                candidate["logits"] = self.payload("synthetic-candidate-logits.npy")
            selection = {"selected_candidate": runner.BASELINE, "production_promotion": False}
            receipt = {"run_id": self.run_id, "source_commit": self.commit, "fixture_only": True,
                       "trained_language_model_evaluated": False,
                       "validation": {"baseline": base, "candidate": candidate},
                       "selection": selection, "test": {"baseline": base, "selected": base, "episode_count": 1}}
            records = ({"fixture_only": True}, base, candidate, selection, receipt)
            for name, record in zip(names, records):
                coordinator.start(name)
                coordinator.finish(name, passed=True, evidence=self.put_record(name + ".json", record))
            self.put_record("receipt.json", receipt)
            self.put_record("finalization.json", {"receipt_sha256": sha256(runner.canonical(receipt)).hexdigest(), "status": "exported"})
        else:
            coordinator.start("load")  # Persisted running work must become blocked, not restart.
        runner.checkpoint(coordinator, self.ledger, plan_id=self.run_id)
        return receipt

    @contextmanager
    def runtime_must_remain_unreached(self):
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.split(".", 1)[0] in {"torch", "transformers", "tokenizers", "safetensors"}:
                raise AssertionError("resume path attempted a model/runtime import: " + name)
            return original_import(name, *args, **kwargs)

        with patch.object(runner, "source_hashes", return_value=deepcopy(self.sources)), \
             patch.object(runner, "verify_checkpoint", side_effect=AssertionError("checkpoint must remain unopened")) as check, \
             patch.object(runner, "runtime", side_effect=AssertionError("runtime must remain unqueried")) as runtime, \
             patch.object(runner, "checkpoint", side_effect=AssertionError("episode must not checkpoint/restart")) as persist, \
             patch("builtins.__import__", side_effect=guarded_import):
            try:
                yield
            finally:
                check.assert_not_called()
                runtime.assert_not_called()
                persist.assert_not_called()

    def execute(self, *, commit=None):
        return runner.execute(self.root / "absent-checkpoint", self.protocol_path, self.lock_path,
                              self.state, self.output, self.run_id, commit or self.commit)

    def test_protocol_shape_identity_and_token_bounds_are_frozen(self):
        runner.validate_protocol(self.protocol)
        for field, value in (("input_positions", 129), ("scored_targets", 127), ("total_token_ids", 128),
                             ("revision", "0" * 40), ("cpu_threads", 3), ("test_episodes", 2),
                             ("input_rule", "token_ids"), ("target_rule", "token_ids[:-1]"),
                             ("scored_targets", 128.0), ("use_cache", 0), ("required_supervisor", "none")):
            changed = deepcopy(self.protocol)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                runner.validate_protocol(changed)
        for replacement in ([0] * 128, [0] * 128 + [-1], [0] * 128 + [True], [0] * 128 + [1.5]):
            changed = deepcopy(self.protocol)
            row = changed["splits"]["test"]
            row["token_ids"] = replacement
            row["token_ids_sha256"] = sha256(runner.canonical(replacement)).hexdigest()
            with self.subTest(last=replacement[-1]), self.assertRaises(ValueError):
                runner.validate_protocol(changed)
        changed = deepcopy(self.protocol)
        changed["splits"]["test"]["token_ids"][3] = 9
        with self.assertRaisesRegex(ValueError, "invalid frozen token sequence"):
            runner.validate_protocol(changed)

    def test_changed_source_or_lock_rejected_before_runtime(self):
        for field in ("source_sha256", "checkpoint_lock_sha256"):
            changed = deepcopy(self.protocol)
            changed[field] = {} if field == "source_sha256" else "0" * 64
            self.write_protocol(changed)
            with self.subTest(field=field), self.runtime_must_remain_unreached():
                with self.assertRaisesRegex(ValueError, "frozen source or checkpoint lock changed"):
                    self.execute()

    def test_persisted_interruption_refuses_replay_and_budget_renewal(self):
        self.seed_episode()
        before = self.ledger.path.read_bytes()
        for attempt in range(2):
            with self.subTest(attempt=attempt), self.runtime_must_remain_unreached():
                with self.assertRaisesRegex(RuntimeError, "incomplete episode requires review"):
                    self.execute()
            self.assertEqual(self.ledger.path.read_bytes(), before)

    def test_rehashed_token_mutation_and_changed_commit_cannot_resume(self):
        self.seed_episode()
        changed = deepcopy(self.protocol)
        row = changed["splits"]["test"]
        row["token_ids"][17] = (row["token_ids"][17] + 1) % 3
        row["token_ids_sha256"] = sha256(runner.canonical(row["token_ids"])).hexdigest()
        self.write_protocol(changed)
        with self.runtime_must_remain_unreached(), self.assertRaisesRegex(RuntimeError, "frozen episode identity changed"):
            self.execute()
        self.write_protocol(self.protocol)
        with self.runtime_must_remain_unreached(), self.assertRaisesRegex(RuntimeError, "frozen episode identity changed"):
            self.execute(commit="b" * 40)

    def test_completed_synthetic_receipt_returns_without_runtime_or_inference(self):
        expected = self.seed_episode(complete=True)
        before = self.ledger.path.read_bytes()
        with self.runtime_must_remain_unreached():
            self.assertEqual(self.execute(), expected)
        self.assertEqual(self.ledger.path.read_bytes(), before)
        self.assertFalse(expected["trained_language_model_evaluated"])

    def test_superseded_protocol_is_not_silently_accepted(self):
        self.seed_episode()
        replacement = deepcopy(self.protocol)
        replacement["max_wall_seconds"] = 301
        self.registry.put_artifact(self.window.project_id, self.prefix + "protocol.json", runner.canonical(replacement), "application/json")
        with self.runtime_must_remain_unreached(), self.assertRaisesRegex(RuntimeError, "immutable artifact superseded"):
            self.execute()

    def test_superseded_initialization_cannot_replace_the_clock_anchor(self):
        self.seed_episode()
        self.registry.put_artifact(self.window.project_id, self.prefix + "initialization.json", b'{"clock":{"started_unix_seconds":9999999999}}', "application/json")
        with self.runtime_must_remain_unreached(), self.assertRaisesRegex(RuntimeError, "immutable artifact superseded"):
            self.execute()

    def test_inconsistent_protocol_anchor_is_rejected(self):
        self.seed_episode(anchor="f" * 64)
        with self.runtime_must_remain_unreached(), self.assertRaisesRegex(RuntimeError, "protocol anchor changed"):
            self.execute()

    def test_superseded_logit_payload_is_rejected_without_inference(self):
        self.seed_episode(complete=True)
        self.registry.put_artifact(self.window.project_id, self.prefix + "synthetic-baseline-logits.npy", b"changed payload", "application/octet-stream")
        with self.runtime_must_remain_unreached(), self.assertRaisesRegex(RuntimeError, "frozen logit artifact changed"):
            self.execute()

    def test_same_digest_different_artifact_still_requires_integrity_verification(self):
        self.seed_episode(complete=True, separate_equal_payload=True)
        self.registry.put_artifact(self.window.project_id, self.prefix + "synthetic-candidate-logits.npy", b"changed second payload", "application/octet-stream")
        with self.runtime_must_remain_unreached(), self.assertRaisesRegex(RuntimeError, "frozen logit artifact changed"):
            self.execute()

    def test_same_size_export_corruption_is_detected(self):
        self.seed_episode(complete=True)
        path = self.output / "synthetic-baseline-logits.npy"
        original = path.read_bytes()
        path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.runtime_must_remain_unreached(), self.assertRaisesRegex(RuntimeError, "exported logit payload changed"):
            self.execute()

    def recovery_protocol(self):
        initial = json.loads((self.output / "initialization.json").read_bytes())
        revised = deepcopy(self.protocol)
        revised["source_sha256"]["scripts/merlin/parallax_lm_rsi.py"] = "3" * 64
        revised["reviewed_pre_forward_recovery"] = {
            "parent_run": self.run_id,
            "parent_ledger_file_sha256": sha256(self.ledger.path.read_bytes()).hexdigest(),
            "parent_initialization_sha256": sha256(runner.canonical(initial)).hexdigest(),
            "original_deadline_unix_seconds": 423.0,
        }
        return revised

    def test_reviewed_recovery_retains_original_deadline_and_consumes_one_claim(self):
        self.seed_episode()
        revised = self.recovery_protocol()
        ledger_before = self.ledger.path.read_bytes()
        with patch.object(runner.time, "time", return_value=200.0):
            result = runner.verify_pre_forward_recovery(revised, self.registry, self.ledger, "synthetic-repaired")
            self.assertEqual(result, {"started_unix_seconds": 123.0, "deadline_unix_seconds": 423.0})
            with self.assertRaisesRegex(RuntimeError, "allowance already consumed"):
                runner.verify_pre_forward_recovery(revised, self.registry, self.ledger, "synthetic-repaired-again")
        self.assertEqual(self.ledger.path.read_bytes(), ledger_before)
        self.assertEqual(runner.restore(self.ledger, plan_id=self.run_id).loops["load"].state, "blocked")

    def test_reviewed_recovery_cannot_renew_expired_budget(self):
        self.seed_episode()
        revised = self.recovery_protocol()
        with patch.object(runner.time, "time", return_value=423.0):
            with self.assertRaisesRegex(TimeoutError, "budget exhausted"):
                runner.verify_pre_forward_recovery(revised, self.registry, self.ledger, "synthetic-repaired")
        self.assertFalse(self.registry.artifact_history(self.window.project_id, self.prefix + "reviewed-recovery-claim.json"))

    def test_reviewed_recovery_cannot_change_candidate_or_tokens(self):
        self.seed_episode()
        for changed_field in ("candidate", "tokens"):
            revised = self.recovery_protocol()
            if changed_field == "candidate":
                revised["source_sha256"]["python/merlin/parallax_torch_centered.py"] = "0" * 64
            else:
                revised["splits"]["test"]["token_ids"][7] = 99
            with self.subTest(field=changed_field), patch.object(runner.time, "time", return_value=200.0):
                with self.assertRaisesRegex(ValueError, "recovery changed"):
                    runner.verify_pre_forward_recovery(revised, self.registry, self.ledger, "synthetic-repaired")
        self.assertFalse(self.registry.artifact_history(self.window.project_id, self.prefix + "reviewed-recovery-claim.json"))


if __name__ == "__main__":
    unittest.main()
