import unittest
from merlin.cpu_fabric.strategy_eval import run_paired_trials


class StrategyEvalTests(unittest.TestCase):
    def test_randomized_paired_development_and_heldout(self):
        orders = []
        def fast(seed):
            return {"quality": .99, "latency_ms": 10 + seed,
                    "peak_rss_bytes": 100, "resident_bytes": 80}
        def slower(seed):
            return {"quality": 1.0, "latency_ms": 20 + seed,
                    "peak_rss_bytes": 100, "resident_bytes": 80}
        result = run_paired_trials(
            {"fast": fast, "slower": slower}, (1, 2, 3), .95,
            held_out_seeds=(11, 12, 13), order_seed=42,
        )
        dev = result["development"]
        self.assertEqual(dev["seed_set"], [1, 2, 3])
        self.assertEqual(result["held_out"]["seed_set"], [11, 12, 13])
        self.assertEqual(dev["paired_differences"]["slower"]["latency_ms"]["mean_difference_vs_baseline"], 10)
        self.assertEqual(dev["paired_differences"]["slower"]["latency_ms"]["n_pairs"], 3)
        self.assertTrue(all(row["order"][0] in ("fast", "slower") for row in dev["randomized_order"]))
        self.assertFalse(result["promotion_authorized"])
        self.assertEqual(result["protocol"]["baseline"], "fast")

    def test_nonfinite_metrics_rejected(self):
        with self.assertRaises(ValueError):
            run_paired_trials({"nan": lambda seed: {
                "quality": .9, "latency_ms": float("nan"),
                "peak_rss_bytes": 1, "resident_bytes": 1
            }}, (1,), .8)

    def test_duplicate_seeds_rejected(self):
        with self.assertRaises(ValueError):
            run_paired_trials({"x": lambda seed: {}}, (1, 1), .8)

    def test_overlapping_development_and_heldout_rejected(self):
        with self.assertRaises(ValueError):
            run_paired_trials({"x": lambda seed: {}}, (1, 2), .8, held_out_seeds=(2, 3))

    def test_empty_strategy_set_rejected(self):
        with self.assertRaises(ValueError):
            run_paired_trials({}, (1,), .8)

    def test_empty_seed_set_rejected(self):
        with self.assertRaises(ValueError):
            run_paired_trials({"x": lambda seed: {}}, (), .9)


if __name__ == "__main__":
    unittest.main()
