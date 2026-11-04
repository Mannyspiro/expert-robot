import unittest

from merlin.cad_assembly import AssemblyComponent, CADAssembly, Transform3D
from merlin.coordinate_frames import CoordinateFrame
from merlin.engineering_ir import EngineeringProject, Net, Part, Pin
from merlin.physical_connectivity import physical_netlist


class PhysicalConnectivityTests(unittest.TestCase):
    def test_net_endpoints_resolve_through_frame_component_part_and_pin(self):
        project = EngineeringProject(
            "physical", "mm",
            (
                Part("J1", "connector", (
                    Pin("1", "VCC", position_mm=(3, 0, 0), direction=(1, 0, 0)),
                    Pin("2", "GND", position_mm=(0, 2, 0)),
                ), position_mm=(1, 0, 0)),
            ),
            (Net("POWER", ("J1.1", "J1.2"), nominal_voltage_v=5.0),),
        )
        assembly = CADAssembly(
            "enclosure",
            (AssemblyComponent("J1", Transform3D(translation_mm=(2, 0, 0)), "board"),),
            frames=(CoordinateFrame("board", None, Transform3D(translation_mm=(10, 0, 0))),),
        )
        result = physical_netlist(project, assembly)
        pins = {item["endpoint"]: item for item in result["nets"][0]["endpoints"]}
        self.assertEqual(pins["J1.1"]["position_mm"], [16, 0, 0])
        self.assertEqual(pins["J1.1"]["direction"], [1, 0, 0])
        self.assertEqual(pins["J1.2"]["position_mm"], [13, 2, 0])
        self.assertEqual(pins["J1.2"]["status"], "position_only")
        self.assertEqual(result["nets"][0]["route_geometry_status"], "not_generated")

    def test_rotation_applies_to_pin_direction(self):
        project = EngineeringProject(
            "rotation", "mm",
            (Part("P1", "part", (
                Pin("1", "signal", position_mm=(1, 0, 0), direction=(1, 0, 0)),
                Pin("2", "return", position_mm=(0, 1, 0), direction=(0, 1, 0)),
            )),),
            (Net("N", ("P1.1", "P1.2")),),
        )
        rotation = Transform3D(rotation=(0, -1, 0, 1, 0, 0, 0, 0, 1))
        result = physical_netlist(project, CADAssembly(
            "rotated", (AssemblyComponent("P1", rotation),)
        ))
        pins = {item["endpoint"]: item for item in result["nets"][0]["endpoints"]}
        self.assertEqual(pins["P1.1"]["position_mm"], [0, 1, 0])
        self.assertEqual(pins["P1.1"]["direction"], [0, 1, 0])
        self.assertEqual(pins["P1.2"]["direction"], [-1, 0, 0])

    def test_missing_physical_geometry_is_explicit(self):
        project = EngineeringProject(
            "missing", "mm",
            (Part("P1", "part", (Pin("1", "signal"), Pin("2", "return"))),),
            (Net("N", ("P1.1", "P1.2")),),
        )
        result = physical_netlist(project, CADAssembly(
            "assembly", (AssemblyComponent("P1"),)
        ))
        self.assertTrue(all(item["status"] == "missing_physical_pin_geometry"
                            for item in result["nets"][0]["endpoints"]))

    def test_pin_geometry_validation_rejects_non_finite_and_non_unit_values(self):
        project = EngineeringProject(
            "invalid", "mm",
            (Part("P1", "part", (
                Pin("1", "bad-position", position_mm=(float("nan"), 0, 0)),
                Pin("2", "bad-direction", direction=(2, 0, 0)),
            )),), (),
        )
        from merlin.engineering_ir import validate_project
        codes = {issue.code for issue in validate_project(project)}
        self.assertIn("INVALID_PIN_POSITION", codes)
        self.assertIn("INVALID_PIN_DIRECTION", codes)


if __name__ == "__main__":
    unittest.main()
