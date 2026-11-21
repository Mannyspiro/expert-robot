"""Real subprocess faults using a synthetic worker, not C++ qualification."""
import json
import os
import subprocess
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python"))
from experimental_self_healing import EvidenceLedger
from runtime_supervisor import RuntimeSupervisor


WORKER = '''import json,sys,time,os
for line in sys.stdin:
    request=json.loads(line)
    task=request["task"]
    if task=="hang":
        time.sleep(30)
    if task=="crash":
        os._exit(17)
    answer={"id":request["id"],"ok":True}
    if task=="multiply 6 7":
        answer["result"]=6*7
    print(json.dumps(answer),flush=True)
'''


class RuntimeSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = pathlib.Path(self.folder.name)
        self.worker = self.root / "worker.py"
        self.worker.write_text(WORKER)
        self.ledger = EvidenceLedger(self.root / "recovery.jsonl")
        self.supervisor = self.make_supervisor()
        self.addCleanup(self.supervisor.close)

    def make_supervisor(self, verifier=None):
        return RuntimeSupervisor(
            [sys.executable, "-I", "-u", str(self.worker)], self.ledger,
            verification_request=("math", "multiply 6 7"),
            verify_response=verifier or (lambda response: response.get("result") == 42),
            request_timeout=0.15, shutdown_timeout=0.2,
        )

    def test_start_reference_check_and_real_process_crash_recovery(self):
        self.assertEqual(self.supervisor.ensure_healthy(sandbox=True), "recovered")
        first = self.supervisor.runtime
        with self.assertRaises(RuntimeError):
            self.supervisor.request("controller", "crash")
        self.assertIsNotNone(first._proc.poll())
        self.assertEqual(self.supervisor.ensure_healthy(sandbox=True), "recovered")
        self.assertNotEqual(first.pid, self.supervisor.runtime.pid)
        self.assertEqual(self.supervisor.request("math", "multiply 6 7")["result"], 42)
        self.assertEqual(self.ledger.pending_recoveries(), set())
        self.ledger.verify()

    def test_hang_stops_then_next_health_check_restarts(self):
        self.assertEqual(self.supervisor.ensure_healthy(sandbox=True), "recovered")
        old = self.supervisor.runtime
        with self.assertRaises(TimeoutError):
            self.supervisor.request("controller", "hang")
        self.assertFalse(old.running)
        self.assertEqual(self.supervisor.ensure_healthy(sandbox=True), "recovered")
        self.assertTrue(self.supervisor.status()["running"])

    def test_failed_independent_reference_rolls_back_to_stopped(self):
        supervisor = self.make_supervisor(verifier=lambda response: response.get("result") == 43)
        self.addCleanup(supervisor.close)
        self.assertEqual(supervisor.ensure_healthy(sandbox=True), "escalate")
        self.assertIsNone(supervisor.runtime)
        events = [json.loads(line)["event"] for line in self.ledger.path.read_text().splitlines()]
        self.assertIn("rolled_back", [event["state"] for event in events])
        self.assertNotIn("verified_recovery", [event["state"] for event in events])

    def test_restart_reuses_durable_history_without_replaying_tasks(self):
        self.assertEqual(self.supervisor.ensure_healthy(sandbox=True), "recovered")
        first_hash = self.ledger.verify()
        self.supervisor.close()
        restarted = self.make_supervisor()
        self.addCleanup(restarted.close)
        self.assertEqual(restarted.ensure_healthy(sandbox=True), "recovered")
        self.assertNotEqual(first_hash, self.ledger.verify())
        self.assertTrue(restarted.status()["running"])

    def test_interrupted_attempt_blocks_even_new_adapter(self):
        self.ledger.append({"subsystem": "cpp_runtime", "state": "repair_started"})
        for _ in range(2):
            restarted = self.make_supervisor()
            self.assertEqual(restarted.ensure_healthy(sandbox=True), "escalate")
            self.assertIsNone(restarted.runtime)
            self.assertTrue(restarted.status()["unresolved_recovery"])

    def test_no_attested_isolation_no_process(self):
        self.assertEqual(self.supervisor.ensure_healthy(), "blocked")
        self.assertIsNone(self.supervisor.runtime)


@unittest.skipUnless(os.environ.get("MERLIN_TEST_RUNTIME"), "set MERLIN_TEST_RUNTIME to the compiled C++ protocol runtime")
class NativeRuntimeSupervisorTests(unittest.TestCase):
    def test_cli_defaults_match_native_health_contract(self):
        result = subprocess.run(
            [sys.executable, str(pathlib.Path(__file__).resolve().parents[1] / "python/orchestrator.py"),
             "--runtime", os.environ["MERLIN_TEST_RUNTIME"], "--timeout", "2"],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"], "runtime protocol healthy")

    def test_native_protocol_crash_recovery_and_negative_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = EvidenceLedger(pathlib.Path(folder) / "native.jsonl")
            supervisor = RuntimeSupervisor(
                os.environ["MERLIN_TEST_RUNTIME"], ledger,
                verification_request=("controller", "reference negative control"),
                verify_response=lambda response: response.get("ok") is False
                and response.get("result") == ""
                and response.get("error") == "generic protocol runtime does not own model state; use expert_robot_research for bounded offline math research",
            )
            try:
                self.assertEqual(supervisor.ensure_healthy(sandbox=True), "recovered")
                old = supervisor.runtime
                self.assertEqual(supervisor.request("health", "check")["result"], "runtime protocol healthy")
                old._proc.kill()
                old._proc.wait(timeout=2)
                self.assertEqual(supervisor.ensure_healthy(sandbox=True), "recovered")
                self.assertNotEqual(old.pid, supervisor.runtime.pid)
                self.assertTrue(supervisor.request("health", "check")["ok"])
                self.assertEqual(EvidenceLedger(ledger.path).verify(), ledger.verify())
                self.assertEqual(ledger.pending_recoveries(), set())
            finally:
                supervisor.close()

    def test_native_rejected_reference_stops_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = EvidenceLedger(pathlib.Path(folder) / "native.jsonl")
            supervisor = RuntimeSupervisor(
                os.environ["MERLIN_TEST_RUNTIME"], ledger,
                verification_request=("health", "check"),
                verify_response=lambda response: response.get("result") == "invalid expected output",
            )
            try:
                self.assertEqual(supervisor.ensure_healthy(sandbox=True), "escalate")
                self.assertIsNone(supervisor.runtime)
                self.assertFalse(supervisor.status()["running"])
            finally:
                supervisor.close()


if __name__ == "__main__":
    unittest.main()
