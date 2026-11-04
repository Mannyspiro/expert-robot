"""Deterministic regression checks for RWEA-051–060."""
import unittest

from merlin.equation_atlas.experiments.stochastic import run_stochastic_checks


class StochasticModelChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_stochastic_checks()

    def test_markov_stationary_distribution(self):
        self.assertLess(self.result["markov"]["stationarity_residual"], 1e-12)
        self.assertLess(self.result["markov"]["transition_row_sum_error"], 1e-12)

    def test_brownian_variance_scaling(self):
        b = self.result["brownian"]
        self.assertLess(abs(b["observed_terminal_variance"] - b["theoretical_terminal_variance"]), 0.06)

    def test_beta_binomial_posterior(self):
        b = self.result["bayesian_beta_binomial"]
        self.assertEqual(b["posterior_alpha"], 9.0)
        self.assertEqual(b["posterior_beta"], 5.0)
        self.assertAlmostEqual(b["posterior_mean"], 9.0 / 14.0)

    def test_scalar_kalman_update(self):
        k = self.result["kalman_scalar"]
        self.assertAlmostEqual(k["gain"], 2.0 / 3.0)
        self.assertAlmostEqual(k["posterior_variance"], 2.0 / 3.0)

    def test_ornstein_uhlenbeck_stationary_variance(self):
        o = self.result["ornstein_uhlenbeck"]
        self.assertAlmostEqual(o["theoretical_stationary_variance"], 1.5)

    def test_entropy_production_sign_and_equilibrium(self):
        e = self.result["entropy_production"]
        self.assertGreater(e["driven_ring_sigma_over_kb"], 0.0)
        self.assertAlmostEqual(e["equilibrium_ring_sigma_over_kb"], 0.0, places=12)


if __name__ == "__main__":
    unittest.main()
