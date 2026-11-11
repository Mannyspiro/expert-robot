from __future__ import annotations

import unittest

from merlin.rsi import (
    CaseOutcome, EvalCase, EvaluationEvidence, SkillProcedure,
    compare_skill_evaluations, suite_digest,
)


def skill(version: int) -> SkillProcedure:
    return SkillProcedure(
        skill_id="math.error-triage", version=version,
        purpose="Diagnose a learner's algebra transformation error.",
        trigger_conditions=("learner submits an invalid equality",),
        steps=("identify the first invalid transformation", "show a counterexample", "ask for a corrected step"),
        guardrails=("do not reveal the full solution before learner retry", "do not award mastery from hints"),
        source_failure_ids=("failure-001", "failure-004"),
    )


def cases():
    return (
        EvalCase("train-1", "train", "a" * 64),
        EvalCase("held-1", "heldout", "b" * 64),
        EvalCase("held-2", "heldout", "c" * 64),
    )


def evidence(version, outcomes):
    current = skill(version)
    return EvaluationEvidence(
        skill_sha256=current.sha256,
        suite_sha256=suite_digest(cases()),
        evaluator_sha256="d" * 64,
        runner_id="github-actions-ubuntu",
        runner_revision="runner-image-2026-11",
        outcomes=tuple(outcomes),
    )


class RSIEvaluationTests(unittest.TestCase):
    def test_heldout_gain_without_regression_is_only_eligible_for_review(self):
        baseline = evidence(1, (
            CaseOutcome("train-1", False),
            CaseOutcome("held-1", True),
            CaseOutcome("held-2", False),
        ))
        candidate = evidence(2, (
            CaseOutcome("train-1", True),
            CaseOutcome("held-1", True),
            CaseOutcome("held-2", True),
        ))
        decision = compare_skill_evaluations(
            baseline_skill=skill(1), candidate_skill=skill(2), cases=cases(),
            baseline=baseline, candidate=candidate, max_resource_units=10,
        )
        self.assertEqual(decision.status, "ELIGIBLE_FOR_REVIEW")
        self.assertEqual(decision.heldout_delta, 0.5)
        self.assertFalse(decision.automatic_promotion)
        self.assertTrue(decision.human_review_required)

    def test_heldout_regression_blocks_even_if_average_score_increases(self):
        baseline = evidence(1, (
            CaseOutcome("train-1", False),
            CaseOutcome("held-1", True),
            CaseOutcome("held-2", True),
        ))
        candidate = evidence(2, (
            CaseOutcome("train-1", True),
            CaseOutcome("held-1", False),
            CaseOutcome("held-2", True),
        ))
        decision = compare_skill_evaluations(
            baseline_skill=skill(1), candidate_skill=skill(2), cases=cases(),
            baseline=baseline, candidate=candidate, max_resource_units=10,
        )
        self.assertEqual(decision.status, "BLOCKED")
        self.assertEqual(decision.heldout_regressions, ("held-1",))

    def test_resource_budget_blocks_candidate(self):
        baseline = evidence(1, (
            CaseOutcome("train-1", True),
            CaseOutcome("held-1", False),
            CaseOutcome("held-2", False),
        ))
        candidate = evidence(2, (
            CaseOutcome("train-1", True, 10),
            CaseOutcome("held-1", True, 10),
            CaseOutcome("held-2", True, 10),
        ))
        decision = compare_skill_evaluations(
            baseline_skill=skill(1), candidate_skill=skill(2), cases=cases(),
            baseline=baseline, candidate=candidate, max_resource_units=20,
        )
        self.assertEqual(decision.reason, "resource_budget_exceeded")

    def test_evaluator_or_runner_must_not_change_between_comparisons(self):
        baseline = evidence(1, (
            CaseOutcome("train-1", True), CaseOutcome("held-1", False),
            CaseOutcome("held-2", False),
        ))
        altered = EvaluationEvidence(
            skill_sha256=skill(2).sha256, suite_sha256=suite_digest(cases()),
            evaluator_sha256="e" * 64, runner_id="different-runner",
            runner_revision="different", outcomes=(
                CaseOutcome("train-1", True), CaseOutcome("held-1", True),
                CaseOutcome("held-2", True),
            ),
        )
        with self.assertRaisesRegex(ValueError, "evaluator and runner"):
            compare_skill_evaluations(
                baseline_skill=skill(1), candidate_skill=skill(2), cases=cases(),
                baseline=baseline, candidate=altered, max_resource_units=20,
            )

    def test_missing_duplicate_or_mismatched_outcomes_fail_closed(self):
        baseline = evidence(1, (
            CaseOutcome("train-1", True), CaseOutcome("held-1", False),
            CaseOutcome("held-2", False),
        ))
        duplicate = evidence(2, (
            CaseOutcome("train-1", True), CaseOutcome("held-1", True),
            CaseOutcome("held-1", True),
        ))
        with self.assertRaisesRegex(ValueError, "every suite case exactly once"):
            compare_skill_evaluations(
                baseline_skill=skill(1), candidate_skill=skill(2), cases=cases(),
                baseline=baseline, candidate=duplicate, max_resource_units=20,
            )

    def test_candidate_must_be_newer_version_of_same_skill(self):
        with self.assertRaisesRegex(ValueError, "newer version"):
            compare_skill_evaluations(
                baseline_skill=skill(1), candidate_skill=skill(1), cases=cases(),
                baseline=evidence(1, (
                    CaseOutcome("train-1", True), CaseOutcome("held-1", False),
                    CaseOutcome("held-2", False),
                )),
                candidate=evidence(1, (
                    CaseOutcome("train-1", True), CaseOutcome("held-1", True),
                    CaseOutcome("held-2", True),
                )), max_resource_units=20,
            )


if __name__ == "__main__":
    unittest.main()
