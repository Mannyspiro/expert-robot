import copy
import unittest

from python.merlin.math_logic_discrete_course import (
    load_math_logic_discrete_manifest,
    validate_math_logic_discrete_manifest,
)
from python.merlin.math_foundations_course import load_math_foundations_manifest


class MathLogicDiscreteCourseTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_math_logic_discrete_manifest()
        foundations = load_math_foundations_manifest()
        # Both course templates are checked against the same canonical catalog.
        self.assertEqual(foundations["curriculum_id"], "math-foundations-v1")

    def _catalog(self):
        from pathlib import Path
        import json
        root = Path(__file__).resolve().parents[1]
        return json.loads((root / "docs/research/merlin-mathematical-idea-catalog.v1.json").read_text())

    def test_canonical_course_covers_all_three_pathways(self):
        result = validate_math_logic_discrete_manifest(self.manifest, self._catalog())
        self.assertEqual(result["objective_count"], 3)
        self.assertEqual(result["lesson_count"], 3)
        self.assertEqual(result["exercise_count"], 3)

    def test_objective_must_match_canonical_prerequisites(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["objectives"][2]["prerequisites"] = []
        with self.assertRaisesRegex(ValueError, "prerequisites differ"):
            validate_math_logic_discrete_manifest(manifest, self._catalog())

    def test_symbols_cannot_precede_exploration(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["lessons"][0]["stages"] = [
            {"mode": "concrete", "prompt": "Concrete."},
            {"mode": "symbol", "prompt": "Use symbols."},
        ]
        with self.assertRaisesRegex(ValueError, "symbols appear before exploration"):
            validate_math_logic_discrete_manifest(manifest, self._catalog())

    def test_every_pathway_module_must_cover_every_lesson(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["modules"][0]["lesson_ids"].pop()
        with self.assertRaisesRegex(ValueError, "all three pathways"):
            validate_math_logic_discrete_manifest(manifest, self._catalog())


if __name__ == "__main__":
    unittest.main()
