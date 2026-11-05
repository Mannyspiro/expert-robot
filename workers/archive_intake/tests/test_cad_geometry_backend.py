import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_geometry_backend import (
    GeometryContractError,
    canonical_sha,
    execute_job,
    validate_backend_receipt,
    validate_request,
)


class FixtureBackend:
    backend_id = "fixture-kernel"
    backend_version = "0.0-test"

    def execute(self, request, input_path, output_dir):
        output = output_dir / "topology.json"
        output.write_text('{"closed_shell":true}')
        return {
            "job_id": request["job_id"],
            "input_sha256": request["input_sha256"],
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "status": "completed",
            "artifacts": [{
                "path": "topology.json",
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }],
            "metrics": {"solid_count": 1},
            "limitations": ["fixture backend; not a CAD kernel"],
        }


class CadGeometryContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.output = self.root / "output"
        self.input = self.workspace / "part.step"
        self.input.write_text("ISO-10303-21; fixture only")
        self.request = {
            "contract_version": "1.0",
            "job_id": "geometry-test-1",
            "operation": "inspect",
            "input_path": "part.step",
            "input_sha256": hashlib.sha256(self.input.read_bytes()).hexdigest(),
            "input_format": "step",
            "units": {"length": "mm", "angle": "deg"},
            "coordinate_frame": {
                "frame_id": "part-local",
                "handedness": "right",
                "axis_convention": "x-right,y-up,z-out",
            },
            "requested_outputs": ["topology_report", "bounding_box"],
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_request_hash_and_frame_validate(self):
        _, path = validate_request(self.request, self.workspace)
        self.assertEqual(path, self.input.resolve())

    def test_declared_format_must_match_file_extension(self):
        self.request["input_format"] = "stl"
        with self.assertRaisesRegex(GeometryContractError, "does not match"):
            validate_request(self.request, self.workspace)

    def test_mesh_job_requires_explicit_positive_tolerances(self):
        self.request["operation"] = "tessellate"
        self.request["requested_outputs"] = ["mesh"]
        with self.assertRaisesRegex(GeometryContractError, "explicitly set"):
            validate_request(self.request, self.workspace)
        self.request["mesh_parameters"] = {
            "linear_deflection": 0.1,
            "angular_deflection": 0.5,
        }
        _, path = validate_request(self.request, self.workspace)
        self.assertEqual(path, self.input.resolve())

    def test_non_finite_mesh_tolerance_rejected(self):
        self.request["mesh_parameters"] = {
            "linear_deflection": float("inf"),
            "angular_deflection": 0.5,
        }
        with self.assertRaisesRegex(GeometryContractError, "finite positive"):
            validate_request(self.request, self.workspace)

    def test_input_digest_mismatch_rejected(self):
        self.request["input_sha256"] = "0" * 64
        with self.assertRaises(GeometryContractError):
            validate_request(self.request, self.workspace)

    def test_workspace_traversal_rejected(self):
        self.request["input_path"] = "../outside.step"
        with self.assertRaises((GeometryContractError, OSError)):
            validate_request(self.request, self.workspace)

    def test_backend_receipt_hashes_outputs(self):
        receipt = execute_job(self.request, self.workspace, self.output, FixtureBackend())
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["verification"],
                         "artifact_hashes_checked;geometry_correctness_not_independently_verified")
        self.assertEqual(receipt["receipt_sha256"], canonical_sha(receipt))

    def test_output_digest_mismatch_rejected(self):
        self.output.mkdir()
        out = self.output / "mesh.stl"
        out.write_text("mesh fixture")
        receipt = {
            "job_id": self.request["job_id"],
            "input_sha256": self.request["input_sha256"],
            "backend_id": "fixture-kernel",
            "backend_version": "0.0-test",
            "status": "completed",
            "artifacts": [{"path": "mesh.stl", "sha256": "0" * 64}],
        }
        with self.assertRaises(GeometryContractError):
            validate_backend_receipt(self.request, receipt, self.output,
                                     "fixture-kernel", "0.0-test")

    def test_output_traversal_rejected(self):
        self.output.mkdir()
        outside = self.root / "outside.stl"
        outside.write_text("not in output workspace")
        receipt = {
            "job_id": self.request["job_id"],
            "input_sha256": self.request["input_sha256"],
            "backend_id": "fixture-kernel",
            "backend_version": "0.0-test",
            "status": "completed",
            "artifacts": [{
                "path": "../outside.stl",
                "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
            }],
        }
        with self.assertRaises(GeometryContractError):
            validate_backend_receipt(self.request, receipt, self.output,
                                     "fixture-kernel", "0.0-test")


if __name__ == "__main__":
    unittest.main()
