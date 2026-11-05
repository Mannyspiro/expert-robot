import unittest

from merlin.linear_simulation import simulate_linear_ode


class LinearSimulationTests(unittest.TestCase):
    def test_rk4_integrates_scalar_exponential_decay(self):
        result = simulate_linear_ode(
            [[-1.0]], [1.0], start=0.0, stop=1.0, step=0.01,
        )
        self.assertEqual(result["engine"], "merlin-rk4-linear-ode/1")
        self.assertEqual(result["steps"], 100)
        self.assertAlmostEqual(result["samples"][-1]["state"][0], 2.718281828459045 ** -1, places=8)

    def test_rejects_dimension_mismatch_and_excessive_step_count(self):
        with self.assertRaisesRegex(ValueError, "square matrix"):
            simulate_linear_ode([[1.0, 2.0]], [0.0], stop=1.0, step=0.1)
        with self.assertRaisesRegex(ValueError, "exceeds max_steps"):
            simulate_linear_ode([[0.0]], [0.0], stop=10.0, step=0.001, max_steps=100)


if __name__ == "__main__":
    unittest.main()
