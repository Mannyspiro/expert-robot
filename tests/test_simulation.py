import unittest

from merlin.simulation import MerlinSimulation


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.sim = MerlinSimulation()

    def test_initial_state_is_explicitly_simulated(self):
        state = self.sim.snapshot()
        self.assertTrue(state["simulation_only"])
        self.assertEqual(state["environment"], "deterministic_simulation")
        self.assertEqual(state["state"]["tick"], 0)

    def test_advance_updates_metrics_and_event_stream(self):
        result = self.sim.step("advance")
        self.assertEqual(result["state"]["tick"], 1)
        self.assertGreater(result["state"]["progress"], 0)
        self.assertTrue(result["state"]["metrics"])
        self.assertEqual(result["state"]["events"][-1]["kind"], "task.progress")

    def test_uncertainty_changes_recommended_action(self):
        result = self.sim.step("inject_uncertainty")
        self.assertGreaterEqual(result["state"]["uncertainty"], 0.65)
        self.assertEqual(result["decision_preview"]["action"], "decompose")

    def test_pause_blocks_advancement_until_resume(self):
        self.sim.step("pause")
        with self.assertRaises(ValueError):
            self.sim.step("advance")
        result = self.sim.step("resume")
        self.assertEqual(result["state"]["mode"], "running")

    def test_reset_returns_to_initial_conditions(self):
        self.sim.step("advance")
        result = self.sim.step("reset")
        self.assertEqual(result["state"]["tick"], 0)
        self.assertEqual(result["state"]["progress"], 0.0)

    def test_unknown_action_rejected(self):
        with self.assertRaises(ValueError):
            self.sim.step("execute_shell")


if __name__ == "__main__":
    unittest.main()
