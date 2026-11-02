import unittest

from python.merlin.biology import (
    fit_michaelis_menten, hill_activation, michaelis_menten, simulate_enzyme_reaction
)


class BiochemistryTests(unittest.TestCase):
    def test_michaelis_menten_known_value(self):
        self.assertAlmostEqual(michaelis_menten(1.0, 2.0, 1.0), 1.0)

    def test_hill_activation_bounds(self):
        self.assertEqual(hill_activation(0.0, 1.0, 2.0), 0.0)
        self.assertAlmostEqual(hill_activation(1.0, 1.0, 2.0), 0.5)
        self.assertGreater(hill_activation(10.0, 1.0, 2.0), 0.99)

    def test_hill_response_handles_tiny_concentration(self):
        self.assertGreaterEqual(hill_activation(1e-200, 1.0, 4.0), 0.0)

    def test_simulation_step_budget_is_enforced(self):
        with self.assertRaisesRegex(ValueError, "step count"):
            simulate_enzyme_reaction(1.0, 1.0, 1.0, 10.0, 1e-8)

    def test_reaction_conserves_substrate_plus_product(self):
        result = simulate_enzyme_reaction(2.0, 0.8, 0.4, 4.0, 0.02)
        self.assertLess(result["mass_balance_error"], 1e-12)
        self.assertEqual(result["substrate"][0], 2.0)
        self.assertGreater(result["product"][-1], 0.0)
        self.assertLess(result["substrate"][-1], 2.0)

    def test_invalid_kinetic_parameters_rejected(self):
        with self.assertRaises(ValueError):
            michaelis_menten(1.0, 1.0, 0.0)

    def test_evolutionary_fit_is_seed_reproducible(self):
        observations = [(s, michaelis_menten(s, 2.4, 0.7)) for s in (0.1,0.2,0.4,0.8,1.5,3.0,6.0)]
        a = fit_michaelis_menten(observations, vmax_bounds=(1.0,4.0), km_bounds=(0.1,2.0), seed=17)
        b = fit_michaelis_menten(observations, vmax_bounds=(1.0,4.0), km_bounds=(0.1,2.0), seed=17)
        self.assertEqual(a, b)
        self.assertLess(a["rmse"], 0.03)


if __name__ == "__main__":
    unittest.main()
