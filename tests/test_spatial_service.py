import json
from pathlib import Path
import tempfile
import unittest

from merlin.spatial_layout import read_study


FIXTURE = Path(__file__).resolve().parents[1] / "examples/merlin/exhibit-service-layouts.json"


class ServiceZoneTests(unittest.TestCase):
    def evaluate(self, spec):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "study.json"
            path.write_text(json.dumps(spec))
            return read_study(path)

    def test_example_classifies_three_distinct_findings(self):
        report, meshes = read_study(FIXTURE)
        first, revised = report["layouts"]
        self.assertEqual(first["collisions"], [])
        self.assertEqual(first["out_of_bounds"], [])
        self.assertEqual(first["service_intrusions"], [{"owner": "pump", "zone": "panel", "equipment": "station"}])
        self.assertEqual(first["service_out_of_bounds"], [{"owner": "filter", "zone": "drawer"}])
        self.assertEqual(first["simultaneous_service_conflicts"], [
            {"owner_a": "pump", "zone_a": "panel", "owner_b": "station", "zone_b": "panel"}])
        for key in ("service_intrusions", "service_out_of_bounds", "simultaneous_service_conflicts"):
            self.assertEqual(revised[key], [])
        spec = json.loads(FIXTURE.read_bytes())
        for layout in spec["layouts"]:
            for item in layout["items"]:
                del item["service_zones"]
        stripped, bare_meshes = self.evaluate(spec)
        self.assertEqual(stripped["layouts"][0]["service_zones"], [])
        self.assertEqual(meshes, bare_meshes)

    def test_self_intrusion_and_same_owner_union(self):
        spec = json.loads(FIXTURE.read_bytes())
        spec["layouts"] = spec["layouts"][:1]
        item = spec["layouts"][0]["items"][0]
        spec["layouts"][0]["items"] = [item]
        zone = item["service_zones"][0]
        zone["origin"][0] = 0.999999
        item["service_zones"].append(dict(zone, id="reach"))
        result, _ = self.evaluate(spec)
        layout = result["layouts"][0]
        self.assertEqual(len(layout["service_intrusions"]), 2)
        self.assertTrue(all(f["owner"] == f["equipment"] for f in layout["service_intrusions"]))
        self.assertEqual(layout["simultaneous_service_conflicts"], [])
        self.assertEqual(layout["service_zones"][0]["origin"], [1.999999, 1.0, 0.0])

    def test_duplicate_zone_names_and_malformed_lists(self):
        spec = json.loads(FIXTURE.read_bytes())
        item = spec["layouts"][0]["items"][0]
        zone = item["service_zones"][0]
        for invalid in (None, {}, [zone, zone], [zone] * 9):
            with self.subTest(invalid=invalid):
                item["service_zones"] = invalid
                with self.assertRaises(ValueError):
                    self.evaluate(spec)
