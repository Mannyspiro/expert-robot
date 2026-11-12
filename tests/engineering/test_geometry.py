import unittest

from python.merlin.engineering.geometry import (
    GeometrySpec, Point3D, bounding_box, to_openscad, validate_geometry
)


class GeometryIRTests(unittest.TestCase):
    def tetrahedron(self):
        return GeometrySpec(
            name="tetrahedron", unit="cm",
            points=(
                Point3D("a", 0, 0, 0), Point3D("b", 1, 0, 0),
                Point3D("c", 0, 1, 0), Point3D("d", 0, 0, 1),
            ),
            faces=(("a", "c", "b"), ("a", "b", "d"), ("a", "d", "c"), ("b", "c", "d")),
            closed_solid=True,
        )

    def test_valid_closed_tetrahedron(self):
        self.assertEqual(validate_geometry(self.tetrahedron()), [])

    def test_unit_conversion_to_mm(self):
        box = bounding_box(self.tetrahedron())
        self.assertEqual(box["max_mm"], (10.0, 10.0, 10.0))

    def test_openscad_export(self):
        text = to_openscad(self.tetrahedron())
        self.assertIn("polyhedron(", text)
        self.assertIn("[10, 0, 0]", text)

    def test_unknown_vertex_is_rejected(self):
        spec = self.tetrahedron()
        bad = GeometrySpec(spec.name, spec.unit, spec.points, spec.faces + (("a", "b", "missing"),), False)
        self.assertIn("face.unknown_point", {i.code for i in validate_geometry(bad)})

    def test_non_manifold_closed_edge_is_rejected(self):
        spec = self.tetrahedron()
        bad = GeometrySpec(spec.name, spec.unit, spec.points, spec.faces[:-1], True)
        self.assertIn("mesh.non_manifold_edge", {i.code for i in validate_geometry(bad)})


if __name__ == "__main__":
    unittest.main()
