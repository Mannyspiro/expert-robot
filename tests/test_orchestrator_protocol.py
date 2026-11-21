"""Protocol smoke with a synthetic subprocess; no claim of real C++ integration."""
import pathlib
import tempfile
import unittest
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python"))
from orchestrator import RuntimeProcess


class OrchestratorProtocolTests(unittest.TestCase):
    def test_request_response_correlation(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = pathlib.Path(folder) / "fake_runtime"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import sys,json\n"
                "for line in sys.stdin:\n"
                " x=json.loads(line); print(json.dumps({'id':x['id'],'ok':True,'role':x['role']}),flush=True)\n"
            )
            fake.chmod(0o755)
            runtime = RuntimeProcess(str(fake))
            try:
                response = runtime.request("controller", "health check")
                self.assertTrue(response["ok"])
                self.assertEqual(response["role"], "controller")
            finally:
                runtime.close()

    def test_mismatched_response_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = pathlib.Path(folder) / "fake_runtime"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import sys,json\n"
                "for line in sys.stdin:\n"
                " print(json.dumps({'id':'wrong','ok':True}),flush=True)\n"
            )
            fake.chmod(0o755)
            runtime = RuntimeProcess(str(fake))
            try:
                with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                    runtime.request("controller", "health check")
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()
