import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

RUNTIME = Path(__file__).resolve().parents[1] / "freecad-runtime"
sys.path.insert(0, str(RUNTIME))
from run_geometry_job import run_request


class FakeBackend:
    backend_id = "fixture"
    backend_version = "1.0"

    def execute(self, request, input_path, output_dir):
        output = output_dir / "report.json"
        output.write_text('{"fixture":true}\n', encoding="utf-8")
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        return {
            "job_id": request["job_id"],
            "input_sha256": request["input_sha256"],
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "status": "completed",
            "artifacts": [{"path": output.name, "sha256": digest}],
            "metrics": {},
            "limitations": ["fixture backend only"],
        }


class FreeCADJobRunnerTests(unittest.TestCase):
    def _fixture(self, root):
        input_root = root / "input"
        output_root = root / "output"
        input_root.mkdir()
        cad = input_root / "part.step"
        cad.write_bytes(b"public fixture bytes")
        digest = hashlib.sha256(cad.read_bytes()).hexdigest()
        request = {
            "contract_version": "1.0",
            "job_id": "fixture-001",
            "operation": "inspect",
            "input_path": "part.step",
            "input_sha256": digest,
            "input_format": "step",
            "units": {"length": "mm", "angle": "deg"},
            "coordinate_frame": {
                "frame_id": "fixture-world",
                "handedness": "right",
                "axis_convention": "X-right,Y-up,Z-out",
            },
            "requested_outputs": ["topology_report"],
        }
        request_path = input_root / "job.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        return input_root, output_root, request_path

    def test_runs_hash_bound_job_and_writes_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs, outputs, request = self._fixture(root)
            receipt = run_request(request, inputs, outputs, backend_factory=FakeBackend)
            saved = json.loads((outputs / "geometry-receipt.json").read_text())
            self.assertEqual(saved["receipt_sha256"], receipt["receipt_sha256"])
            self.assertEqual(saved["status"], "completed")
            self.assertEqual(len(saved["artifacts"]), 1)

    def test_rejects_nested_input_output_workspaces(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs, _, request = self._fixture(root)
            with self.assertRaisesRegex(ValueError, "separate"):
                run_request(request, inputs, inputs / "outputs", backend_factory=FakeBackend)

    def test_rejects_modified_input_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs, outputs, request = self._fixture(root)
            (inputs / "part.step").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "digest"):
                run_request(request, inputs, outputs, backend_factory=FakeBackend)


if __name__ == "__main__":
    unittest.main()
