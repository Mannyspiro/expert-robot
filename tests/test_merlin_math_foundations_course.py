import json
import tempfile
import unittest
from pathlib import Path

from python.merlin.learning_platform import Actor, LearningPlatform
from python.merlin.learner_model import LearnerStore
from python.merlin.math_foundations_course import (
    load_math_foundations_manifest,
    validate_math_foundations_manifest,
)


class MathFoundationsCourseTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).parents[1]
        self.manifest = load_math_foundations_manifest(self.repo_root)
        self.catalog = json.loads(
            (self.repo_root / "docs" / "research" / "merlin-mathematical-idea-catalog.v1.json")
            .read_text(encoding="utf-8")
        )

    def test_course_manifest_matches_canonical_idea_graph(self):
        result = validate_math_foundations_manifest(self.manifest, self.catalog)
        self.assertEqual(result["curriculum_id"], "math-foundations-v1")
        self.assertEqual(result["objective_count"], 7)
        self.assertEqual(result["lesson_count"], 7)
        self.assertEqual(result["exercise_count"], 7)

    def test_all_lessons_begin_concrete_and_delay_symbolic_notation(self):
        for lesson in self.manifest["lessons"]:
            with self.subTest(lesson=lesson["id"]):
                self.assertEqual(lesson["stages"][0]["mode"], "concrete")
                modes = [stage["mode"] for stage in lesson["stages"]]
                if "symbol" in modes:
                    symbol_index = modes.index("symbol")
                    self.assertTrue(
                        "observation" in modes[:symbol_index]
                        or "visual" in modes[:symbol_index]
                    )

    def test_proof_assessment_requires_human_review(self):
        proof = next(
            item for item in self.manifest["assessments"]
            if item["objective_id"] == "MATH-LOG-001"
        )
        self.assertFalse(proof["high_stakes"])
        self.assertTrue(proof["human_review_required"])
        self.assertTrue(self.manifest["grading_policy"]["proof_requires_human_review"])

    def test_course_lifecycle_and_fresh_learner_recommendation(self):
        with tempfile.TemporaryDirectory() as temp:
            platform = LearningPlatform(Path(temp) / "courses.sqlite3")
            learner_store = LearnerStore(Path(temp) / "learners.sqlite3")
            instructor = Actor("tenant-a", "instructor-a", "instructor")
            reviewer = Actor("tenant-a", "reviewer-a", "reviewer")
            learner = Actor("tenant-a", "learner-a", "learner")

            course = platform.create_course(
                instructor,
                "math-foundations",
                self.manifest["title"],
                self.manifest["description"],
            )
            updated = platform.update_manifest(instructor, course["course_id"], self.manifest)
            platform.review_course(
                reviewer, course["course_id"], updated["version"],
                "approved", "Reviewed low-stakes content and human-review requirements.",
            )
            platform.publish_course(instructor, course["course_id"])
            platform.enroll(learner, course["course_id"])

            recommendation = platform.recommend_next_lesson(
                learner, course["course_id"], learner_store
            )
            self.assertEqual(recommendation["state"], "recommended")
            self.assertIn(
                recommendation["lesson_id"],
                {"math-foundations-counting-v1", "math-foundations-variables-v1"},
            )
            self.assertEqual(recommendation["authority"], "recommendation_only")


if __name__ == "__main__":
    unittest.main()
