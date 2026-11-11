import copy
import json
import unittest
from pathlib import Path

from python.merlin.math_calculus_probability_course import (
    load_math_calculus_probability_manifest,
    validate_math_calculus_probability_manifest,
)


class MathCalculusProbabilityCourseTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_math_calculus_probability_manifest()
        root = Path(__file__).resolve().parents[1]
        self.catalog = json.loads(
            (root / "docs/research/merlin-mathematical-idea-catalog.v1.json").read_text()
        )

    def test_course_covers_calculus_probability_and_statistics(self):
        result = validate_math_calculus_probability_manifest(self.manifest, self.catalog)
        self.assertEqual(result["objective_count"], 5)
        self.assertEqual(result["lesson_count"], 5)
        self.assertEqual(result["exercise_count"], 5)

    def test_external_prerequisites_are_explicit(self):
        calc = next(x for x in self.manifest["objectives"] if x["id"] == "MATH-CALC-001")
        self.assertEqual(calc["external_prerequisites"], ["MATH-FUNC-001"])
        probability = next(x for x in self.manifest["objectives"] if x["id"] == "MATH-PROB-001")
        self.assertEqual(probability["external_prerequisites"], ["MATH-SET-001"])

    def test_objective_dimensions_must_match_canonical_catalog(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["objectives"][0]["dimensions"] = ["memorization"]
        with self.assertRaisesRegex(ValueError, "dimensions differ"):
            validate_math_calculus_probability_manifest(manifest, self.catalog)

    def test_every_pathway_must_cover_every_lesson(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["modules"][2]["lesson_ids"].pop()
        with self.assertRaisesRegex(ValueError, "all three pathways"):
            validate_math_calculus_probability_manifest(manifest, self.catalog)

    def test_external_prerequisite_must_have_a_canonical_lesson(self):
        catalog = copy.deepcopy(self.catalog)
        function_idea = next(x for x in catalog["ideas"] if x["id"] == "MATH-FUNC-001")
        function_idea["learning"]["lesson_id"] = None
        with self.assertRaisesRegex(ValueError, "has no canonical lesson"):
            validate_math_calculus_probability_manifest(self.manifest, catalog)

    def test_all_assessments_require_independent_human_review(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["assessments"][0]["human_review_required"] = False
        with self.assertRaisesRegex(ValueError, "low-stakes and human-reviewed"):
            validate_math_calculus_probability_manifest(manifest, self.catalog)


if __name__ == "__main__":
    unittest.main()
