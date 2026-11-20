"""Independent interpolation oracles and coverage/parser negatives."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / "scripts/merlin/measure_mesh_interpolation.py"
SPEC = importlib.util.spec_from_file_location("mesh_interpolation_measurement", PATH)
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


class MeshInterpolationTests(unittest.TestCase):
    def test_exact_vertex_budget_and_complete_non_square_row_counts(self):
        for count in (4, 5, 7, 10, 31, 64, 541):
            with self.subTest(count=count):
                vertices, triangles = BENCHMARK.near_uniform_mesh(count)
                _, result = BENCHMARK.validate_square_mesh(vertices, triangles)
                self.assertEqual(len(vertices), count)
                self.assertEqual(result["vertex_count"], count)
                self.assertEqual(result["triangle_components"], 1)
                self.assertAlmostEqual(result["summed_triangle_area"], 1)
                self.assertTrue(result["all_four_boundary_sides_covered"])

    def test_independent_quadratic_interpolation_oracle(self):
        vertices, triangles = BENCHMARK.near_uniform_mesh(4)
        # On either triangle, vertex x^2 values at x=0/1 interpolate as x.
        # At x=1/4 the exact error is 1/4-1/16=3/16, independent of reader output.
        with patch.object(BENCHMARK, "field", side_effect=lambda x, y: x * x):
            result = BENCHMARK.evaluate(vertices, triangles, [(0.25, 0.25)])
        self.assertEqual(result["metrics"]["rmse"], 3 / 16)
        self.assertLess(result["metrics"]["affine_control_max_absolute_error"], 1e-12)

    def test_hole_duplicate_and_unused_vertices_are_rejected(self):
        vertices, triangles = BENCHMARK.near_uniform_mesh(9)
        for points, faces in ((vertices, triangles[:-1]),
                              (vertices, triangles + triangles[:1]),
                              (vertices + [(0.1, 0.2)], triangles)):
            with self.subTest(faces=len(faces)), self.assertRaises(ValueError):
                BENCHMARK.validate_square_mesh(points, faces)

    def test_outside_and_invalid_connectivity_are_rejected(self):
        vertices, triangles = BENCHMARK.near_uniform_mesh(4)
        with self.assertRaises(ValueError):
            BENCHMARK.validate_square_mesh([(-.1, 0)] + vertices[1:], triangles)
        with self.assertRaises(ValueError):
            BENCHMARK.validate_square_mesh(vertices, [(0, 1, 50), triangles[1]])

    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.txt"
            path.write_text(text)
            return BENCHMARK.read_mesh(path)

    def test_medit_and_gmsh_noncontiguous_node_ids(self):
        medit = "MeshVersionFormatted 1\nDimension 2\nVertices 4\n0 0 1\n1 0 1\n0 1 1\n1 1 1\nTriangles 2\n1 2 3 1\n2 4 3 1\nEnd\n"
        gmsh = "$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$Nodes\n4\n10 0 0 0\n20 1 0 0\n30 0 1 0\n40 1 1 0\n$EndNodes\n$Elements\n2\n17 2 2 9 9 10 20 30\n18 2 0 20 40 30\n$EndElements\n"
        left = self.parse(medit)
        right = self.parse(gmsh)
        self.assertEqual(left[:2], right[:2])
        BENCHMARK.validate_square_mesh(*right[:2])
        with self.assertRaises(ValueError):
            self.parse(gmsh.replace("40 1 1 0", "40 1 1 1"))
        with self.assertRaises(ValueError):
            self.parse(gmsh.replace("20 40 30", "20 99 30"))

    def test_frozen_protocol_rejects_modified_bytes(self):
        result = BENCHMARK.load_protocol()
        self.assertEqual(len(result["samples"]), 4096)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "modified.json"
            path.write_text("{}")
            with patch.object(BENCHMARK, "PROTOCOL", path), self.assertRaises(ValueError):
                BENCHMARK.load_protocol()

    def test_structured_fallback_is_explicit_control_with_equal_error(self):
        report = BENCHMARK.measure(synthetic_vertices=49)
        self.assertEqual(report["candidate_origin"], "structured_synthetic_control_not_native")
        self.assertEqual(report["candidate_to_uniform_rmse_ratio"], 1)
        self.assertFalse(report["qualification"])
        self.assertFalse(report["promotion_authority"])

    def test_native_receipt_cannot_substitute_different_mesh_bytes(self):
        # Synthetic receipt exercises byte binding only, never runner authenticity.
        text = "MeshVersionFormatted 1\nDimension 2\nVertices 4\n0 0 1\n1 0 1\n0 1 1\n1 1 1\nTriangles 2\n1 2 3 1\n2 4 3 1\nEnd\n"
        receipt = {"schema": "merlin-refine-native-build/1",
            "source": {"commit": BENCHMARK.NATIVE_SOURCE_COMMIT}, "execution": {"exit_code": 0},
            "artifact_sha256": {"adapted.msh2": BENCHMARK.digest(text.encode())},
            "output": {"filename": "adapted.msh2", "vertices_from_native_log": 4,
                       "triangles_from_native_log": 2}, "qualification": False, "promotion_authority": False}
        with tempfile.TemporaryDirectory() as directory:
            mesh = Path(directory) / "synthetic.mesh"
            metadata = Path(directory) / "synthetic-receipt.json"
            mesh.write_text(text)
            metadata.write_text(json.dumps(receipt))
            result = BENCHMARK.measure(mesh, native_receipt=metadata)
            self.assertFalse(result["qualification"])
            receipt["artifact_sha256"]["adapted.msh2"] = "0" * 64
            metadata.write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):
                BENCHMARK.measure(mesh, native_receipt=metadata)


if __name__ == "__main__":
    unittest.main()
