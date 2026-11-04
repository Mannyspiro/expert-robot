import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from merlin.engineering_ir import EngineeringProject, Net, Part, Pin
from merlin.engineering_project_store import (
    EngineeringProjectStore, deterministic_diff, project_from_dict, project_hash, project_to_dict,
)

def sample():
    return EngineeringProject(
        name="bench-controller", units="mm",
        parts=(
            Part("U1", "controller", (Pin("1", "VCC", 5.5, 0.5), Pin("2", "GND", 5.5, 0.5)),
                 size_mm=(20, 15, 2), position_mm=(0, 0, 1)),
            Part("J1", "power connector", (Pin("1", "5V", 5.5, 1.0), Pin("2", "GND", 5.5, 1.0))),
        ),
        nets=(
            Net("VCC_5V", ("U1.1", "J1.1"), nominal_voltage_v=5.0, max_current_a=0.25),
            Net("GND", ("U1.2", "J1.2"), nominal_voltage_v=0.0, max_current_a=0.25),
        ),
        metadata={"owner": "Merlin", "purpose": "test fixture"},
    )

class EngineeringProjectStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = EngineeringProjectStore(Path(self.temp.name) / "engineering.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_round_trip_and_stable_hash(self):
        original = sample()
        restored = project_from_dict(project_to_dict(original))
        self.assertEqual(project_hash(original), project_hash(restored))
        self.assertEqual(restored.name, original.name)
        self.assertEqual(next(part for part in restored.parts if part.ref == "U1").pins[0].name, "VCC")

    def test_canonical_hash_ignores_input_order(self):
        original = sample()
        reordered = replace(original, parts=tuple(reversed(original.parts)),
                            nets=tuple(reversed(original.nets)))
        self.assertEqual(project_hash(original), project_hash(reordered))

    def test_save_is_idempotent_and_revisions_are_append_only(self):
        first = self.store.save("project-1", sample())
        repeat = self.store.save("project-1", sample())
        self.assertEqual(first["revision"], 1)
        self.assertTrue(repeat["unchanged"])
        updated = replace(sample(), name="bench-controller-v2")
        second = self.store.save("project-1", updated)
        self.assertEqual(second["revision"], 2)
        self.assertEqual(len(self.store.history("project-1")), 2)
        self.assertTrue(self.store.verify_history("project-1"))

    def test_revision_diff_is_deterministic(self):
        before = sample()
        after = replace(before, parts=(replace(before.parts[0], position_mm=(1, 2, 3)),
                                       before.parts[1]))
        diff_a = deterministic_diff(before, after)
        diff_b = deterministic_diff(before, after)
        self.assertEqual(diff_a, diff_b)
        self.assertTrue(any(item["operation"] == "replace" and
                            item["path"].endswith("/position_mm/0") for item in diff_a))

    def test_store_diff_between_revisions(self):
        self.store.save("project-2", sample())
        changed = replace(sample(), parts=(replace(sample().parts[0], position_mm=(5, 0, 1)),
                                           sample().parts[1]))
        self.store.save("project-2", changed)
        diff = self.store.diff("project-2", 1, 2)
        self.assertTrue(any("/position_mm/0" in item["path"] for item in diff))

    def test_rejects_unsupported_schema_and_invalid_project(self):
        document = project_to_dict(sample())
        document["schema_version"] = 999
        with self.assertRaises(ValueError):
            project_from_dict(document)
        invalid = replace(sample(), units="inches")
        with self.assertRaises(ValueError):
            self.store.save("bad-project", invalid)

    def test_missing_revision_raises(self):
        with self.assertRaises(KeyError):
            self.store.load("not-found")

if __name__ == "__main__":
    unittest.main()