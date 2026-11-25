"""Tiny CPU tensors only: independent oracle, attention semantics, and guards.

No model, checkpoint, tokenizer, corpus, validation, or held-out inputs are used.
Missing PyTorch is an explicit skip, never runtime validation of this candidate.
"""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

try:
    import torch
except ModuleNotFoundError as exc:
    if exc.name != "torch":
        raise
    torch = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
if torch is not None:
    from merlin.parallax_torch_centered import centered_parallax_forward


def raw_moment_oracle(query, r, key, value, mask, scaling):
    """Float64, explicit head/row loops, unnormalized exponential moments.

    Deliberately does not use the candidate's head expansion, softmax call,
    einsum, or centered reduction. Inputs are the same supplied projections.
    """
    _, heads, q_len, dim = query.shape
    kv_len, groups = key.shape[2], heads // key.shape[1]
    result = torch.empty((1, q_len, heads, dim), dtype=torch.float64)
    for head in range(heads):
        keys = key[0, head // groups].double()
        values = value[0, head // groups].double()
        for row in range(q_len):
            scores = torch.mv(keys, query[0, head, row].double()) * scaling
            if mask is None:
                for column in range(kv_len):
                    if column > row + kv_len - q_len:
                        scores[column] = -torch.inf
            else:
                mask_head = 0 if mask.shape[1] == 1 else head
                scores = scores + mask[0, mask_head, row, :kv_len].double()
            weights = torch.exp(scores - scores.max())
            mass = weights.sum()
            responses = torch.mv(keys, r[0, head, row].double())
            first = torch.mv(values.T, weights)
            mixed = torch.mv(values.T, weights * responses)
            response_sum = torch.dot(weights, responses)
            result[0, row, head] = (first / mass) * (1 + response_sum / mass) - mixed / mass
    return result


@unittest.skipIf(torch is None, "PyTorch is unavailable; runtime candidate checks have not run")
class ParallaxTorchTests(unittest.TestCase):
    def fixture(self, q_len=3, kv_len=3, heads=4, kv_heads=2, dim=5):
        generator = torch.Generator(device="cpu").manual_seed(7123 + 17 * q_len + kv_len)
        shapes = [(1, heads, q_len, dim)] * 2 + [(1, kv_heads, kv_len, dim)] * 2
        tensors = [torch.randn(shape, generator=generator, dtype=torch.float32) * 0.35 for shape in shapes]
        module = SimpleNamespace(training=False, num_key_value_groups=heads // kv_heads)
        return module, tensors

    def evaluate(self, module, tensors, mask=None, scaling=0.37, dropout=0.0):
        with torch.inference_mode(), torch.autocast("cpu", enabled=False):
            result, weights = centered_parallax_forward(module, *tensors, mask, scaling, dropout=dropout)
        self.assertIsNone(weights)
        self.assertEqual(result.dtype, torch.float32)
        self.assertTrue(result.is_contiguous())
        self.assertEqual(result.shape, tensors[0].transpose(1, 2).shape)
        return result

    def causal_mask(self, q_len, kv_len):
        mask = torch.zeros((1, 1, q_len, kv_len), dtype=torch.float32)
        for row in range(q_len):
            for column in range(kv_len):
                if column > row + kv_len - q_len:
                    mask[0, 0, row, column] = -torch.inf
        return mask

    def test_random_gqa_and_equal_head_cases_match_independent_float64_oracle(self):
        for q_len, kv_len, heads, kv_heads in ((3, 3, 4, 2), (2, 5, 4, 2), (1, 5, 4, 2), (3, 3, 2, 2)):
            with self.subTest(q=q_len, kv=kv_len, heads=heads, kv_heads=kv_heads):
                module, tensors = self.fixture(q_len, kv_len, heads, kv_heads)
                actual = self.evaluate(module, tensors)
                expected = raw_moment_oracle(*tensors, None, 0.37)
                torch.testing.assert_close(actual.double(), expected, rtol=3e-6, atol=3e-7)

    def test_no_mask_matches_explicit_causal_mask_including_prefix_offset(self):
        for q_len, kv_len in ((3, 3), (2, 5), (1, 5)):
            with self.subTest(q=q_len, kv=kv_len):
                module, tensors = self.fixture(q_len, kv_len)
                implicit = self.evaluate(module, tensors)
                explicit = self.evaluate(module, tensors, self.causal_mask(q_len, kv_len))
                torch.testing.assert_close(implicit, explicit, rtol=0, atol=0)

    def test_supplied_per_head_additive_mask_and_larger_span_slicing(self):
        module, tensors = self.fixture()
        mask = self.causal_mask(3, 3).expand(1, 4, 3, 3).clone()
        mask -= torch.arange(36, dtype=torch.float32).reshape(1, 4, 3, 3) / 19
        actual = self.evaluate(module, tensors, mask)
        torch.testing.assert_close(actual.double(), raw_moment_oracle(*tensors, mask, 0.37), rtol=3e-6, atol=3e-7)
        padded = torch.full((1, 4, 5, 6), -torch.inf, dtype=torch.float32)
        padded[:, :, :3, :3] = mask
        torch.testing.assert_close(actual, self.evaluate(module, tensors, padded), rtol=0, atol=0)

    def test_cached_offset_single_query_and_explicit_noncausal_mask(self):
        module = SimpleNamespace(training=False, num_key_value_groups=2)
        key = torch.zeros((1, 1, 4, 1), dtype=torch.float32)
        value = torch.tensor([0.0, 0.0, 6.0, 18.0]).reshape(1, 1, 4, 1)
        query = torch.zeros((1, 2, 2, 1), dtype=torch.float32)
        tensors = [query, query.clone(), key, value]
        expected = torch.tensor([2.0, 6.0]).reshape(1, 2, 1, 1).expand(1, 2, 2, 1)
        torch.testing.assert_close(self.evaluate(module, tensors), expected, rtol=0, atol=3e-7)
        # An explicitly supplied zero mask does not acquire extra causal masking.
        full = self.evaluate(module, tensors, torch.zeros((1, 1, 2, 4)))
        torch.testing.assert_close(full, torch.full_like(full, 6.0), rtol=0, atol=0)
        single = [query[:, :, :1], query[:, :, :1].clone(), key, value]
        decoded = self.evaluate(module, single)
        torch.testing.assert_close(decoded, torch.full_like(decoded, 6.0), rtol=0, atol=0)

    def test_gqa_maps_adjacent_query_heads_to_the_same_kv_head(self):
        module, tensors = self.fixture()
        tensors[0].zero_()
        tensors[1].zero_()
        tensors[3][:, 0].fill_(2.0)
        tensors[3][:, 1].fill_(-3.0)
        result = self.evaluate(module, tensors)
        expected = torch.tensor([2.0, 2.0, -3.0, -3.0]).reshape(1, 1, 4, 1).expand_as(result)
        torch.testing.assert_close(result, expected, rtol=0, atol=5e-7)

    def test_training_dropout_and_missing_inference_mode_are_rejected(self):
        module, tensors = self.fixture()
        module.training = True
        with self.assertRaisesRegex(ValueError, "dropout-free inference"):
            self.evaluate(module, tensors)
        module.training = False
        with self.assertRaisesRegex(ValueError, "dropout-free inference"):
            self.evaluate(module, tensors, dropout=0.1)
        with torch.inference_mode(False), torch.enable_grad():
            with self.assertRaisesRegex(ValueError, "requires inference_mode"):
                centered_parallax_forward(module, *tensors, None, 0.37)
        with torch.inference_mode(False), torch.no_grad():
            with self.assertRaisesRegex(ValueError, "requires inference_mode"):
                centered_parallax_forward(module, *tensors, None, 0.37)

    def test_cpu_autocast_is_rejected(self):
        module, tensors = self.fixture()
        with torch.inference_mode(), torch.autocast("cpu", dtype=torch.bfloat16):
            with self.assertRaisesRegex(ValueError, "autocast disabled"):
                centered_parallax_forward(module, *tensors, None, 0.37)

    def test_each_non_fp32_projection_is_rejected(self):
        module, tensors = self.fixture()
        for index in range(4):
            for dtype in (torch.float16, torch.bfloat16, torch.float64):
                with self.subTest(input=index, dtype=dtype):
                    changed = list(tensors)
                    changed[index] = changed[index].to(dtype)
                    with self.assertRaisesRegex(ValueError, "requires FP32"):
                        self.evaluate(module, changed)

    def test_mask_broadcast_expansion_dtype_rank_and_span_are_rejected(self):
        module, tensors = self.fixture()
        shapes = ((2, 1, 3, 3), (1, 5, 3, 3), (1, 1, 2, 3), (1, 1, 3, 2),
                  (1, 1, 130, 3), (1, 1, 3, 130), (1, 3, 3))
        masks = [torch.zeros(shape) for shape in shapes]
        masks += [torch.zeros((1, 1, 3, 3), dtype=dtype) for dtype in (torch.bool, torch.float64)]
        masks += [torch.empty((1, 1, 3, 3), device="meta", dtype=torch.float32)]
        for index, mask in enumerate(masks):
            with self.subTest(case=index), self.assertRaisesRegex(ValueError, "bounded FP32 additive mask"):
                self.evaluate(module, tensors, mask)

    def test_nan_positive_infinity_and_all_masked_rows_are_rejected(self):
        module, tensors = self.fixture()
        for invalid in (torch.nan, torch.inf):
            mask = torch.zeros((1, 1, 3, 3))
            mask[0, 0, 1, 0] = invalid
            with self.subTest(value=invalid), self.assertRaisesRegex(ValueError, "NaN or positive infinity"):
                self.evaluate(module, tensors, mask)
        mask = torch.zeros((1, 1, 3, 3))
        mask[0, 0, 1] = -torch.inf
        with self.assertRaisesRegex(ValueError, "nonfinite attention output"):
            self.evaluate(module, tensors, mask)

    def test_out_of_scope_shapes_and_scaling_are_rejected(self):
        for dims in ((130, 130, 4, 2, 5), (4, 3, 4, 2, 5), (3, 3, 17, 17, 5), (3, 3, 4, 2, 129)):
            module, tensors = self.fixture(*dims)
            with self.subTest(dims=dims), self.assertRaisesRegex(ValueError, "frozen one-window"):
                self.evaluate(module, tensors)
        module, tensors = self.fixture()
        batched = [tensor.expand(2, *tensor.shape[1:]) for tensor in tensors]
        with self.assertRaisesRegex(ValueError, "frozen one-window"):
            self.evaluate(module, batched)
        for scaling in (0, -1, float("nan"), float("inf")):
            with self.subTest(scaling=scaling), self.assertRaisesRegex(ValueError, "frozen one-window"):
                self.evaluate(module, tensors, scaling=scaling)


if __name__ == "__main__":
    unittest.main()
