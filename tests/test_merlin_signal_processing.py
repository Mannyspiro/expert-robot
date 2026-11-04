"""Regression tests for RWEA-041–050 synthetic signal-processing checks."""
import unittest

from merlin.equation_atlas.experiments.signal_processing import run_signal_checks


class SignalProcessingChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_signal_checks()

    def test_dft_round_trip_and_parseval(self):
        dft = self.result["dft"]
        self.assertLess(dft["round_trip_max_abs_error"], 1e-12)
        self.assertLess(dft["parseval_absolute_error"], 1e-12)

    def test_convolution_theorem_with_linear_zero_padding(self):
        self.assertLess(
            self.result["convolution"]["linear_convolution_max_abs_error"], 1e-12
        )

    def test_sampling_aliasing_example(self):
        alias = self.result["sampling_aliasing"]
        self.assertAlmostEqual(alias["observed_fft_peak_hz"], 3.0, places=12)
        self.assertAlmostEqual(alias["expected_alias_frequency_hz"], 3.0)

    def test_entropy_and_mutual_information_identities(self):
        info = self.result["information_theory"]
        self.assertAlmostEqual(info["fair_binary_entropy_bits"], 1.0)
        self.assertAlmostEqual(info["deterministic_entropy_bits"], 0.0)
        self.assertAlmostEqual(info["independent_mutual_information_bits"], 0.0)
        self.assertAlmostEqual(info["perfectly_correlated_mutual_information_bits"], 1.0)

    def test_quantization_variance_model(self):
        q = self.result["quantization"]
        self.assertLess(q["relative_variance_error"], 0.02)


if __name__ == "__main__":
    unittest.main()
