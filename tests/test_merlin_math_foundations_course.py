import copy
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


    def test_all_three_pathways_have_aligned_module_and_lesson_membership(self):
        modules = {item["id"]: item["lesson_ids"] for item in self.manifest["modules"]}
        expected = {
            "mathematician": "mathematician",
            "mathematics-programmer": "mathematics_programmer",
            "computational-hacker": "computational_hacker",
        }
        for module_id, pathway in expected.items():
            for lesson_id in modules[module_id]:
                lesson = next(item for item in self.manifest["lessons"] if item["id"] == lesson_id)
                self.assertIn(pathway, lesson["pathways"])

    def test_rejects_unknown_objective_pathway(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["objectives"][0]["pathways"] = ["invented_path"]
        with self.assertRaisesRegex(ValueError, "known learning paths"):
            validate_math_foundations_manifest(manifest, self.catalog)

    def test_rejects_module_lesson_pathway_mismatch(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["lessons"][0]["pathways"].remove("mathematician")
        with self.assertRaisesRegex(ValueError, "outside its pathway"):
            validate_math_foundations_manifest(manifest, self.catalog)

    def test_rejects_objective_dimensions_that_drift_from_canonical_graph(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["objectives"][0]["dimensions"].append("invented_dimension")
        with self.assertRaisesRegex(ValueError, "dimensions differ"):
            validate_math_foundations_manifest(manifest, self.catalog)

    def test_rejects_prerequisite_cycles(self):
        manifest = copy.deepcopy(self.manifest)
        catalog = copy.deepcopy(self.catalog)
        manifest["objectives"][0]["prerequisites"] = ["MATH-NT-002"]
        idea = next(item for item in catalog["ideas"] if item["id"] == "MATH-NT-001")
        idea["learning"]["prerequisites"] = ["MATH-NT-002"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_math_foundations_manifest(manifest, catalog)

    def test_rejects_symbolic_stage_before_observation_or_visualization(self):
        manifest = copy.deepcopy(self.manifest)
        lesson = manifest["lessons"][0]
        lesson["stages"] = [
            {"mode": "concrete", "prompt": "Start with objects."},
            {"mode": "symbol", "prompt": "Write the formula."},
        ]
        with self.assertRaisesRegex(ValueError, "precedes exploration"):
            validate_math_foundations_manifest(manifest, self.catalog)

    def test_rejects_duplicate_exercise_task_ids(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["lessons"][1]["exercise"]["task_id"] = manifest["lessons"][0]["exercise"]["task_id"]
        with self.assertRaisesRegex(ValueError, "task_id must be unique"):
            validate_math_foundations_manifest(manifest, self.catalog)

    def test_rejects_ai_only_or_high_stakes_foundation_grading(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["grading_policy"]["ai_only_mastery_promotion"] = True
        with self.assertRaisesRegex(ValueError, "unsafe grading policy"):
            validate_math_foundations_manifest(manifest, self.catalog)

    def test_rejects_missing_human_review_for_proof_assessment(self):
        manifest = copy.deepcopy(self.manifest)
        proof = next(item for item in manifest["assessments"] if item["objective_id"] == "MATH-LOG-001")
        proof["human_review_required"] = False
        with self.assertRaisesRegex(ValueError, "low-stakes and human-reviewed"):
            validate_math_foundations_manifest(manifest, self.catalog)


if __name__ == "__main__":
    unittest.main()


    def test_canonical_idea_catalog_has_no_dangling_relations(self):
        from scripts.merlin_math_idea_validate import validate_catalog

        self.assertEqual(validate_catalog(self.catalog), [])
