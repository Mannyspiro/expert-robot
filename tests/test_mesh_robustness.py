import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "scripts/merlin"), *sys.path]):
    import measure_mesh_three_rows as study


class MeshRobustnessTests(unittest.TestCase):
    def test_known_center_and_tilt_are_recovered(self):
        for mid, slope in ((.43, -.45), (.57, .45)):
            center, gradient = study.fit(lambda x,y: study.field(x,y,mid+slope*(y-.5)))
            self.assertAlmostEqual(center, mid, places=12)
            self.assertAlmostEqual(gradient, slope, places=12)

    def test_background_mismatch_detects_nonpositive_residual(self):
        import math
        def source(x,y):
            return math.exp(-((x-(.43-.45*(y-.5)))/.08)**2)+.12*math.sin(2*math.pi*y)
        with self.assertRaisesRegex(ValueError, "positive residual"):
            study.fit(source)
