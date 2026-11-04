import tempfile
import unittest
from pathlib import Path

from merlin.observatory_benchmarks import (\n    run_core_benchmarks, run_negative_controls, run_repeated_benchmarks, write_benchmark_receipt,\n)


COMMIT = "a" * 40


class ObservatoryBenchmarkTests(unittest.TestCase):
    def test_all_four_domains_emit_passing_reproducible_receipts(self):
        first = run_core_benchmarks(COMMIT)
        second = run_core_benchmarks(COMMIT)
        self.assertTrue(first["all_passed"], first["domains"])
        self.assertEqual(first, second)
        self.assertEqual(
            set(first["domains"]),
            {"geometry", "xmg", "equation_atlas", "cad"},
        )
        self.assertEqual(len(first["receipt_sha256"]), 64)
        self.assertEqual(len(first["source_sha256"]), 10)

    def test_controlled_negative_cases_are_detected(self):\n        controls = run_negative_controls()\n        self.assertTrue(controls["all_detected"], controls)\n\n    def test_repeated_runs_are_stable(self):\n        result = run_repeated_benchmarks(COMMIT, repeats=3)\n        self.assertTrue(result["all_passed"], result)\n        self.assertEqual(result["repeats"], 3)\n        self.assertTrue(all(result["domain_stable"].values()))\n\n    def test_repeat_count_is_bounded(self):\n        with self.assertRaises(ValueError):\n            run_repeated_benchmarks(COMMIT, repeats=1)\n\n    def test_receipt_is_pinned_to_source_commit(self):
        with self.assertRaises(ValueError):
            run_core_benchmarks("not-a-commit")

    def test_receipt_writer_emits_canonical_json(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifacts" / "merlin-observatory.json"
            receipt = write_benchmark_receipt(path, COMMIT)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded, receipt)
            self.assertTrue(receipt["all_passed"])


if __name__ == "__main__":
    unittest.main()
