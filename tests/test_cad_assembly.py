import unittest
from dataclasses import replace

from merlin.cad_assembly import (
    AssemblyComponent, CADAssembly, Transform3D, export_assembly_openscad,
    validate_assembly, validate_transform,
)
from merlin.engineering_ir import EngineeringProject, Part, Pin

def sample_project():
    return EngineeringProject(
        name="assembly-test", units="mm",
        parts=(
            Part("A1", "housing", (Pin("1", "mount"),), size_mm=(20, 20, 10)),
            Part("B1", "board", (Pin("1", "io"),), size_mm=(10, 10, 2)),
        ), nets=(),
    )

class CADAssemblyTests(unittest.TestCase):
    def test_identity_transform_is_valid(self):
        self.assertEqual(validate_transform(Transform3D()), ())

    def test_rejects_non_orthonormal_and_reflection_matrices(self):
        skew = Transform3D(rotation=(1, 0.2, 0, 0, 1, 0, 0, 0, 1))
        reflection = Transform3D(rotation=(-1, 0, 0, 0, 1, 0, 0, 0, 1))
        self.assertTrue(validate_transform(skew))
        self.assertIn("rotation matrix must have determinant +1",
                      validate_transform(reflection))

    def test_detects_conservative_aabb_interference(self):
        assembly = CADAssembly("overlap", (
            AssemblyComponent("A1", Transform3D(translation_mm=(0, 0, 0))),
            AssemblyComponent("B1", Transform3D(translation_mm=(2, 0, 0))),
        ))
        codes = {issue.code for issue in validate_assembly(sample_project(), assembly)}
        self.assertIn("AABB_INTERFERENCE", codes)

    def test_separated_components_do_not_interfere(self):
        assembly = CADAssembly("separated", (
            AssemblyComponent("A1"),
            AssemblyComponent("B1", Transform3D(translation_mm=(30, 0, 0))),
        ))
        codes = {issue.code for issue in validate_assembly(sample_project(), assembly)}
        self.assertNotIn("AABB_INTERFERENCE", codes)

    def test_rejects_unknown_parts_and_duplicate_components(self):
        assembly = CADAssembly("bad", (
            AssemblyComponent("A1"), AssemblyComponent("A1"), AssemblyComponent("MISSING"),
        ))
        codes = {issue.code for issue in validate_assembly(sample_project(), assembly)}
        self.assertIn("DUPLICATE_ASSEMBLY_COMPONENT", codes)
        self.assertIn("UNKNOWN_ASSEMBLY_PART", codes)

    def test_exports_transformed_openscad(self):
        assembly = CADAssembly("simple", (
            AssemblyComponent("A1", Transform3D(translation_mm=(4, 5, 6))),
        ))
        output = export_assembly_openscad(sample_project(), assembly)
        self.assertIn("multmatrix(", output)
        self.assertIn("cube([20, 20, 10]", output)

    def test_invalid_assembly_cannot_export(self):
        assembly = CADAssembly("invalid", (AssemblyComponent("missing"),))
        with self.assertRaises(ValueError):
            export_assembly_openscad(sample_project(), assembly)

if __name__ == "__main__":
    unittest.main()