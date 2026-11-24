"""Matched-input math reference timing controls; no model claims."""
from pathlib import Path
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("common_reference",ROOT/"scripts"/"merlin_common_input_reference_benchmark.py")
assert SPEC and SPEC.loader
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class CommonReferenceTests(unittest.TestCase):
    def test_common_inputs_and_non_equivalence(self):
        report=module.compare()
        self.assertEqual(report["sequence_lengths"],[64,128,256])
        self.assertEqual(report["repeats"],5)
        self.assertTrue(report["same_input_samples"])
        self.assertFalse(report["equivalent_prediction_tasks"])
        self.assertFalse(report["model_inference_executed"])
        self.assertFalse(report["model_quality_comparable"])
        self.assertFalse(report["production_qualified"])
        for row in report["observations"]:
            self.assertEqual(set(row["variants"]),{
                "scalar_recurrence","complex_state_reference","local_linear_reference"})
            self.assertEqual(len(row["input_sha256"]),64)
            for item in row["variants"].values():
                self.assertEqual(item["output_length"],row["n"])
                self.assertEqual(item["trials"],5)
                self.assertLessEqual(item["min_seconds"],item["median_seconds"])
                self.assertLessEqual(item["median_seconds"],item["max_seconds"])


if __name__=="__main__":
    unittest.main()
