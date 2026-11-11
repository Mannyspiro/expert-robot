import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "merlin_math_lesson_backlog_validate",
    ROOT / "scripts" / "merlin_math_lesson_backlog_validate.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class MathLessonBacklogValidationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(
            (ROOT / "docs/research/merlin-mathematical-idea-catalog.v1.json").read_text()
        )
        self.backlog = json.loads(
            (ROOT / "docs/merlin/MERLIN_MATH_LESSON_BACKLOG_V1.json").read_text()
        )

    def test_canonical_backlog_covers_every_unlinked_catalog_idea(self):
        self.assertEqual(MODULE.validate(self.catalog, self.backlog), [])

    def test_missing_blueprint_is_rejected(self):
        backlog = copy.deepcopy(self.backlog)
        backlog["blueprints"].pop()
        backlog["blueprint_count"] -= 1
        errors = MODULE.validate(self.catalog, backlog)
        self.assertTrue(any("blueprint coverage mismatch" in error for error in errors))

    def test_refuted_idea_cannot_enter_instructional_lane(self):
        backlog = copy.deepcopy(self.backlog)
        item = next(x for x in backlog["blueprints"] if x["catalog_status"] == "refuted")
        item["delivery_state"] = "instructional_candidate"
        errors = MODULE.validate(self.catalog, backlog)
        self.assertTrue(any("refuted idea must remain audit_only" in error for error in errors))

    def test_unresolved_conjecture_cannot_enter_core_lane(self):
        backlog = copy.deepcopy(self.backlog)
        item = next(x for x in backlog["blueprints"] if x["catalog_status"] == "unresolved")
        item["delivery_state"] = "instructional_candidate"
        errors = MODULE.validate(self.catalog, backlog)
        self.assertTrue(any("must remain research_laboratory" in error for error in errors))

    def test_claim_drift_is_rejected(self):
        backlog = copy.deepcopy(self.backlog)
        backlog["blueprints"][0]["source_claim"] += " altered"
        errors = MODULE.validate(self.catalog, backlog)
        self.assertTrue(any("source claim drift" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
