import tempfile
import unittest
from pathlib import Path

from merlin.observatory_benchmarks import run_core_benchmarks, write_benchmark_receipt


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
        self.assertEqual(len(first["source_sha256"]), 9)

    def test_receipt_is_pinned_to_source_commit(self):
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
