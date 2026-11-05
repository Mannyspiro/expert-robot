import unittest

from merlin.research_optimizer import (
    ResearchCandidate, ResearchMetrics, ResearchWeights,
    pareto_front, rank_research_candidates,
)


def metrics(**overrides):
    values = dict(
        information_gain=1, verified_progress=1,
        dependency_unlock_value=1, reproducibility=1,
        uncertainty=1, compute_cost=1, wall_time=1,
        verification_cost=1,
    )
    values.update(overrides)
    return ResearchMetrics(**values)


class ResearchOptimizerTests(unittest.TestCase):
    def test_hard_constraints_exclude_candidate_before_scoring(self):
        candidates = [
            ResearchCandidate("allowed", metrics(), {"approval": True, "budget": True}),
            ResearchCandidate("blocked", metrics(information_gain=100),
                              {"approval": False, "budget": True}),
        ]
        result = rank_research_candidates(candidates)
        self.assertEqual([item.task_id for item in result], ["allowed"])

    def test_pareto_front_preserves_tradeoffs(self):
        a = ResearchCandidate("high-info", metrics(information_gain=5, compute_cost=5), {"lease": True})
        b = ResearchCandidate("cheap", metrics(information_gain=2, compute_cost=1), {"lease": True})
        c = ResearchCandidate("dominated", metrics(information_gain=1, compute_cost=6), {"lease": True})
        front = pareto_front([a, b, c])
        self.assertEqual(front, {"high-info", "cheap"})

    def test_rank_exposes_components_and_evidence(self):
        item = ResearchCandidate("proof-task", metrics(verified_progress=3),
                                 {"approved": True}, ("receipt:abc",))
        result = rank_research_candidates([item], ResearchWeights())
        self.assertEqual(result[0].evidence_refs, ("receipt:abc",))
        self.assertIn("verified_progress", result[0].components)
        self.assertTrue(result[0].pareto_optimal)

    def test_missing_or_false_constraints_fail_closed(self):
        a = ResearchCandidate("no-constraints", metrics(), {})
        b = ResearchCandidate("false-constraint", metrics(), {"runner": False})
        self.assertEqual(rank_research_candidates([a, b]), [])

    def test_invalid_metrics_and_duplicate_ids_rejected(self):
        bad = ResearchCandidate("bad", metrics(compute_cost=float("nan")), {"ok": True})
        with self.assertRaises(ValueError):
            rank_research_candidates([bad])
        a = ResearchCandidate("same", metrics(), {"ok": True})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            rank_research_candidates([a, a])


if __name__ == "__main__":
    unittest.main()
