"""Synthetic tests for the first Merlin numerical execution primitives."""
import unittest
import numpy as np

from merlin.equation_atlas.simulation import (
    SimulationConfig,
    explicit_euler,
    graph_exchange_rhs,
    periodic_diffusion_rhs,
    periodic_upwind_advection_rhs,
    run_gillespie_ssa,
)


class SimulationEngineTests(unittest.TestCase):
    def test_periodic_diffusion_conserves_sum(self):
        initial = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        result = explicit_euler(
            initial, periodic_diffusion_rhs(0.1, 1.0),
            SimulationConfig(dt=0.1, steps=20), model_id="periodic-diffusion",
            parameters={"D": 0.1, "dx": 1.0}, boundary_conditions="periodic",
        )
        for state in result.states:
            self.assertAlmostEqual(sum(state), 1.0, places=12)
        self.assertEqual(result.metadata["status"], "SYNTHETIC_NUMERICAL_RUN_NOT_EMPIRICAL_VALIDATION")
        self.assertEqual(len(result.metadata["run_sha256"]), 64)

    def test_periodic_advection_conserves_sum(self):
        initial = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        result = explicit_euler(
            initial, periodic_upwind_advection_rhs(0.5, 1.0),
            SimulationConfig(dt=0.2, steps=5), model_id="periodic-advection",
            parameters={"v": 0.5}, boundary_conditions="periodic",
        )
        self.assertTrue(all(abs(sum(s) - 1.0) < 1e-12 for s in result.states))

    def test_symmetric_graph_exchange_conserves_total(self):
        adjacency = [[0, 1, 0], [1, 0, 1], [0, 1, 0]]
        rhs = graph_exchange_rhs(adjacency, rate=0.2)
        result = explicit_euler(
            [10.0, 0.0, 0.0], rhs, SimulationConfig(dt=0.1, steps=20),
            model_id="graph-exchange", parameters={"rate": 0.2},
            boundary_conditions="closed-undirected-graph",
        )
        self.assertTrue(all(abs(sum(s) - 10.0) < 1e-12 for s in result.states))
        self.assertTrue(all(min(s) >= 0.0 for s in result.states))

    def test_explicit_euler_rejects_bad_rhs_shape(self):
        with self.assertRaises(ValueError):
            explicit_euler([1.0], lambda x, t: np.array([1.0, 2.0]),
                           SimulationConfig(0.1, 1), model_id="bad",
                           parameters={}, boundary_conditions="none")

    def test_ssa_reproducible_with_seed_and_conserves_molecules(self):
        # A <-> B with one molecule. Both channels are first-order.
        nu = [[-1, 1], [1, -1]]
        def rates(x):
            return [1.0 * x[0], 0.5 * x[1]]
        args = dict(initial_counts=[1, 0], stoichiometry=nu,
                    propensity=rates, end_time=5.0, seed=42,
                    model_id="A_to_B_to_A", parameters={"k1": 1.0, "k2": 0.5})
        a, b = run_gillespie_ssa(**args), run_gillespie_ssa(**args)
        self.assertEqual(a["states"], b["states"])
        self.assertEqual(a["times"], b["times"])
        self.assertTrue(all(sum(s) == 1 for s in a["states"]))
        self.assertEqual(len(a["run_sha256"]), 64)

    def test_ssa_rejects_negative_propensities(self):
        with self.assertRaises(ValueError):
            run_gillespie_ssa([1], [[-1]], lambda x: [-1.0], 1.0,
                              seed=1, model_id="invalid", parameters={})


if __name__ == "__main__":
    unittest.main()
