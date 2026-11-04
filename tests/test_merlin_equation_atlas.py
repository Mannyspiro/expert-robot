"""Regression tests for Merlin equation-atlas dimensional and numerical checks."""
import unittest

from merlin.equation_atlas.dimensions import core_dimension_checks
from merlin.equation_atlas.symbolic_checks import run_symbolic_checks
from merlin.equation_atlas.experiments.baseline import run

class EquationAtlasTests(unittest.TestCase):
    def test_core_dimensions_are_homogeneous(self):
        results = core_dimension_checks()
        self.assertGreaterEqual(len(results), 8)

    def test_symbolic_checks(self):
        results = run_symbolic_checks()
        self.assertIn("RWEA-001", results)
        self.assertIn("RWEA-063", results)

    def test_baseline_experiments_are_reproducible(self):
        first = run()
        second = run()
        self.assertEqual(first, second)
        self.assertTrue(first["heat_equation_ftcs"]["stable"])
        self.assertAlmostEqual(first["fourier_sampling"]["dominant_fft_bin_hz"], 5.0)
        self.assertGreaterEqual(first["logistic_rk4"]["population_at_end"], 80.0)
        self.assertLessEqual(first["logistic_rk4"]["population_at_end"], 1000.0)

if __name__ == "__main__":
    unittest.main()
