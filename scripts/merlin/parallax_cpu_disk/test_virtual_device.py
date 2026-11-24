#!/usr/bin/env python3
"""Policy tests plus small CPU operation fixtures; no checkpoint is loaded."""
from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import parallax_virtual_device as device

try:
    import torch
except ImportError:
    torch = None


class AdmissionPolicyTests(unittest.TestCase):
    def test_limit_caps_and_types(self):
        for values in ({"max_forward_calls": True}, {"max_query_tokens": 65},
                       {"max_context_tokens": 81}, {"max_logits_bytes": 0},
                       {"max_torch_threads": 3}, {"max_forward_calls": 17},
                       {"max_context_tokens": 1}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                device.ExecutionLimits(**values)

    def test_unknown_backend_refuses_before_capability_query(self):
        with patch.object(device, "capabilities", side_effect=AssertionError("queried")):
            with self.assertRaisesRegex(ValueError, "explicitly cpu or cuda"):
                device.select_backend("auto")

    def test_cuda_never_silently_falls_back(self):
        # These are decision fixtures, not observations of physical GPU hardware.
        for built, available, word in ((False, False, "unavailable"),
                                       (True, False, "unavailable"), (True, True, "unqualified")):
            with self.subTest(built=built, available=available):
                with patch.object(device, "capabilities", return_value={"cuda_built": built, "cuda_available": available}):
                    with self.assertRaisesRegex(device.BackendUnavailable, word):
                        device.select_backend("cuda")


@unittest.skipIf(torch is None, "the pinned offline Torch runtime is required for CPU fixtures")
class ExecutionFixtures(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.accelerator = device.select_backend()
        self.model = self.make_model()
        self.ids = torch.tensor([[1, 3]], dtype=torch.long)
        self.mask = torch.ones((1, 2), dtype=torch.long)

    @staticmethod
    def make_model():
        class SmallModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.config = SimpleNamespace(vocab_size=17)
                self.weight = torch.nn.Parameter(torch.arange(68, dtype=torch.float32).reshape(17, 4) / 64)
                self.calls = 0
                self.transform = lambda value: value
                self.observed_inference = False

            def forward(self, *, input_ids, attention_mask, past_key_values, use_cache, return_dict):
                self.calls += 1
                self.observed_inference = torch.is_inference_mode_enabled()
                hidden = self.weight[input_ids]
                logits = self.transform(hidden @ self.weight.T)
                size = attention_mask.shape[1]
                values = torch.zeros((1, 1, size, 4), dtype=torch.float32)
                cache = SimpleNamespace(layers=[SimpleNamespace(keys=values, values=values)],
                                        get_seq_length=lambda: size)
                return SimpleNamespace(logits=logits, past_key_values=cache)
        return SmallModel().eval()

    def call(self, **changes):
        args = {"input_ids": self.ids, "attention_mask": self.mask}
        args.update(changes)
        return self.accelerator.forward(self.model, **args)

    def test_actual_cpu_operation_equals_direct_and_decode(self):
        with torch.inference_mode():
            expected = self.model(input_ids=self.ids, attention_mask=self.mask,
                                  past_key_values=None, use_cache=True, return_dict=True).logits
        actual = self.call()
        self.assertTrue(torch.equal(actual.logits, expected))
        self.assertTrue(self.model.observed_inference)
        next_result = self.call(input_ids=torch.tensor([[4]]), attention_mask=torch.ones((1, 3), dtype=torch.long),
                                past_key_values=actual.past_key_values)
        self.assertEqual(tuple(next_result.logits.shape), (1, 1, 17))
        snapshot = self.accelerator.snapshot()
        self.assertEqual(snapshot["completed_calls"], 2)
        self.assertEqual(snapshot["maximum_returned_logits_bytes"], 136)
        self.assertFalse(snapshot["hardware_acceleration"])
        self.assertEqual(snapshot["actual_device"], "cpu")

    def test_input_and_mask_rejections_do_not_execute(self):
        cases = [{"input_ids": self.ids.float()}, {"input_ids": torch.tensor([[-1, 2]])},
                 {"attention_mask": torch.tensor([[1, 0]])},
                 {"attention_mask": torch.ones((1, 3), dtype=torch.long)},
                 {"input_ids": torch.ones((1, 65), dtype=torch.long)}, {"use_cache": False}]
        for changes in cases:
            with self.subTest(changes=list(changes)), self.assertRaises(ValueError):
                self.call(**changes)
        self.assertEqual(self.model.calls, 0)
        self.assertFalse(self.accelerator.snapshot()["poisoned"])
        self.call()

    def test_predicted_bytes_context_and_calls_are_preflighted(self):
        self.accelerator = device.select_backend(limits=device.ExecutionLimits(max_logits_bytes=135))
        with self.assertRaisesRegex(ValueError, "predicted logits"):
            self.call()
        self.assertEqual(self.model.calls, 0)
        self.accelerator = device.select_backend(limits=device.ExecutionLimits(max_query_tokens=2, max_context_tokens=2))
        prior = self.call()
        with self.assertRaisesRegex(ValueError, "context token bound"):
            self.call(input_ids=torch.tensor([[1]]), past_key_values=prior.past_key_values,
                      attention_mask=torch.ones((1, 3), dtype=torch.long))
        self.accelerator = device.select_backend(limits=device.ExecutionLimits(max_forward_calls=1))
        self.call()
        calls = self.model.calls
        with self.assertRaisesRegex(ValueError, "call budget"):
            self.call()
        self.assertEqual(self.model.calls, calls)

    def test_actual_returned_byte_limit_and_poison(self):
        self.accelerator = device.select_backend(limits=device.ExecutionLimits(max_logits_bytes=136))
        self.model.transform = lambda value: torch.zeros((1, 2, 18), dtype=torch.float32)
        with self.assertRaisesRegex(ValueError, "actual returned logits"):
            self.call()
        with self.assertRaisesRegex(ValueError, "poisoned"):
            self.call()
        self.assertEqual(self.model.calls, 1)
        self.assertFalse(self.accelerator.snapshot()["in_flight"])
        self.assertEqual(self.accelerator.snapshot()["failed_calls"], 1)

    def test_nonfinite_and_wrong_device_returned_tensors(self):
        for transform, message in ((lambda value: value * float("nan"), "finite"),
                                   (lambda value: value.to("meta"), "CPU FP32")):
            self.accelerator = device.select_backend()
            self.model.transform = transform
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.call()

    def test_small_view_of_oversized_backing_storage_is_rejected(self):
        self.accelerator = device.select_backend(limits=device.ExecutionLimits(max_logits_bytes=136))
        self.model.transform = lambda value: torch.zeros((1, 2, 40), dtype=torch.float32)[:, :, :17]
        with self.assertRaisesRegex(ValueError, "backing storage"):
            self.call()
        self.assertTrue(self.accelerator.snapshot()["poisoned"])

    def test_borrowed_cache_and_buffer_devices_are_checked(self):
        value = torch.empty((1, 1, 1, 4), device="meta")
        cache = SimpleNamespace(layers=[SimpleNamespace(keys=value, values=value)], get_seq_length=lambda: 1)
        with self.assertRaisesRegex(ValueError, "borrowed cache"):
            self.call(past_key_values=cache)
        self.model.register_buffer("unexpected", torch.empty(1, device="meta"))
        with self.assertRaisesRegex(ValueError, "model buffers"):
            self.call()
        self.assertEqual(self.model.calls, 0)

    def test_reentrant_execution_is_rejected(self):
        # Reentrant use exercises the same lock admission as concurrent callers.
        def try_nested(value):
            with self.assertRaisesRegex(ValueError, "one forward"):
                self.call()
            return value
        self.model.transform = try_nested
        self.call()
        self.assertEqual(self.model.calls, 1)
        self.assertEqual(self.accelerator.snapshot()["rejected_calls"], 1)

    def test_model_fault_poison_and_thread_bound(self):
        torch.set_num_threads(3)
        with self.assertRaisesRegex(ValueError, "thread count"):
            self.call()
        torch.set_num_threads(2)
        def fail(value):
            raise RuntimeError("synthetic model fault")
        self.model.transform = fail
        with self.assertRaisesRegex(RuntimeError, "synthetic model fault"):
            self.call()
        self.assertTrue(self.accelerator.snapshot()["poisoned"])


if __name__ == "__main__":
    unittest.main()
