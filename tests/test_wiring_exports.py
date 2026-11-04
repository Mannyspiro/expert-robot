import unittest

from merlin.engineering_ir import EngineeringProject, Net, Part, Pin
from merlin.physical_connectivity import physical_netlist
from merlin.wiring_exports import (
    export_schematic_manifest, export_wiring_graph_dot, export_wiring_schedule_csv,
)


class WiringExportTests(unittest.TestCase):
    def setUp(self):
        self.project = EngineeringProject(
            "export-test", "mm",
            (
                Part("J1", "input", (Pin("1", "OUT", position_mm=(0, 0, 0)),)),
                Part("J2", "output", (Pin("1", "IN", position_mm=(0, 0, 0)),)),
            ),
            (Net("SIGNAL", ("J1.1", "J2.1"), 5.0, 0.1, "signal"),),
        )
        from merlin.cad_assembly import AssemblyComponent, CADAssembly, Transform3D
        self.assembly = CADAssembly(
            "export-assembly",
            (AssemblyComponent("J1"), AssemblyComponent("J2", Transform3D(translation_mm=(20, 0, 0)))),
        )
        self.physical = physical_netlist(self.project, self.assembly)

    def test_graph_dot_is_labelled_as_non_release(self):
        dot = export_wiring_graph_dot(self.project, self.physical)
        self.assertIn("NOT A RELEASE SCHEMATIC", dot)
        self.assertIn('"J1.1" -- "J2.1"', dot)

    def test_schedule_does_not_invent_wire_spec(self):
        schedule = export_wiring_schedule_csv(self.project, self.physical)
        self.assertIn("NOT_SPECIFIED", schedule)
        self.assertIn("SIGNAL", schedule)

    def test_manifest_retains_missing_geometry_and_limits(self):
        manifest = export_schematic_manifest(self.project, self.physical)
        self.assertEqual(manifest["wire_specification"], "NOT_SPECIFIED")
        self.assertEqual(manifest["artifact_status"],
                         "LOGICAL_SCHEMATIC_AND_ROUTE_PROPOSALS_NOT_RELEASE_DOCUMENTS")
        self.assertIsNotNone(manifest["parts"][0]["pins"][0]["position_mm"])

    def test_dot_export_escapes_user_supplied_labels(self):
        from dataclasses import replace
        from merlin.engineering_ir import Pin, Part
        project = replace(
            self.project,
            parts=(
                Part("J1", 'input "quoted"', (Pin("1", 'OUT\\n"quoted"', position_mm=(0, 0, 0)),)),
                self.project.parts[1],
            ),
        )
        physical = physical_netlist(project, self.assembly)
        dot = export_wiring_graph_dot(project, physical)
        import json
        expected = json.dumps('J1.1\\nOUT\\n"quoted"', ensure_ascii=False)
        self.assertIn(expected, dot)

    def test_unknown_physical_netlist_rejected(self):
        with self.assertRaises(ValueError):
            export_schematic_manifest(self.project, {"format": "wrong"})


if __name__ == "__main__":
    unittest.main()
