import itertools
import tempfile
import unittest
from pathlib import Path
from runpy import run_path

from dot_ai_os.cross_agent_review import ARMS, CrossAgentReviewer
from dot_ai_os.training_parents import choose_parents, plan_training_parents
from merlin.project_registry import MerlinRegistry


class TrainingParentsTest(unittest.TestCase):
    def test_duplicate_and_complementary(self):
        rows = {"baseline": {"q1", "q2"}, "coder_a": {"q1", "q2"}, "coder_b": {"q3"}}
        self.assertEqual(choose_parents(rows), ["baseline", "coder_b"])
        self.assertEqual(choose_parents(rows, limit=1), ["baseline"])
        self.assertEqual(choose_parents(dict.fromkeys(ARMS, set())), ["baseline"])
        with self.assertRaises(ValueError):
            choose_parents(rows, limit=True)

    def test_each_small_training_matrix_reaches_best_available_coverage(self):
        masks = [set(itertools.compress(range(3), bits))
                 for bits in itertools.product((0, 1), repeat=3)]
        for rows in itertools.product(masks, repeat=3):
            grouped = dict(zip(ARMS, rows))
            for budget in (1, 2):
                selected = choose_parents(grouped, limit=budget)
                union = set().union(*(grouped[arm] for arm in selected))
                best = max(len(set.union(*batch))
                           for batch in itertools.combinations(rows, budget))
                self.assertEqual(len(union), best)
                self.assertLessEqual(len(selected), budget)

    def test_verified_host_trial_exports_training_inputs_only(self):
        root = Path(__file__).resolve().parents[1]
        run = run_path(str(root / "scripts/measure_dot_review.py"))["run"]
        with tempfile.TemporaryDirectory() as directory:
            measured = run(directory)
            registry = MerlinRegistry(directory)
            reviewer = CrossAgentReviewer(registry, project_id=measured["protocol_ref"]["project_id"])
            plan = plan_training_parents(reviewer, measured["protocol_ref"])
            self.assertEqual(plan["train_cases_covered"], 2)
            self.assertEqual([parent["arm"] for parent in plan["parents"]], ["coder_a"])
            self.assertEqual(plan["uncovered_train_ids"], [])
            self.assertNotIn("holdout", str(plan))
            self.assertNotIn("observation_ref", str(plan))
            self.assertFalse(plan["promotion_authority"])
            self.assertEqual(plan, plan_training_parents(reviewer, measured["protocol_ref"]))
