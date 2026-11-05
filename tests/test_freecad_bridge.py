import json
import tempfile
import unittest
from pathlib import Path

from merlin.engineering_ir import EngineeringProject, Net, Part, Pin
from merlin.freecad_bridge import build_freecad_macro, write_freecad_bundle


class FreeCADBridgeTests(unittest.TestCase):
    def project(self):
        return EngineeringProject(
            name="Test assembly", units="mm",
            parts=(Part("U1", "Controller", (Pin("1", "VCC", position_mm=(0, 0, 1)),
                                                  Pin("2", "GND")), size_mm=(10, 8, 2),
                        position_mm=(20, 30, 5)),),
            nets=(Net("POWER", ("U1.1", "U1.2"), nominal_voltage_v=3.3),),
        )

    def test_macro_preserves_centered_geometry_and_pin_markers(self):
        macro = build_freecad_macro(self.project(), "/tmp/model.FCStd", "/tmp/model.step")
        self.assertIn("obj.Placement.Base = Vector(x - sx/2.0", macro)
        self.assertIn('marker = DOC.addObject("Part::Sphere", "Pin_" + item["ref"]', macro)
        self.assertIn("model.step", macro)
        self.assertIn("MerlinReference", macro)

    def test_bundle_contains_macro_and_validated_netlist(self):
        with tempfile.TemporaryDirectory() as temp:
            result = write_freecad_bundle(self.project(), temp)
            self.assertTrue(Path(result["macro"]).is_file())
            self.assertTrue(Path(result["netlist"]).is_file())
            netlist = json.loads(Path(result["netlist"]).read_text())
            self.assertEqual(netlist["format"], "merlin-netlist-v1")
            self.assertEqual(netlist["nets"][0]["name"], "POWER")

    def test_invalid_project_is_rejected(self):
        invalid = EngineeringProject("bad", "inch", (), ())
        with self.assertRaises(ValueError):
            build_freecad_macro(invalid, "/tmp/bad.FCStd")


if __name__ == "__main__":
    unittest.main()
