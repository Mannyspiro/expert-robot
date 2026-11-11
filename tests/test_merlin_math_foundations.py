import tempfile
import unittest
from pathlib import Path

from merlin.learning_core import LearnerStore, LessonSession
from merlin.math_foundations import (
    FOUNDATION_CONCEPTS,
    FOUNDATION_LESSONS,
    select_foundation_lesson,
    validate_foundation_curriculum,
)


class MathFoundationsCurriculumTests(unittest.TestCase):
    def test_curriculum_has_valid_prerequisite_graph_and_unique_ids(self):
        result = validate_foundation_curriculum()
        self.assertEqual(len(result), 8)
        self.assertEqual(len({item.exercise.task_id for item in result.values()}), 8)
        self.assertEqual(FOUNDATION_CONCEPTS.get("proof-by-contradiction").prerequisites, ("prime-numbers",))

    def test_all_lessons_are_zero_first_and_have_progressive_hints(self):
        for item in FOUNDATION_LESSONS:
            with self.subTest(lesson=item.lesson.lesson_id):
                item.validate(FOUNDATION_CONCEPTS)
                self.assertEqual(item.lesson.stages[0].mode, "concrete")
                self.assertGreaterEqual(len(item.exercise.hints), 2)
                self.assertTrue(item.exercise.transfer_prompt)
                self.assertTrue(item.exercise.rubric)

    def test_symbolic_stages_follow_observation_or_visual_exploration(self):
        for item in FOUNDATION_LESSONS:
            with self.subTest(lesson=item.lesson.lesson_id):
                symbol_index = next(
                    (i for i, stage in enumerate(item.lesson.stages) if stage.introduces_symbols),
                    None,
                )
                if symbol_index is not None:
                    prior_modes = {stage.mode for stage in item.lesson.stages[:symbol_index]}
                    self.assertTrue({"observation", "visual"} & prior_modes)

    def test_euclid_lesson_preserves_historical_source_context(self):
        item = next(x for x in FOUNDATION_LESSONS if x.exercise.task_id == "prove-infinite-primes")
        self.assertIn("Elements, Book IX, Proposition 20", item.historical_context)
        self.assertEqual(item.source_refs, ("Euclid, Elements, Book IX, Proposition 20",))

    def test_new_learner_gets_a_zero_prerequisite_lesson_on_each_path(self):
        with tempfile.TemporaryDirectory() as temp:
            store = LearnerStore(Path(temp) / "learner.sqlite")
            for path in ("mathematician", "mathematics_programmer", "computational_hacker"):
                with self.subTest(path=path):
                    selected = select_foundation_lesson(f"learner-{path}", store, path=path)
                    self.assertIsNotNone(selected)
                    self.assertEqual(selected.prerequisites, ())

    def test_lesson_session_keeps_symbolic_content_sequential(self):
        item = FOUNDATION_LESSONS[0]
        session = LessonSession(item.lesson)
        self.assertEqual(session.current_stage.mode, "concrete")
        for stage in item.lesson.stages[:-1]:
            session.complete_current_stage(stage.stage_id)
        self.assertTrue(session.current_stage.introduces_symbols)


if __name__ == "__main__":
    unittest.main()


class AdaptiveFoundationPlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = LearnerStore(Path(self.temp.name) / "adaptive.sqlite")

    def tearDown(self):
        self.temp.cleanup()

    def test_interest_fit_changes_the_top_recommendation(self):
        from merlin.math_foundations import recommend_foundation_lessons

        result = recommend_foundation_lessons(
            "learner", self.store,
            path_weights={"mathematician": 1.0},
            interests=["modeling"],
        )
        self.assertEqual(result["ranked_lessons"][0]["task_id"], "introduce-variables")
        self.assertIn("matches_learner_interests", result["ranked_lessons"][0]["reason_codes"])

    def test_prerequisite_is_blocked_until_core_learning_dimensions_are_demonstrated(self):
        from merlin.learning_core import Attempt
        from merlin.math_foundations import recommend_foundation_lessons

        before = recommend_foundation_lessons(
            "learner", self.store,
            path_weights={"mathematician": 1.0},
            interests=["number_theory"],
        )
        blocked_ids = {item["task_id"] for item in before["blocked_lessons"]}
        self.assertIn("build-factor-table", blocked_ids)

        self.store.record_attempt(
            Attempt(
                "learner", "foundation-diagnostic", "whole-number-check",
                {"conceptual": 1.0, "procedural": 1.0, "representational": 1.0},
                independent=True,
            ),
            ("whole-number-structure",),
            learning_rate=1.0,
        )
        after = recommend_foundation_lessons(
            "learner", self.store,
            path_weights={"mathematician": 1.0},
            interests=["number_theory"],
        )
        ranked_ids = {item["task_id"] for item in after["ranked_lessons"]}
        self.assertIn("build-factor-table", ranked_ids)

    def test_time_budget_and_completed_task_filters_are_explicit(self):
        from merlin.math_foundations import recommend_foundation_lessons

        over_budget = recommend_foundation_lessons(
            "learner", self.store,
            path_weights={
                "mathematician": 1 / 3,
                "mathematics_programmer": 1 / 3,
                "computational_hacker": 1 / 3,
            },
            max_minutes=15,
        )
        self.assertEqual(over_budget["eligible_count"], 0)
        self.assertEqual(len(over_budget["blocked_lessons"]), 8)

        completed = recommend_foundation_lessons(
            "learner", self.store,
            path_weights={"mathematician": 1.0},
            completed_task_ids=["discover-counting-patterns"],
        )
        self.assertNotIn(
            "discover-counting-patterns",
            {item["task_id"] for item in completed["ranked_lessons"]},
        )

    def test_planner_is_deterministic_and_rejects_invalid_weights(self):
        from merlin.math_foundations import recommend_foundation_lessons

        kwargs = {
            "path_weights": {"mathematician": 0.5, "mathematics_programmer": 0.5},
            "interests": ["patterns", "python"],
        }
        first = recommend_foundation_lessons("learner", self.store, **kwargs)
        second = recommend_foundation_lessons("learner", self.store, **kwargs)
        self.assertEqual(first, second)
        with self.assertRaisesRegex(ValueError, "at least one path weight"):
            recommend_foundation_lessons(
                "learner", self.store,
                path_weights={"mathematician": 0.0},
            )
