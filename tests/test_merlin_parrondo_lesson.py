import unittest
from merlin.parrondo_lesson import PARRONDO_LESSON, expected_gain, lesson_results, make_canonical_games, stationary_distribution

class ParrondoLessonTests(unittest.TestCase):
    def test_lesson_starts_concrete_and_delays_symbols(self):
        self.assertEqual(PARRONDO_LESSON[0].mode, "concrete")
        self.assertFalse(PARRONDO_LESSON[0].introduces_symbols)
        symbol_index = next(i for i, stage in enumerate(PARRONDO_LESSON) if stage.introduces_symbols)
        self.assertTrue(all(not stage.introduces_symbols for stage in PARRONDO_LESSON[:symbol_index]))
        self.assertIn("interactive", {stage.mode for stage in PARRONDO_LESSON[:symbol_index]})
    def test_two_losing_games_can_have_winning_mix(self):
        results = lesson_results(0.005)
        self.assertLess(results["A"].expected_gain_per_turn, 0)
        self.assertLess(results["B"].expected_gain_per_turn, 0)
        self.assertGreater(results["random_mix_A_B"].expected_gain_per_turn, 0)
    def test_canonical_expected_values(self):
        results = lesson_results(0.005)
        self.assertAlmostEqual(results["A"].expected_gain_per_turn, -0.01, places=10)
        self.assertAlmostEqual(results["B"].expected_gain_per_turn, -0.0086952867, places=7)
        self.assertAlmostEqual(results["random_mix_A_B"].expected_gain_per_turn, 0.0157042254, places=7)
    def test_stationary_distribution_is_normalized(self):
        _, game_b, _ = make_canonical_games()
        distribution = stationary_distribution(game_b)
        self.assertAlmostEqual(sum(distribution), 1.0, places=12)
        self.assertTrue(all(value > 0 for value in distribution))
    def test_invalid_epsilon_and_probabilities_rejected(self):
        from merlin.parrondo_lesson import Game
        for epsilon in (0, 0.05, -0.1, 1):
            with self.subTest(epsilon=epsilon), self.assertRaises(ValueError):
                make_canonical_games(epsilon)
        with self.assertRaises(ValueError):
            expected_gain(Game("bad", (0.5, 1.0, 0.5)))

if __name__ == "__main__":
    unittest.main()
