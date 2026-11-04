import unittest

from merlin.cad_assembly import AssemblyComponent, CADAssembly, Transform3D, validate_assembly, export_assembly_openscad
from merlin.coordinate_frames import CoordinateFrame, compose, inverse, resolve_frames, transform_point
from merlin.engineering_ir import EngineeringProject, Part, Pin


class CoordinateFrameTests(unittest.TestCase):
    def test_nested_translation_frames_resolve_to_world(self):
        frames = (
            CoordinateFrame("root", None, Transform3D(translation_mm=(10, 0, 0))),
            CoordinateFrame("tool", "root", Transform3D(translation_mm=(0, 5, 0))),
        )
        resolved = resolve_frames(frames)
        self.assertEqual(resolved["tool"].translation_mm, (10, 5, 0))

    def test_rotation_then_translation_composition(self):
        quarter_turn = Transform3D(rotation=(0, -1, 0, 1, 0, 0, 0, 0, 1))
        translated = Transform3D(translation_mm=(2, 0, 0))
        result = compose(quarter_turn, translated)
        self.assertEqual(result.translation_mm, (0, 2, 0))

    def test_inverse_round_trip(self):
        transform = Transform3D(translation_mm=(3, -2, 7))
        point = (4, 5, 6)
        world = transform_point(transform, point)
        restored = transform_point(inverse(transform), world)
        for actual, expected in zip(restored, point):
            self.assertAlmostEqual(actual, expected)

    def test_rejects_missing_parent_and_cycles(self):
        with self.assertRaisesRegex(ValueError, "unknown parent"):
            resolve_frames((CoordinateFrame("child", "missing"),))
        with self.assertRaisesRegex(ValueError, "cycle"):
            resolve_frames((CoordinateFrame("a", "b"), CoordinateFrame("b", "a")))

    def test_rejects_duplicate_frame_ids(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            resolve_frames((CoordinateFrame("same"), CoordinateFrame("same")))

    def test_assembly_uses_frame_and_part_local_position(self):
        project = EngineeringProject(
            "frame-test", "mm",
            (Part("P1", "part", (Pin("1", "p"),), size_mm=(2, 2, 2),
                  position_mm=(1, 0, 0)),), (),
        )
        assembly = CADAssembly(
            "nested",
            (AssemblyComponent("P1", Transform3D(translation_mm=(0, 2, 0)), "tool"),),
            frames=(CoordinateFrame("root", None, Transform3D(translation_mm=(10, 0, 0))),
                    CoordinateFrame("tool", "root", Transform3D(translation_mm=(0, 5, 0)))),
        )
        output = export_assembly_openscad(project, assembly)
        self.assertIn("[[1.0,0.0,0.0,11.0],[0.0,1.0,0.0,7.0]", output)

    def test_invalid_frame_graph_blocks_export(self):
        project = EngineeringProject("bad-frame", "mm",
            (Part("P1", "part", (Pin("1", "p"),)),), ())
        assembly = CADAssembly("bad", (AssemblyComponent("P1", frame_id="missing"),))
        with self.assertRaises(ValueError):
            export_assembly_openscad(project, assembly)

    def test_frame_graph_error_is_reported_by_validator(self):
        project = EngineeringProject("bad-frame", "mm",
            (Part("P1", "part", (Pin("1", "p"),)),), ())
        assembly = CADAssembly("bad", (AssemblyComponent("P1", frame_id="missing"),))
        codes = {issue.code for issue in validate_assembly(project, assembly)}
        self.assertIn("INVALID_FRAME_GRAPH", codes)


if __name__ == "__main__":
    unittest.main()
