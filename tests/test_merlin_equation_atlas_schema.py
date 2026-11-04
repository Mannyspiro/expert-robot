"""Tests for canonical equation-atlas schema migration."""
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from merlin.equation_atlas.normalize import normalize_entry

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "docs/research/real-world-equation-atlas"

class CanonicalSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ATLAS / "equation-entry.schema.json").read_text())
        cls.legacy = json.loads((ATLAS / "NORMALIZED_ENTRIES_001-020.json").read_text())
        cls.batch_021_030 = json.loads((ATLAS / "NORMALIZED_ENTRIES_021-030.json").read_text())
        cls.batch_031_040 = json.loads((ATLAS / "NORMALIZED_ENTRIES_031-040.json").read_text())
        cls.batch_041_050 = json.loads((ATLAS / "NORMALIZED_ENTRIES_041-050.json").read_text())
        cls.validator = Draft202012Validator(cls.schema)

    def test_all_legacy_entries_migrate_to_canonical_schema(self):
        migrated = [normalize_entry(item) for item in self.legacy["entries"]] + self.batch_021_030["entries"] + self.batch_031_040["entries"] + self.batch_041_050["entries"]
        self.assertEqual(len(migrated), 50)
        self.assertEqual([item["id"] for item in migrated], [f"RWEA-{i:03d}" for i in range(1, 51)])
        for entry in migrated:
            with self.subTest(entry=entry["id"]):
                self.assertEqual(list(self.validator.iter_errors(entry)), [])
                self.assertEqual(entry["evidence_status"], "UNVERIFIED")

    def test_dimensions_are_preserved(self):
        migrated = {x["id"]: x for x in map(normalize_entry, self.legacy["entries"])}
        p = migrated["RWEA-017"]["variables"]
        by_symbol = {v["symbol"]: v for v in p}
        self.assertEqual(by_symbol["p"]["dimension"], "L")
        self.assertEqual(by_symbol["R"]["dimension"], "dimensionless")

    def test_legacy_conditions_are_not_discarded(self):
        migrated = normalize_entry(self.legacy["entries"][0])
        self.assertTrue(any(x.startswith("Condition:") for x in migrated["assumptions"]))

    def test_unknown_fields_are_rejected(self):
        migrated = normalize_entry(self.legacy["entries"][0])
        migrated["invented_field"] = True
        self.assertTrue(list(self.validator.iter_errors(migrated)))

if __name__ == "__main__":
    unittest.main()
