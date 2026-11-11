import unittest

from merlin.parrondo import (
    Parameters, expected_gain_per_turn, play_trial, stationary_distribution, summarize,
)


class ParrondoTests(unittest.TestCase):
    def test_canonical_parameters_make_each_game_losing_but_mixture_winning(self):
        params = Parameters(epsilon=0.005, mix_probability=0.5)
        self.assertLess(expected_gain_per_turn("A", params), 0)
        self.assertLess(expected_gain_per_turn("B", params), 0)
        self.assertGreater(expected_gain_per_turn("mixed", params), 0)

    def test_seed_reproduces_trial(self):
        first = play_trial("mixed", turns=500, seed=812)
        second = play_trial("mixed", turns=500, seed=812)
        self.assertEqual(first, second)

    def test_summary_reports_sample_metadata(self):
        rows = [play_trial("A", turns=100, seed=seed) for seed in range(20)]
        result = summarize(rows)
        self.assertEqual(result.trials, 20)
        self.assertEqual(result.turns_per_trial, 100)
        self.assertGreaterEqual(result.fraction_profitable, 0)
        self.assertLessEqual(result.fraction_profitable, 1)

    def test_stationary_distribution_is_normalized(self):
        distribution = stationary_distribution("mixed")
        self.assertAlmostEqual(sum(distribution), 1.0, places=12)
        self.assertTrue(all(value >= 0 for value in distribution))

    def test_invalid_parameters_rejected(self):
        with self.assertRaises(ValueError):
            play_trial("mixed", parameters=Parameters(epsilon=0.2))


if __name__ == "__main__":
    unittest.main()
