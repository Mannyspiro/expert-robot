import unittest

from merlin.engineering_ir import (
    EngineeringProject, Net, Part, Pin, export_netlist, export_openscad,
    export_spice_netlist, validate_project,
)


def sample():
    return EngineeringProject(
        name="bench-controller",
        units="mm",
        parts=(
            Part("U1", "controller", (
                Pin("1", "VCC", max_voltage_v=5.5, max_current_a=0.5),
                Pin("2", "GND", max_voltage_v=5.5, max_current_a=0.5),
            ), size_mm=(20, 15, 2), position_mm=(0, 0, 1)),
            Part("J1", "power connector", (
                Pin("1", "5V", max_voltage_v=5.5, max_current_a=1.0),
                Pin("2", "GND", max_voltage_v=5.5, max_current_a=1.0),
            )),
        ),
        nets=(
            Net("VCC_5V", ("U1.1", "J1.1"), nominal_voltage_v=5.0, max_current_a=0.25, net_class="power"),
            Net("GND", ("U1.2", "J1.2"), nominal_voltage_v=0.0, max_current_a=0.25, net_class="return"),
        ),
    )


class EngineeringIRTests(unittest.TestCase):
    def test_valid_project_exports_netlist_and_openscad(self):
        project = sample()
        self.assertEqual(validate_project(project), ())
        self.assertEqual(export_netlist(project)["format"], "merlin-netlist-v1")
        scad = export_openscad(project)
        self.assertIn("cube(size, center=true)", scad)
        self.assertIn("U1: controller", scad)

    def test_detects_unknown_endpoint_and_pin_assigned_twice(self):
        project = sample()
        bad = EngineeringProject(
            project.name, project.units, project.parts,
            project.nets + (
                Net("BAD", ("U1.1", "NOPE.1"), nominal_voltage_v=3.3),
            ),
        )
        codes = {issue.code for issue in validate_project(bad)}
        self.assertIn("UNKNOWN_ENDPOINT", codes)
        self.assertIn("PIN_ON_MULTIPLE_NETS", codes)

    def test_detects_voltage_and_current_rating_exceedance(self):
        project = sample()
        bad = EngineeringProject(
            project.name, project.units, project.parts,
            (Net("OVER", ("U1.1", "J1.1"), nominal_voltage_v=12.0, max_current_a=2.0),),
        )
        codes = {issue.code for issue in validate_project(bad)}
        self.assertIn("PIN_VOLTAGE_EXCEEDED", codes)
        self.assertIn("PIN_CURRENT_EXCEEDED", codes)

    def test_explicit_component_specs_export_deterministic_spice_netlist(self):
        project = EngineeringProject(
            "divider", "mm",
            parts=(
                Part("V1", "supply", (Pin("1", "positive"), Pin("2", "negative"))),
                Part("R1", "upper resistor", (Pin("1", "input"), Pin("2", "output"))),
                Part("R2", "lower resistor", (Pin("1", "input"), Pin("2", "return"))),
            ),
            nets=(
                Net("SUPPLY", ("V1.1", "R1.1"), nominal_voltage_v=5.0),
                Net("MID", ("R1.2", "R2.1"), nominal_voltage_v=2.5),
                Net("GND", ("V1.2", "R2.2"), nominal_voltage_v=0.0),
            ),
        )
        output = export_spice_netlist(
            project,
            {"V1": {"kind": "V", "value": "5"},
             "R1": {"kind": "R", "value": "1k"},
             "R2": {"kind": "R", "value": "1k"}},
            ground_net="GND",
            measure_nets=("MID",),
        )
        self.assertIn("R1 SUPPLY MID 1k\\n", output)
        self.assertIn("R2 MID 0 1k\\n", output)
        self.assertIn("V1 SUPPLY 0 DC 5\\n", output)
        self.assertIn("* requested operating-point voltage: MID\\n", output)
        self.assertNotIn(".meas", output)
        self.assertTrue(output.endswith(".end\\n"))

    def test_spice_export_rejects_injected_values_and_unknown_refs(self):
        project = EngineeringProject(
            "divider", "mm",
            parts=(Part("R1", "resistor", (Pin("1", "a"), Pin("2", "b"))),),
            nets=(Net("A", ("R1.1", "R1.2")),),
        )
        with self.assertRaisesRegex(ValueError, "invalid SPICE value"):
            export_spice_netlist(project, {"R1": {"kind": "R", "value": "1k\\n.shell"}},
                                 ground_net="A")
        with self.assertRaisesRegex(ValueError, "unknown part references"):
            export_spice_netlist(project, {"R9": {"kind": "R", "value": "1k"}},
                                 ground_net="A")

    def test_invalid_projects_cannot_export(self):
        project = sample()
        bad = EngineeringProject(
            project.name, project.units, project.parts,
            (Net("BROKEN", ("U1.1", "MISSING.1")),),
        )
        with self.assertRaises(ValueError):
            export_netlist(bad)


if __name__ == "__main__":
    unittest.main()
