import unittest
from merlin.cpu_fabric.strategy_eval import run_paired_trials


class StrategyEvalTests(unittest.TestCase):
    def test_paired_seeds_and_pareto_frontier(self):
        def fast(seed):
            return {"quality": .99, "latency_ms": 10 + seed,
                    "peak_rss_bytes": 100, "resident_bytes": 80}
        def slower(seed):
            return {"quality": 1.0, "latency_ms": 20 + seed,
                    "peak_rss_bytes": 100, "resident_bytes": 80}
        def poor(seed):
            return {"quality": .80, "latency_ms": 2,
                    "peak_rss_bytes": 50, "resident_bytes": 40}
        result = run_paired_trials(
            {"fast": fast, "slower": slower, "poor": poor},
            seeds=(1, 2, 3), quality_floor=.95,
        )
        self.assertEqual(result["seed_set"], [1, 2, 3])
        self.assertEqual(result["pareto_frontier"], ["fast", "slower"])
        self.assertFalse(result["promotion_authorized"])

    def test_nonfinite_metrics_rejected(self):
        with self.assertRaises(ValueError):
            run_paired_trials({"nan": lambda seed: {
                "quality": .9, "latency_ms": float("nan"),
                "peak_rss_bytes": 1, "resident_bytes": 1
            }}, (1,), .8)

    def test_duplicate_seeds_rejected(self):
        with self.assertRaises(ValueError):
            run_paired_trials({"x": lambda seed: {}}, (1, 1), .8)

    def test_empty_strategy_set_rejected(self):
        with self.assertRaises(ValueError):
            run_paired_trials({}, (1,), .8)

    def test_empty_seed_set_rejected(self):
        with self.assertRaises(ValueError):
            run_paired_trials({"x": lambda seed: {}}, (), .9)


if __name__ == "__main__":
    unittest.main()
