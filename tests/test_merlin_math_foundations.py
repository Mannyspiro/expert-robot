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
