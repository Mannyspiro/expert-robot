import unittest

from merlin.learning_core import DEFAULT_CONCEPTS
from merlin.parrondo_lesson import PARRONDO_LESSON
from merlin.renderer import render_lesson


class ParrondoLessonIntegrationTests(unittest.TestCase):
    def test_lesson_targets_are_in_canonical_concept_registry(self):
        DEFAULT_CONCEPTS.validate()
        known = {concept.concept_id for concept in DEFAULT_CONCEPTS.all()}
        self.assertTrue(set(PARRONDO_LESSON.concept_ids) <= known)

    def test_all_paths_share_one_lesson_and_one_concept_set(self):
        self.assertEqual(
            set(PARRONDO_LESSON.path_tags),
            {"mathematician", "mathematics_programmer", "computational_hacker"},
        )
        self.assertEqual(PARRONDO_LESSON.lesson_id, "math.parrondo.zero_first.v1")

    def test_renderer_preserves_concrete_before_symbolic_order(self):
        rendered = render_lesson(PARRONDO_LESSON)
        kinds = [block.kind for block in rendered["blocks"]]
        self.assertEqual(kinds[0], "story")
        self.assertLess(kinds.index("manipulative"), kinds.index("explanation"))
        self.assertTrue(rendered["accessibility"]["screen_reader_labels_required"])

    def test_simulation_has_explicit_reproducibility_metadata(self):
        experiment = next(b for b in PARRONDO_LESSON.blocks if b.kind == "simulation")
        self.assertEqual(experiment.content["seed"], 20261111)
        self.assertEqual(experiment.content["engine"], "parrondo.v1")
        self.assertEqual(experiment.content["parameters"]["trials"], 1000)


if __name__ == "__main__":
    unittest.main()
