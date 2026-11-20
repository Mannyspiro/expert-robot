"""Regression checks for the nine-probe mesh experiment."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "scripts/merlin"), *sys.path]):
    import measure_mesh_localization as study


class MeshLocalizationTests(unittest.TestCase):
    def test_peak_and_fallback(self):
        xs = [0, 0.25, 0.5, 0.75, 1]
        self.assertEqual(study.estimate_center(xs, [0, 3, 1, 1, 0], 0.1), 0.25)
        for values in ([0] * 5, [0, .01, 0, 0, 0], [1, 1, 0, 0, 0], [3, 1, 0, 0, 0]):
            with self.subTest(values=values):
                self.assertIsNone(study.estimate_center(xs, values, 0.1))
        with self.assertRaises(ValueError):
            study.estimate_center(xs, [0, 0, float("nan"), 1, 0], 0.1)

    def test_template_warp(self):
        vertices = [(x/4, 0.25) for x in range(5)]
        self.assertEqual(study.move_template(vertices, 0.25),
                         [(x, .25) for x in (0, .125, .25, .625, 1)])

    def test_replay_and_budgets(self):
        saved = json.loads((ROOT / "docs/evidence/mesh-localization-20261118.json").read_bytes())
        replay = study.measure()
        self.assertEqual(replay["advance"], saved["advance"])
        self.assertEqual(replay["cases"].keys(), saved["cases"].keys())
        for name, case in replay["cases"].items():
            self.assertEqual(case["shared_pilot_queries"], 9)
            for arm, result in case["arms"].items():
                with self.subTest(name=name, arm=arm):
                    self.assertEqual((result["vertex_queries"], result["scoring_queries"]), (541, 4096))
                    self.assertEqual(result["uncovered"], 0)
                    self.assertLess(result["affine_max_error"], 1e-10)
                    expected = saved["cases"][name]["arms"][arm]["rmse"]
                    self.assertAlmostEqual(result["rmse"], expected, places=12)
