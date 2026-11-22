"""Budgeted Studio local model output: positive, negative, and UI contract controls.

Synthetic model transport only; no live inference, network or host mutation.
"""
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[1] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
from engine import Application
from model import LocalModel, ModelError


class OutputTokenBudgetTests(unittest.TestCase):
    def test_default_and_valid_bounds(self):
        self.assertEqual(Application.validate_settings({})["max_output_tokens"], 2048)
        for budget in (16, 64, 256, 2048):
            with self.subTest(budget=budget):
                settings = Application.validate_settings({"max_output_tokens": budget})
                self.assertEqual(settings["max_output_tokens"], budget)

    def test_invalid_budget_rejected_before_running(self):
        for budget in (None, True, False, 0, -1, 15, 2049, 4096, 64.0, "64"):
            with self.subTest(budget=budget):
                with self.assertRaises(ValueError):
                    Application.validate_settings({"max_output_tokens": budget})

    def test_model_emits_exact_selected_limit(self):
        observed = []
        def transport(method, path, body, timeout):
            observed.append((method, path, body, timeout))
            return {"choices": [{"message": {"role": "assistant", "content": "42"}}]}
        for limit in (16, 64, 256, 2048):
            with self.subTest(limit=limit):
                model = LocalModel({"model_id": "test", "max_output_tokens": limit}, transport=transport)
                answer = model.complete([{"role":"user", "content":"Compute 6 times 7"}], [], timeout=10)
                self.assertEqual(answer["content"], "42")
                self.assertEqual(observed[-1][0:2], ("POST", "/v1/chat/completions"))
                self.assertEqual(observed[-1][2]["max_tokens"], limit)
                self.assertEqual(observed[-1][3], 10)

    def test_invalid_direct_model_input_fails_before_transport(self):
        invoked = []
        def transport(*args):
            invoked.append(args)
            raise AssertionError("untrusted budget reached model transport")
        for limit in (True, 64.2, -1, 4096):
            model = LocalModel({"max_output_tokens": limit}, transport=transport)
            with self.subTest(limit=limit), self.assertRaises(ModelError):
                model.complete([], [], timeout=5)
        self.assertEqual(invoked, [])

    def test_ui_explicitly_reads_and_writes_budget(self):
        source = (STUDIO / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="max-output-tokens"', source)
        self.assertIn("settings.max_output_tokens??2048", source)
        self.assertIn("max_output_tokens:tokens", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
