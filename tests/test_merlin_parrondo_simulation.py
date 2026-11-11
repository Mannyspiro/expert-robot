import unittest

from merlin.learning_core import LessonSession
from merlin.parrondo_lesson import make_canonical_games
from merlin.parrondo_simulation import (
    PARRONDO_LESSON_SPEC,
    canonical_simulations,
    simulate_game,
    summarize_trials,
)


class ParrondoSimulationTests(unittest.TestCase):
    def test_lesson_is_compatible_with_persistent_lesson_session(self):
        session = LessonSession(PARRONDO_LESSON_SPEC)
        self.assertEqual(session.current_stage.stage_id, "notice")
        with self.assertRaisesRegex(ValueError, "expected current stage"):
            session.complete_current_stage("probabilities")
        while session.current_stage is not None:
            session.complete_current_stage(session.current_stage.stage_id)
        self.assertTrue(session.is_complete)

    def test_simulation_is_reproducible(self):
        game = make_canonical_games()[2]
        first = simulate_game(game, turns=500, seed="same-seed")
        second = simulate_game(game, turns=500, seed="same-seed")
        self.assertEqual(first, second)

    def test_simulation_records_every_state_and_conserves_turns(self):
        game = make_canonical_games()[0]
        result = simulate_game(game, turns=25, seed=7, start_total=4)
        self.assertEqual(len(result.trajectory), 26)
        self.assertEqual(result.trajectory[0], 4)
        self.assertEqual(result.wins + result.losses, 25)
        self.assertEqual(result.final_total, 4 + result.wins - result.losses)
        self.assertAlmostEqual(result.empirical_gain_per_turn, (result.wins-result.losses)/25)

    def test_canonical_comparison_uses_equal_budgets(self):
        a, b, mixed = canonical_simulations(turns=300, seed=11)
        self.assertEqual((a.turns, b.turns, mixed.turns), (300, 300, 300))
        self.assertEqual((a.seed, b.seed, mixed.seed), (11, 11, 11))

    def test_trial_summary_is_reproducible_and_reports_uncertainty(self):
        game = make_canonical_games()[2]
        first = summarize_trials(game, trials=40, turns_per_trial=200, seed="study-1")
        second = summarize_trials(game, trials=40, turns_per_trial=200, seed="study-1")
        self.assertEqual(first, second)
        self.assertGreaterEqual(first.sample_standard_deviation, 0)
        self.assertGreaterEqual(first.standard_error, 0)
        self.assertLess(first.approximate_95_percent_interval[0], first.approximate_95_percent_interval[1])

    def test_invalid_simulation_inputs_fail_closed(self):
        game = make_canonical_games()[0]
        for turns in (0, -1, 1.5, True):
            with self.subTest(turns=turns), self.assertRaises(ValueError):
                simulate_game(game, turns=turns, seed=1)
        with self.assertRaises(ValueError):
            summarize_trials(game, trials=1, turns_per_trial=10, seed=1)


if __name__ == "__main__":
    unittest.main()
