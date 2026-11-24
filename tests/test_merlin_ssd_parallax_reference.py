"""Independent numerical and storage tests for single-query Parallax attention.

The oracle uses high-precision normalized probabilities and centered covariance.
It intentionally does not reproduce the implementation's online accumulators.
"""
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import random
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import merlin.ssd_parallax_reference as parallax_module
from merlin.ssd_parallax_reference import (
    load_kv_store,
    parallax_attention_file,
    parallax_attention_resident,
    write_kv_store,
)

HEADER = struct.Struct("<8sIIII32s")


def _decimal(value):
    return Decimal.from_float(value) if isinstance(value, float) else Decimal(value)


def covariance_oracle(q, r, keys, values, scale=None):
    """Independent 70-digit expression: E[V] - Cov(r.K, V)."""
    with localcontext() as context:
        context.prec = 70
        query = list(map(_decimal, q))
        projector = list(map(_decimal, r))
        key_rows = [list(map(_decimal, row)) for row in keys]
        value_rows = [list(map(_decimal, row)) for row in values]
        # Match the API's float64 default scale rather than changing its input.
        multiplier = _decimal(1.0 / math.sqrt(len(q)) if scale is None else scale)
        logits = [sum(a * b for a, b in zip(query, row)) * multiplier
                  for row in key_rows]
        weights = [(logit - max(logits)).exp() for logit in logits]
        denominator = sum(weights)
        probabilities = [weight / denominator for weight in weights]
        projected = [sum(a * b for a, b in zip(projector, row))
                     for row in key_rows]
        mean_projection = sum(p * u for p, u in zip(probabilities, projected))
        answer = []
        for dimension in range(len(values[0])):
            mean_value = sum(p * row[dimension]
                             for p, row in zip(probabilities, value_rows))
            covariance = sum(p * (u - mean_projection) * (row[dimension] - mean_value)
                             for p, u, row in zip(probabilities, projected, value_rows))
            answer.append(float(mean_value - covariance))
        return answer


def softmax_oracle(q, keys, values, scale):
    """Separately express the r=0 identity without a covariance calculation."""
    with localcontext() as context:
        context.prec = 70
        scores = [sum(_decimal(a) * _decimal(b) for a, b in zip(q, row))
                  * _decimal(scale) for row in keys]
        mass = [(score - max(scores)).exp() for score in scores]
        total = sum(mass)
        return [float(sum(weight * _decimal(row[j])
                          for weight, row in zip(mass, values)) / total)
                for j in range(len(values[0]))]


class ParallaxAttentionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.q = [0.3, -0.8, 0.2]
        self.r = [-0.5, 0.7, 0.1]
        self.keys = [[1.0, 0.5, -1.0], [-0.5, 2.0, 0.25],
                     [0.0, -0.75, 0.8], [2.0, 0.25, -0.4]]
        self.values = [[0.2, -0.6], [1.5, 0.4], [-0.7, 1.2], [2.0, -0.9]]

    def assertVectorClose(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertTrue(math.isfinite(a))
            self.assertTrue(math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10),
                            msg=f"actual={actual!r}, expected={expected!r}")

    def store(self, keys=None, values=None, name="fixture.kv"):
        path = self.directory / name
        metadata = write_kv_store(path, self.keys if keys is None else keys,
                                  self.values if values is None else values)
        return path, metadata

    def evaluate_both(self, q, r, keys, values, *, scale=None, name="fixture.kv"):
        path, metadata = self.store(keys, values, name)
        return (
            parallax_attention_resident(q, r, keys, values, qk_scale=scale)["output"],
            parallax_attention_file(path, q, r, expected_sha256=metadata["sha256"],
                                    qk_scale=scale, block_records=2)["output"],
        )

    def test_actual_parallax_formula_matches_independent_decimal_covariance(self):
        for scale in (None, 0.25, 1.7):
            expected = covariance_oracle(self.q, self.r, self.keys, self.values, scale)
            for actual in self.evaluate_both(self.q, self.r, self.keys, self.values,
                                            scale=scale, name=f"formula-{scale}.kv"):
                self.assertVectorClose(actual, expected)
        plain = softmax_oracle(self.q, self.keys, self.values, 0.25)
        adjusted = covariance_oracle(self.q, self.r, self.keys, self.values, 0.25)
        self.assertGreater(max(abs(a - b) for a, b in zip(plain, adjusted)), 0.1)

    def test_zero_projector_is_softmax_attention(self):
        zero_r = [0.0] * len(self.q)
        expected = softmax_oracle(self.q, self.keys, self.values, 0.4)
        for actual in self.evaluate_both(self.q, zero_r, self.keys, self.values,
                                        scale=0.4):
            self.assertVectorClose(actual, expected)

    def test_singleton_and_constant_values_have_zero_covariance(self):
        cases = [([[3.0, -1.0, 0.5]], [[7.0, -2.0]]),
                 (self.keys, [[7.0, -2.0]] * len(self.keys))]
        for i, (keys, values) in enumerate(cases):
            for actual in self.evaluate_both(self.q, self.r, keys, values,
                                            name=f"constant-{i}.kv"):
                self.assertVectorClose(actual, [7.0, -2.0])

    def test_signed_correction_can_leave_the_convex_hull(self):
        keys, values = [[0.0], [1.0]], [[0.0], [1.0]]
        for actual in self.evaluate_both([0.0], [4.0], keys, values):
            self.assertVectorClose(actual, [-0.5])
            self.assertLess(actual[0], min(row[0] for row in values))

    def test_constant_keys_give_uniform_mean_with_zero_covariance(self):
        keys = [[2.0, -3.0]] * 3
        values = [[2.0, 5.0], [-4.0, 1.0], [8.0, -3.0]]
        for actual in self.evaluate_both([1.0, -0.4], [-7.0, 3.0], keys, values):
            self.assertVectorClose(actual, [2.0, 1.0])

    def test_large_common_key_and_value_offsets_preserve_fine_correction(self):
        keys = [[1e12 + row[0], -1e12 + row[1]] for row in self.keys]
        values = [[1e8 + row[0], -1e8 + row[1]] for row in self.values]
        q, r = [0.3, -0.8], [-0.5, 0.7]
        expected = covariance_oracle(q, r, keys, values)
        for actual in self.evaluate_both(q, r, keys, values):
            for a, b in zip(actual, expected):
                # Relative tolerance against a large offset would conceal loss
                # of the small attention correction; check a few FP64 ULPs.
                self.assertLessEqual(abs(a - b), 8 * math.ulp(b))

    def test_key_translation_is_invariant(self):
        translation = [2.0, -4.0, 0.5]
        shifted = [[x + offset for x, offset in zip(row, translation)]
                   for row in self.keys]
        expected = covariance_oracle(self.q, self.r, self.keys, self.values)
        for actual in self.evaluate_both(self.q, self.r, shifted, self.values):
            self.assertVectorClose(actual, expected)

    def test_value_translation_is_equivariant(self):
        translation = [3.0, -2.0]
        shifted = [[x + offset for x, offset in zip(row, translation)]
                   for row in self.values]
        expected = [x + offset for x, offset in zip(
            covariance_oracle(self.q, self.r, self.keys, self.values), translation)]
        for actual in self.evaluate_both(self.q, self.r, self.keys, shifted):
            self.assertVectorClose(actual, expected)

    def test_kv_permutation_preserves_pairing_and_result(self):
        order = [2, 0, 3, 1]
        expected = covariance_oracle(self.q, self.r, self.keys, self.values)
        for actual in self.evaluate_both(self.q, self.r,
                                        [self.keys[i] for i in order],
                                        [self.values[i] for i in order]):
            self.assertVectorClose(actual, expected)

    def test_positive_negative_projector_and_unscaled_correction(self):
        # r.K is signed and is not multiplied by the q.K softmax scale.
        for i, multiplier in enumerate((-3.0, 0.125, 2.0)):
            projector = [multiplier * x for x in self.r]
            expected = covariance_oracle(self.q, projector, self.keys, self.values, 0.125)
            for actual in self.evaluate_both(self.q, projector, self.keys, self.values,
                                            scale=0.125, name=f"projector-{i}.kv"):
                self.assertVectorClose(actual, expected)

    def test_multiple_block_boundaries_and_single_payload_pass(self):
        rng = random.Random(173)
        keys = [[rng.uniform(-2, 2) for _ in range(3)] for _ in range(19)]
        values = [[rng.uniform(-1, 1) for _ in range(5)] for _ in range(19)]
        expected = covariance_oracle(self.q, self.r, keys, values)
        path, metadata = self.store(keys, values)
        for block_records in (1, 2, 3, 8, 19, 64):
            with self.subTest(block_records=block_records):
                result = parallax_attention_file(
                    path, self.q, self.r, expected_sha256=metadata["sha256"],
                    block_records=block_records)
                self.assertVectorClose(result["output"], expected)
                io = result["io"]
                self.assertEqual(io["payload_passes"], 1)
                self.assertEqual(io["payload_bytes_read"], metadata["payload_bytes"])
                self.assertEqual(io["bytes_read"], metadata["file_bytes"])
                self.assertLessEqual(io["peak_read_buffer_bytes"],
                                     max(HEADER.size, block_records * 8 * (3 + 5)))

    def test_extreme_logits_remain_finite_and_rescale_after_new_maximum(self):
        keys = [[-1000.0, 1.0], [1000.0, -0.5], [999.75, 0.2],
                [-900.0, -2.0], [1001.0, 0.7]]
        values = [[2.0, -1.0], [-0.2, 0.7], [1.4, -0.8],
                  [5.0, 5.0], [0.9, -0.1]]
        q, r = [1.0, 0.0], [0.001, -0.3]
        expected = covariance_oracle(q, r, keys, values, 1.0)
        path, metadata = self.store(keys, values)
        self.assertVectorClose(parallax_attention_resident(
            q, r, keys, values, qk_scale=1.0)["output"], expected)
        for block in (1, 2, 3):
            self.assertVectorClose(parallax_attention_file(
                path, q, r, expected_sha256=metadata["sha256"],
                qk_scale=1.0, block_records=block)["output"], expected)

    def test_valid_store_round_trip_and_byte_contract(self):
        # Single-pass outer iterators are accepted by the writer.
        path, metadata = self.store(iter(self.keys), iter(self.values))
        loaded = load_kv_store(path, expected_sha256=metadata["sha256"])
        self.assertEqual(tuple(map(tuple, self.keys)), loaded["keys"])
        self.assertEqual(tuple(map(tuple, self.values)), loaded["values"])
        raw = path.read_bytes()
        magic, version, count, kd, vd, digest = HEADER.unpack(raw[:HEADER.size])
        self.assertEqual((magic, version, count, kd, vd), (b"MRLKV001", 1, 4, 3, 2))
        self.assertEqual(digest.hex(), hashlib.sha256(raw[HEADER.size:]).hexdigest())
        self.assertEqual(metadata["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(metadata["payload_sha256"], digest.hex())
        self.assertEqual(metadata["payload_bytes"], 4 * 5 * 8)
        self.assertEqual(metadata["file_bytes"], HEADER.size + 4 * 5 * 8)

    def test_writer_refuses_overwrite_and_leaves_original_bytes(self):
        path, _ = self.store()
        original = path.read_bytes()
        with self.assertRaises((ValueError, OSError)):
            write_kv_store(path, [[1.0]], [[2.0]])
        self.assertEqual(path.read_bytes(), original)

    def test_invalid_row_dimensions_numbers_and_lengths_are_rejected(self):
        bad_stores = [([], []), ([[1.0]], []), ([[1.0]], [[1.0], [2.0]]),
                      ([[]], [[1.0]]), ([[1.0]], [[]]),
                      ([[1.0], [1.0, 2.0]], [[1.0], [2.0]]),
                      ([[1.0]], [[float("nan")]]),
                      ([[float("inf")]], [[1.0]]),
                      ([[True]], [[1.0]]), ([["1"]], [[1.0]])]
        for i, (keys, values) in enumerate(bad_stores):
            with self.subTest(case=i):
                path = self.directory / f"invalid-{i}.kv"
                with self.assertRaises(ValueError):
                    write_kv_store(path, keys, values)
                self.assertFalse(path.exists(), "failed writes must not leave a valid-looking store")
        for keys, values in bad_stores:
            with self.subTest(resident=(keys, values)), self.assertRaises(ValueError):
                parallax_attention_resident([1.0], [0.5], keys, values)

    def test_invalid_query_projector_and_scale_are_rejected_by_both_paths(self):
        path, metadata = self.store()
        cases = [([], self.r, None), ([1.0], self.r, None),
                 (self.q, [1.0], None), ([True, 0.0, 0.0], self.r, None),
                 ([float("nan"), 0.0, 0.0], self.r, None),
                 (self.q, [float("inf"), 0.0, 0.0], None),
                 (self.q, self.r, float("nan")), (self.q, self.r, float("inf")),
                 (self.q, self.r, True)]
        for q, r, scale in cases:
            with self.subTest(q=q, r=r, scale=scale):
                with self.assertRaises(ValueError):
                    parallax_attention_resident(q, r, self.keys, self.values, qk_scale=scale)
                with self.assertRaises(ValueError):
                    parallax_attention_file(path, q, r, expected_sha256=metadata["sha256"],
                                            qk_scale=scale)

    def test_float_overflow_is_rejected_instead_of_returning_nonfinite_output(self):
        # A singleton's common offset cancels and need not overflow. Distinct
        # keys below force an unrepresentable relative dot product instead.
        for actual in self.evaluate_both([1e308], [1e308], [[1e308]], [[1.0]],
                                        name="large-common-offset.kv"):
            self.assertVectorClose(actual, [1.0])
        keys, values = [[0.0], [1e308]], [[1.0], [2.0]]
        path, metadata = self.store(keys, values)
        for q, r in (([1e308], [0.0]), ([0.0], [1e308])):
            with self.subTest(q=q, r=r):
                with self.assertRaises(ValueError):
                    parallax_attention_resident(q, r, keys, values)
                with self.assertRaises(ValueError):
                    parallax_attention_file(path, q, r, expected_sha256=metadata["sha256"])

    def test_block_and_buffer_limits_reject_invalid_requests(self):
        path, metadata = self.store()
        for options in ({"block_records": 0}, {"block_records": -1},
                        {"block_records": True}, {"block_records": 1.5},
                        {"max_buffer_bytes": 0}, {"max_buffer_bytes": True},
                        {"max_buffer_bytes": 8 * 1024 * 1024 + 1},
                        {"block_records": 2, "max_buffer_bytes": 16}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                parallax_attention_file(path, self.q, self.r,
                                        expected_sha256=metadata["sha256"], **options)

    def test_header_also_counts_against_configured_read_buffer(self):
        path, metadata = self.store([[1.0]], [[2.0]])
        with self.assertRaises(ValueError):
            parallax_attention_file(path, [1.0], [0.5], expected_sha256=metadata["sha256"],
                                    block_records=1, max_buffer_bytes=16)
        result = parallax_attention_file(
            path, [1.0], [0.5], expected_sha256=metadata["sha256"],
            block_records=1, max_buffer_bytes=HEADER.size)
        self.assertVectorClose(result["output"], [2.0])
        self.assertEqual(result["io"]["peak_read_buffer_bytes"], HEADER.size)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX special-file tests")
    def test_reader_refuses_symlinks_directories_and_fifos(self):
        path, metadata = self.store()
        symlink = self.directory / "linked.kv"
        symlink.symlink_to(path)
        fifo = self.directory / "fifo.kv"
        os.mkfifo(fifo)
        for unsafe in (symlink, self.directory, fifo):
            with self.subTest(path=unsafe):
                with self.assertRaises(ValueError):
                    parallax_attention_file(unsafe, self.q, self.r,
                                            expected_sha256=metadata["sha256"])
                with self.assertRaises(ValueError):
                    load_kv_store(unsafe, expected_sha256=metadata["sha256"])

    def _mutate_during_attention(self, *, block_records, expect_signature_failure=False):
        path, metadata = self.store()
        original_scores = parallax_module._scores
        mutated = False

        def score_and_mutate(*args):
            nonlocal mutated
            if not mutated:
                mutated = True
                before = path.stat()
                path.chmod(0o600)
                with path.open("r+b") as stream:
                    stream.seek(-1, os.SEEK_END)
                    byte = stream.read(1)
                    stream.seek(-1, os.SEEK_END)
                    stream.write(bytes([byte[0] ^ 1]))
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
            return original_scores(*args)

        with mock.patch.object(parallax_module, "_scores", side_effect=score_and_mutate):
            with self.assertRaises(ValueError) as caught:
                parallax_attention_file(path, self.q, self.r,
                                        expected_sha256=metadata["sha256"],
                                        block_records=block_records)
        self.assertTrue(mutated)
        if expect_signature_failure:
            self.assertIn("changed while", str(caught.exception))

    def test_mutation_after_first_record_before_later_reads_is_rejected(self):
        self._mutate_during_attention(block_records=1)

    def test_mutation_after_entire_payload_read_is_rejected_before_result(self):
        # The reader has already hashed the entire block before yielding its
        # first record. A later mutation must still fail the final FD check.
        self._mutate_during_attention(block_records=len(self.keys), expect_signature_failure=True)

    def test_whole_file_expected_digest_is_mandatory_and_verified(self):
        path, metadata = self.store()
        with self.assertRaises(TypeError):
            parallax_attention_file(path, self.q, self.r)
        for digest in ("", "invalid", "0" * 64, metadata["sha256"][:-1]):
            with self.subTest(digest=digest):
                with self.assertRaises(ValueError):
                    parallax_attention_file(path, self.q, self.r, expected_sha256=digest)
                with self.assertRaises(ValueError):
                    load_kv_store(path, expected_sha256=digest)

    def assertCorruptRejected(self, raw, name):
        path = self.directory / name
        path.write_bytes(raw)
        # Matching the outer hash cannot excuse malformed content or bad payload hash.
        digest = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):
            parallax_attention_file(path, self.q, self.r, expected_sha256=digest)
        with self.assertRaises(ValueError):
            load_kv_store(path, expected_sha256=digest)

    def test_corrupt_payload_rejected_even_with_matching_whole_file_digest(self):
        path, _ = self.store()
        raw = bytearray(path.read_bytes())
        raw[-1] ^= 1
        self.assertCorruptRejected(bytes(raw), "corrupt-payload.kv")

    def test_truncated_extended_and_invalid_headers_rejected(self):
        path, _ = self.store()
        raw = path.read_bytes()
        for i, changed in enumerate((raw[:20], raw[:-1], raw + b"x",
                                     b"NOTKV001" + raw[8:])):
            self.assertCorruptRejected(changed, f"bad-file-{i}.kv")
        fields = list(HEADER.unpack(raw[:HEADER.size]))
        for i, (index, value) in enumerate(((1, 2), (2, 0), (2, 65537),
                                          (3, 0), (3, 129), (4, 0), (4, 129))):
            changed = fields.copy()
            changed[index] = value
            self.assertCorruptRejected(HEADER.pack(*changed) + raw[HEADER.size:],
                                       f"bad-header-{i}.kv")

    def test_self_consistent_hashes_do_not_allow_nonfinite_payload(self):
        for i, number in enumerate((float("nan"), float("inf"), -float("inf"))):
            payload = struct.pack("<5d", number, 0.5, -1.0, 0.2, -0.6)
            header = HEADER.pack(b"MRLKV001", 1, 1, 3, 2, hashlib.sha256(payload).digest())
            self.assertCorruptRejected(header + payload, f"nonfinite-{i}.kv")


class ParallaxBenchmarkTests(unittest.TestCase):
    def load_benchmark(self):
        spec = importlib.util.spec_from_file_location(
            "ssd_parallax_benchmark", ROOT / "scripts" / "merlin_ssd_parallax_benchmark.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_small_benchmark_has_matched_outputs_and_limited_claims(self):
        module = self.load_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            report = module.run_benchmark(Path(directory), sizes=(16,), dimension=3,
                                          repeats=2, block_sizes=(1, 8))
        self.assertEqual(report["schema"], "merlin-ssd-parallax-attention-benchmark/1")
        self.assertTrue(report["real_parallax_formula_executed"])
        self.assertTrue(report["resident_fixture_remains_live_during_trials"])
        self.assertTrue(report["resident_fixture_remains_live_during_allocation_measurements"])
        self.assertTrue(report["source_files_unchanged_during_measurement"])
        self.assertEqual(len(report["source_files_sha256"]), 4)
        self.assertLessEqual(report["measurement_started_utc"], report["measurement_finished_utc"])
        for field in ("trained_model_evaluated", "gpu_used", "physical_ssd_verified",
                      "cold_storage_benchmark", "process_rss_measured", "production_qualified"):
            self.assertFalse(report[field])
        self.assertEqual(len(report["observations"]), 1)
        row = report["observations"][0]
        self.assertTrue(row["numerical_agreement"])
        self.assertEqual(len(row["input_sha256"]), 64)
        self.assertGreater(row["allocations"]["resident_load_and_compute_peak_bytes"], 0)
        self.assertGreaterEqual(row["preparation"]["fixture_generation_seconds"], 0)
        self.assertEqual(set(row["variants"]), {
            "hot_resident", "resident_load_and_compute", "file_block_1", "file_block_8"})
        for variant in row["variants"].values():
            self.assertEqual(len(variant["trial_seconds"]), 2)
            self.assertLessEqual(variant["min_seconds"], variant["median_seconds"])
            self.assertLessEqual(variant["median_seconds"], variant["max_seconds"])

    def test_concurrent_source_change_invalidates_benchmark_result(self):
        module = self.load_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(module, "_source_hashes", side_effect=[{"code": "before"}, {"code": "after"}]):
                with self.assertRaisesRegex(RuntimeError, "source files or Git identity changed"):
                    module.run_benchmark(Path(directory), sizes=(4,), dimension=2,
                                         repeats=1, block_sizes=(1,))

    def test_environment_label_does_not_bind_uncommitted_source(self):
        module = self.load_benchmark()
        results = [mock.Mock(stdout="a" * 40 + "\n", returncode=0),
                   mock.Mock(stdout="source.py\n", returncode=0),
                   mock.Mock(stdout=" M source.py\n", returncode=0)]
        with mock.patch.dict(os.environ, {"MERLIN_EXPECTED_SHA": "a" * 40}):
            with mock.patch.object(module.subprocess, "run", side_effect=results):
                identity = module._source_identity()
        self.assertEqual(identity["source_commit"], "unbound")
        self.assertFalse(identity["source_tree_clean"])
        self.assertTrue(identity["expected_source_matches_head"])

    def test_report_creation_does_not_replace_earlier_evidence(self):
        module = self.load_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            module.write_report_exclusive(path, {"result": "first"})
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                module.write_report_exclusive(path, {"result": "second"})
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
