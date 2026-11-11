import copy
import json
import unittest
from pathlib import Path

from python.merlin.math_algebra_functions_course import (
    load_math_algebra_functions_manifest,
    validate_math_algebra_functions_manifest,
)


class MathAlgebraFunctionsCourseTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_math_algebra_functions_manifest()
        root = Path(__file__).resolve().parents[1]
        self.catalog = json.loads((root / "docs/research/merlin-mathematical-idea-catalog.v1.json").read_text())

    def test_course_covers_patterns_algebra_sets_equations_and_functions(self):
        result = validate_math_algebra_functions_manifest(self.manifest, self.catalog)
        self.assertEqual(result["objective_count"], 5)
        self.assertEqual(result["lesson_count"], 5)
        self.assertEqual(result["exercise_count"], 5)

    def test_prerequisite_metadata_must_match_canonical_idea(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["objectives"][-1]["prerequisites"] = ["MATH-NT-001"]
        with self.assertRaisesRegex(ValueError, "prerequisites differ"):
            validate_math_algebra_functions_manifest(manifest, self.catalog)

    def test_high_stakes_or_ai_only_assessment_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["assessments"][0]["high_stakes"] = True
        with self.assertRaisesRegex(ValueError, "low-stakes"):
            validate_math_algebra_functions_manifest(manifest, self.catalog)

    def test_each_pathway_must_cover_every_lesson(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["modules"][1]["lesson_ids"].pop()
        with self.assertRaisesRegex(ValueError, "all three pathways"):
            validate_math_algebra_functions_manifest(manifest, self.catalog)


if __name__ == "__main__":
    unittest.main()
