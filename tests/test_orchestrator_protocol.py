"""Protocol smoke with a synthetic subprocess; no claim of real C++ integration."""
import pathlib
import tempfile
import unittest
import sys
import concurrent.futures
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python"))
from orchestrator import RuntimeProcess


class OrchestratorProtocolTests(unittest.TestCase):
    def worker(self, source, **options):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        script = pathlib.Path(folder.name) / "worker.py"
        script.write_text(source, encoding="utf-8")
        runtime = RuntimeProcess([sys.executable, "-I", "-u", str(script)], **options)
        self.addCleanup(runtime.close)
        return runtime

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

    def test_hung_response_has_deadline_and_stops_process(self):
        runtime = self.worker("import time\ntime.sleep(30)\n", request_timeout=0.1, shutdown_timeout=0.2)
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            runtime.request("controller", "health check")
        self.assertLess(time.monotonic() - start, 2)
        self.assertFalse(runtime.running)
        self.assertIsNotNone(runtime._proc.poll())
        with self.assertRaises(RuntimeError):
            runtime.request("controller", "next request")

    def test_full_input_pipe_is_also_bounded(self):
        runtime = self.worker("import time\ntime.sleep(30)\n", request_timeout=0.1, shutdown_timeout=0.2)
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            runtime.request("controller", "x" * 200000)
        self.assertLess(time.monotonic() - start, 2)
        self.assertIsNotNone(runtime._proc.poll())

    def test_oversized_response_without_newline_is_rejected(self):
        runtime = self.worker(
            "import sys,time\nsys.stdin.readline()\nsys.stdout.write('x'*10000);sys.stdout.flush()\ntime.sleep(30)\n",
            max_response_bytes=128,
        )
        with self.assertRaisesRegex(RuntimeError, "byte limit"):
            runtime.request("controller", "test")
        self.assertFalse(runtime.running)

    def test_invalid_response_types_fail_closed(self):
        for reply in ("[]", "{'id': x['id'], 'ok': 'true'}"):
            with self.subTest(reply=reply):
                runtime = self.worker(
                    "import sys,json\nx=json.loads(sys.stdin.readline())\nprint(json.dumps(" + reply + "),flush=True)\n"
                )
                with self.assertRaises(RuntimeError):
                    runtime.request("controller", "test")
                self.assertFalse(runtime.running)

    def test_concurrent_requests_preserve_identity(self):
        runtime = self.worker(
            "import sys,json\nfor line in sys.stdin:\n x=json.loads(line); print(json.dumps({'id':x['id'],'ok':True,'echo':x['task']}),flush=True)\n"
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            answers = list(pool.map(lambda i: runtime.request("controller", str(i))["echo"], range(12)))
        self.assertEqual(answers, [str(i) for i in range(12)])

    def test_request_limit_does_not_break_healthy_connection(self):
        runtime = self.worker(
            "import sys,json\nfor line in sys.stdin:\n x=json.loads(line); print(json.dumps({'id':x['id'],'ok':True}),flush=True)\n",
            max_request_bytes=256,
        )
        with self.assertRaisesRegex(ValueError, "byte limit"):
            runtime.request("controller", "x" * 300)
        self.assertTrue(runtime.request("controller", "health check")["ok"])

    def test_invalid_timeout_rejected_before_spawn(self):
        for value in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                RuntimeProcess([sys.executable, "-c", "pass"], request_timeout=value)

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

