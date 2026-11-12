import unittest
from merlin.simulation_lab import SCENARIOS, compare_scenarios, replay_actions, run_scenario

class SimulationLabTests(unittest.TestCase):
    def test_scenario_is_reproducible(self):
        actions = SCENARIOS["uncertainty_recovery"]
        self.assertEqual(run_scenario(actions)["final"], run_scenario(actions)["final"])

    def test_comparison_is_labeled_simulation_only(self):
        result = compare_scenarios(SCENARIOS, seeds=(3, 5))
        self.assertEqual(result["paired_seeds"], [3, 5])
        self.assertFalse(result["promotion_authorized"])
        self.assertFalse(result["causal_claims_supported"])

    def test_replay_matches_direct_run(self):
        actions = ("advance", "verify", "compress")
        self.assertEqual(replay_actions(actions)["final"], run_scenario(actions)["final"])

if __name__ == "__main__":
    unittest.main()
