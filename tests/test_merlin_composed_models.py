"""Tests for composed Merlin reference models."""
import unittest
import numpy as np

from merlin.equation_atlas.models import (
    simulate_lotka_volterra,
    simulate_reaction_diffusion_1d,
    simulate_sir,
)
from merlin.equation_atlas.simulation import SimulationConfig


class ComposedModelTests(unittest.TestCase):
    def test_reaction_diffusion_composes_reaction_and_diffusion(self):
        initial = np.full(16, 0.1)
        def logistic(u, _t):
            return 0.2 * u * (1.0 - u)
        result = simulate_reaction_diffusion_1d(
            initial, logistic, diffusivity=0.05, dx=1.0,
            config=SimulationConfig(dt=0.1, steps=20),
            parameters={"growth_rate": 0.2, "capacity": 1.0},
        )
        self.assertEqual(result.metadata["composition"], ["local_reaction", "periodic_diffusion"])
        self.assertLessEqual(result.metadata["diffusion_cfl_number"], 0.5)
        self.assertTrue(np.all(np.asarray(result.states) >= 0))

    def test_reaction_diffusion_rejects_unstable_diffusion_step(self):
        with self.assertRaises(ValueError):
            simulate_reaction_diffusion_1d(
                [1.0, 0.0], lambda u, t: np.zeros_like(u), 1.0, 1.0,
                SimulationConfig(dt=0.6, steps=1), parameters={},
            )

    def test_sir_conserves_closed_population(self):
        result = simulate_sir(
            [999.0, 1.0, 0.0], transmission=0.3, recovery=0.1,
            population=1000.0, config=SimulationConfig(dt=0.1, steps=100),
        )
        self.assertLess(result.metadata["invariant_max_abs_population_residual"], 1e-9)
        self.assertTrue(np.all(np.asarray(result.states) >= 0))

    def test_sir_rejects_initial_population_mismatch(self):
        with self.assertRaises(ValueError):
            simulate_sir([9.0, 1.0, 0.0], 0.3, 0.1, 11.0,
                         SimulationConfig(0.1, 1))

    def test_lotka_volterra_returns_reproducible_model_trace(self):
        args = dict(initial_state=[40.0, 9.0], alpha=1.0, beta=0.02,
                    delta=0.01, gamma=0.5, config=SimulationConfig(0.001, 100))
        a, b = simulate_lotka_volterra(**args), simulate_lotka_volterra(**args)
        self.assertEqual(a.states, b.states)
        self.assertEqual(a.metadata["model_id"], "lotka-volterra-classical")


if __name__ == "__main__":
    unittest.main()
