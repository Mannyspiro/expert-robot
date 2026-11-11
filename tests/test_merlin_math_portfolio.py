import copy
import unittest

from scripts.merlin_math_portfolio_validate import load_portfolio, validate_portfolio


class MerlinMathPortfolioTests(unittest.TestCase):
    def setUp(self):
        self.catalog, self.manifests = load_portfolio()

    def test_authored_course_portfolio_has_resolved_cross_course_prerequisites(self):
        self.assertEqual(validate_portfolio(self.catalog, self.manifests), [])

    def test_external_prerequisite_must_be_taught_in_another_course(self):
        manifests = [
            copy.deepcopy(item) for item in self.manifests
            if item["curriculum_id"] != "math-algebra-functions-v1"
        ]
        errors = validate_portfolio(self.catalog, manifests)
        self.assertTrue(any("external prerequisite MATH-FUNC-001 has no lesson" in x for x in errors))

    def test_shared_lesson_id_must_have_identical_content(self):
        manifests = copy.deepcopy(self.manifests)
        logic = next(x for x in manifests if x["curriculum_id"] == "math-logic-discrete-v1")
        algebra = next(x for x in manifests if x["curriculum_id"] == "math-algebra-functions-v1")
        shared = next(x for x in algebra["lessons"] if x["id"] == "math-sets-relations-v1")
        shared["body"] += " Divergent duplicate."
        errors = validate_portfolio(self.catalog, manifests)
        self.assertTrue(any("has divergent content" in x for x in errors))

    def test_cross_course_objective_metadata_must_match(self):
        manifests = copy.deepcopy(self.manifests)
        algebra = next(x for x in manifests if x["curriculum_id"] == "math-algebra-functions-v1")
        objective = next(x for x in algebra["objectives"] if x["id"] == "MATH-SET-001")
        objective["title"] = "A different title"
        errors = validate_portfolio(self.catalog, manifests)
        self.assertTrue(any("cross-course objective drift for MATH-SET-001" in x for x in errors))


if __name__ == "__main__":
    unittest.main()
