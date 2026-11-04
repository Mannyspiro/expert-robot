"""Regression checks for RWEA-061–070 toy systems."""
import unittest

from merlin.equation_atlas.experiments.biological_complexity import run_biological_complexity_checks


class BiologicalComplexityChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_biological_complexity_checks()

    def test_periodic_diffusion_conserves_mass(self):
        self.assertLess(self.result["reaction_diffusion"]["periodic_laplacian_mass_residual"], 1e-12)

    def test_logistic_population_is_bounded(self):
        x = self.result["logistic"]
        self.assertGreater(x["population_after_steps"], 0.0)
        self.assertLess(x["population_after_steps"], x["carrying_capacity"])

    def test_replicator_preserves_simplex_invariant(self):
        x = self.result["replicator"]
        self.assertAlmostEqual(x["frequency_sum"], 1.0, places=12)
        self.assertGreaterEqual(x["minimum_frequency"], 0.0)

    def test_cellular_automaton_rule_is_reproducible(self):
        ca = self.result["cellular_automaton"]
        self.assertEqual(ca["next"], [0, 0, 0, 1, 1, 1, 0, 0, 0])

    def test_kuramoto_coupling_increases_coherence(self):
        k = self.result["kuramoto"]
        self.assertLess(k["final_phase_spread"], k["initial_phase_spread"])
        self.assertGreater(k["order_parameter"], 0.99)

    def test_mutual_information_toy_distributions(self):
        m = self.result["mutual_information"]
        self.assertAlmostEqual(m["independent_bits"], 0.0, places=12)
        self.assertAlmostEqual(m["paired_bits"], 1.0, places=12)

    def test_graph_component_size(self):
        self.assertEqual(self.result["percolation_graph"]["largest_component_size"], 3)


if __name__ == "__main__":
    unittest.main()
