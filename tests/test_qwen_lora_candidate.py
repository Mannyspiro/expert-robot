"""Offline/preflight-only checks: no CUDA, download, or large model needed."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from merlin.qwen_lora_candidate import preflight, execute


class QwenCandidatePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.model = root / "source"
        self.output = root / "candidates"
        self.model.mkdir()
        self.output.mkdir()
        (self.model / "config.json").write_text(json.dumps({"model_type": "qwen2", "architectures": ["Qwen2ForCausalLM"], "hidden_size": 1536, "num_hidden_layers": 28, "num_attention_heads": 12, "num_key_value_heads": 2}))
        (self.model / "tokenizer.json").write_text("{}")
        (self.model / "model.safetensors").write_bytes(b"fixture-only")
        self.train = root / "train.json"
        self.holdout = root / "holdout.json"
        self.train.write_text(json.dumps([
            {"id":"train.1", "question":"2+3?", "answer":"5"},
            {"id":"train.2", "question":"7+1?", "answer":"8"}]))
        self.holdout.write_text(json.dumps([
            {"id":"held.1", "question":"3+4?", "answer":"7"},
            {"id":"held.2", "question":"9+2?", "answer":"11"}]))

    def test_local_only_preflight_never_claims_training(self):
        result = preflight(self.model, self.train, self.holdout, self.output)
        self.assertEqual(result["model_architecture"], "qwen2")
        self.assertEqual(result["train_cases"], 2)
        self.assertEqual(result["heldout_cases"], 2)
        self.assertFalse(result["candidate_weights_trained"])
        self.assertFalse(result["promotion_authority"])
        self.assertFalse(result["checkpoint_verified_by_operator"])
        self.assertEqual(list(self.output.iterdir()), [])

    def test_reject_leaked_and_duplicate_questions(self):
        self.holdout.write_text(json.dumps([
            {"id":"held.1", "question":" 2+3? ", "answer":"5"},
            {"id":"held.2", "question":"9+2?", "answer":"11"}]))
        with self.assertRaises(ValueError):
            preflight(self.model, self.train, self.holdout, self.output)
        self.train.write_text(json.dumps([
            {"id":"train.1", "question":"2+3?", "answer":"5"},
            {"id":"train.1", "question":"8+1?", "answer":"9"}]))
        with self.assertRaises(ValueError):
            preflight(self.model, self.train, self.holdout, self.output)

    def test_other_qwen2_sizes_are_not_misidentified_as_coder_1_5b(self):
        config=json.loads((self.model/"config.json").read_text())
        for change in ({"hidden_size":896},{"num_hidden_layers":24},
                       {"num_attention_heads":16},{"num_key_value_heads":4}):
            bad={**config,**change}
            (self.model/"config.json").write_text(json.dumps(bad))
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    preflight(self.model,self.train,self.holdout,self.output)
        (self.model/"config.json").write_text(json.dumps(config))

    def test_reject_gguf_and_unrecognized_model_architecture(self):
        (self.model / "model.gguf").write_bytes(b"fixture")
        with self.assertRaises(ValueError):
            preflight(self.model, self.train, self.holdout, self.output)
        (self.model / "model.gguf").unlink()
        (self.model / "config.json").write_text(json.dumps({"model_type":"llama"}))
        with self.assertRaises(ValueError):
            preflight(self.model, self.train, self.holdout, self.output)

    def test_bounded_train_config_rejected_before_any_model_loading(self):
        for steps, rank in ((0,4),(31,4),(1,3),("12",4),(12,False)):
            with self.subTest(steps=steps,rank=rank):
                with self.assertRaises(ValueError):
                    execute(self.model, self.train, self.holdout, self.output,
                            steps=steps,rank=rank)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_reject_symlinks_missing_weights_and_overlap_output(self):
        (self.model / "model.safetensors").unlink()
        with self.assertRaises(ValueError):
            preflight(self.model, self.train, self.holdout, self.output)
        (self.model / "model.safetensors").symlink_to(self.train)
        with self.assertRaises(ValueError):
            preflight(self.model, self.train, self.holdout, self.output)
        (self.model / "model.safetensors").unlink()
        (self.model / "model.safetensors").write_bytes(b"fixture")
        with self.assertRaises(ValueError):
            preflight(self.model, self.train, self.holdout, self.model)


if __name__ == "__main__":
    unittest.main(verbosity=2)
