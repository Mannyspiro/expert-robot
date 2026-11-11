import tempfile
import unittest
from pathlib import Path

from merlin.lesson_schema import LessonBlock, LessonDocument, lesson_to_dict
from merlin.renderer import interaction_count, record_interaction, render_lesson
from merlin.learning_core import LearnerStore


def sample_lesson():
    return LessonDocument(
        lesson_id="math.parrondo.zero_first.v1",
        version=1,
        title="Two losing games",
        concept_ids=("quantity", "change"),
        prerequisites=(),
        path_tags=("mathematician", "mathematics_programmer", "computational_hacker"),
        blocks=(
            LessonBlock("story", "story", {"narration": "Two games appear to lose."}),
            LessonBlock("tokens", "manipulative", {"initial_tokens": 30}),
            LessonBlock("predict", "choice", {"options": ["A", "B", "mixture"]}),
            LessonBlock("run", "simulation", {"engine": "parrondo.v1", "parameters": {"turns": 3000}, "seed": 41}),
            LessonBlock("plot", "chart", {"series": [{"name": "balance", "values": [30, 31]}]}),
            LessonBlock("explain", "explanation", {"text": "State frequencies matter."}),
            LessonBlock("reflect", "reflection", {"prompt": "Explain in your own words."}),
            LessonBlock("recall", "retrieval", {"prompt": "What controls game B?"}),
            LessonBlock("assess", "assessment", {"rubric": ["conceptual", "transfer"]}),
        ),
    )


class LessonSchemaTests(unittest.TestCase):
    def test_valid_zero_first_lesson(self):
        lesson = sample_lesson()
        lesson.validate(("quantity", "change"))
        self.assertEqual(lesson_to_dict(lesson)["lesson_id"], lesson.lesson_id)

    def test_rejects_symbol_before_exploration(self):
        lesson = sample_lesson()
        bad = LessonDocument(
            lesson.lesson_id, 1, lesson.title, lesson.concept_ids, (), lesson.path_tags,
            (LessonBlock("symbols", "explanation", {}, True), LessonBlock("story", "story", {})),
        )
        with self.assertRaises(ValueError):
            bad.validate()

    def test_rejects_duplicate_block_ids(self):
        lesson = sample_lesson()
        bad = LessonDocument(
            lesson.lesson_id, 1, lesson.title, lesson.concept_ids, (), lesson.path_tags,
            (LessonBlock("x", "story"), LessonBlock("x", "manipulative")),
        )
        with self.assertRaises(ValueError):
            bad.validate()


class RendererTests(unittest.TestCase):
    def test_rendered_lesson_has_accessibility_contract(self):
        result = render_lesson(sample_lesson())
        self.assertTrue(result["accessibility"]["keyboard"])
        self.assertEqual(len(result["blocks"]), 9)

    def test_interaction_persists_without_changing_mastery(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LearnerStore(Path(tmp) / "learner.sqlite")
            lesson = sample_lesson()
            before = store.mastery("learner-1", "quantity")
            event_id = record_interaction(
                store, learner_id="learner-1", lesson=lesson,
                block_id="tokens", event_type="apply_action", response={"move": "add"},
            )
            self.assertGreater(event_id, 0)
            self.assertEqual(interaction_count(store, "learner-1"), 1)
            self.assertEqual(before, store.mastery("learner-1", "quantity"))

    def test_assessment_can_update_mastery(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LearnerStore(Path(tmp) / "learner.sqlite")
            record_interaction(
                store, learner_id="learner-1", lesson=sample_lesson(),
                block_id="assess", event_type="assessment_submitted",
                response={"explanation": "State frequencies shift."},
                scores={"conceptual": 0.8, "transfer": 0.6},
            )
            self.assertGreater(store.mastery("learner-1", "quantity")["conceptual"], 0)


if __name__ == "__main__":
    unittest.main()
