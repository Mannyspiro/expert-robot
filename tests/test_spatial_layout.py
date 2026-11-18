import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from merlin.spatial_layout import read_study, render_layout


FIXTURE = Path(__file__).resolve().parents[1] / "examples/merlin/exhibit-layouts.json"


class SpatialReviewTests(unittest.TestCase):
    def test_example_preserves_inventory_and_removes_two_geometric_defects(self):
        report, models = read_study(FIXTURE)
        first, second = report["layouts"]
        self.assertEqual(first["collisions"], [["wave-tank", "imaging-bench"]])
        self.assertEqual(first["out_of_bounds"], ["screen"])
        self.assertEqual(second["collisions"], [])
        self.assertEqual(second["out_of_bounds"], [])
        inventory = lambda layout: {item["id"]: item["size"] for item in layout["items"]}
        self.assertEqual(inventory(first), inventory(second))
        for layout in report["layouts"]:
            model = models[layout["obj"]]
            self.assertEqual(hashlib.sha256(model).hexdigest(), layout["obj_sha256"])
            self.assertEqual(model.count(b"\nv "), 24)
            self.assertEqual(model.count(b"\nf "), 18)

    def test_micrometre_contact_and_penetration(self):
        a = {"id": "a", "origin": [0.1, 0, 0], "size": [0.2, 1, 1]}
        b = {"id": "b", "origin": [0.3, 0, 0], "size": [1, 1, 1]}
        layout = {"name": "contact", "items": [a, b]}
        spec = {"title": "Contact test", "unit": "m", "room": [2, 2, 2], "layouts": [layout]}
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "study.json"
            for x, expected in ((0.3, []), (0.299999, [["a", "b"]])):
                b["origin"][0] = x
                source.write_text(json.dumps(spec))
                report, _ = read_study(source)
                self.assertEqual(report["layouts"][0]["collisions"], expected)
            b["origin"][0] = 0.3000001
            source.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ValueError, "micrometre"):
                read_study(source)

    def test_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "existing"
            destination.mkdir()
            marker = destination / "original"
            marker.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                render_layout(FIXTURE, destination)
            self.assertEqual(marker.read_bytes(), b"original")
            self.assertEqual(list(destination.iterdir()), [marker])
