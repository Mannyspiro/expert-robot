import copy
import json
import unittest
from pathlib import Path

from python.merlin.math_numerical_scientific_computing_course import (
    load_math_numerical_scientific_computing_manifest,
    validate_math_numerical_scientific_computing_manifest,
)


class MathNumericalScientificComputingCourseTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_math_numerical_scientific_computing_manifest()
        root = Path(__file__).resolve().parents[1]
        self.catalog = json.loads(
            (root / "docs/research/merlin-mathematical-idea-catalog.v1.json").read_text()
        )

    def test_course_covers_linear_algebra_numerics_odes_and_optimization(self):
        result = validate_math_numerical_scientific_computing_manifest(self.manifest, self.catalog)
        self.assertEqual(result["objective_count"], 4)
        self.assertEqual(result["lesson_count"], 4)
        self.assertEqual(result["exercise_count"], 4)

    def test_external_prerequisites_are_explicit(self):
        ode = next(x for x in self.manifest["objectives"] if x["id"] == "MATH-ODE-001")
        self.assertEqual(
            ode["external_prerequisites"], ["MATH-CALC-002", "MATH-CALC-003"]
        )

    def test_objective_prerequisites_must_match_catalog(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["objectives"][2]["prerequisites"] = ["MATH-NUM-001"]
        with self.assertRaisesRegex(ValueError, "prerequisites differ"):
            validate_math_numerical_scientific_computing_manifest(manifest, self.catalog)

    def test_each_pathway_must_cover_all_lessons(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["modules"][1]["lesson_ids"].pop()
        with self.assertRaisesRegex(ValueError, "all three pathways"):
            validate_math_numerical_scientific_computing_manifest(manifest, self.catalog)


if __name__ == "__main__":
    unittest.main()
