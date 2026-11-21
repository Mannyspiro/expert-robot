"""Run: python -m unittest discover -s tests -p 'test_experimental_self_healing.py'"""
import json
import concurrent.futures
import multiprocessing
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from experimental_self_healing import EvidenceLedger, ExperimentalSupervisor, RecoveryPolicy
from experimental_fault_advisory import summarize_faults


def _append_in_process(path, count):
    ledger = EvidenceLedger(Path(path))
    for i in range(count):
        ledger.append({"worker_event": i})


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = EvidenceLedger(Path(self.temp.name) / "evidence.jsonl")
        self.supervisor = ExperimentalSupervisor(self.ledger)

    def states(self):
        return [json.loads(x)["event"]["state"] for x in self.ledger.path.read_text().splitlines()]

    def test_fault_repair_verified_and_persisted(self):
        state = {"healthy": False}
        result = self.supervisor.recover(
            "math", lambda: state["healthy"],
            lambda: state.update(healthy=True),
            lambda: state["healthy"], lambda: state.update(healthy=False), sandbox=True,
        )
        self.assertEqual(result, "recovered")
        self.assertIn("verified_recovery", self.states())
        self.assertEqual(EvidenceLedger(self.ledger.path).verify(), self.ledger.verify())

    def test_failed_verification_rolls_back(self):
        state = {"healthy": False, "rollback": False}
        result = self.supervisor.recover(
            "browser", lambda: state["healthy"],
            lambda: state.update(healthy=True), lambda: False,
            lambda: state.update(healthy=False, rollback=True), sandbox=True,
        )
        self.assertEqual(result, "escalate")
        self.assertTrue(state["rollback"])
        self.assertIn("rolled_back", self.states())

    def test_no_production_repair(self):
        called = []
        result = self.supervisor.recover(
            "core", lambda: False, lambda: called.append("repair"),
            lambda: True, lambda: None,
        )
        self.assertEqual(result, "blocked")
        self.assertEqual(called, [])

    def test_tampered_evidence_detected(self):
        self.ledger.append({"state": "healthy"})
        self.ledger.path.write_text(self.ledger.path.read_text().replace("healthy", "unhealthy"))
        with self.assertRaises(ValueError):
            self.ledger.verify()

    def test_zero_repair_budget(self):
        supervisor = ExperimentalSupervisor(self.ledger, RecoveryPolicy(max_repairs=0))
        self.assertEqual(supervisor.recover("cad", lambda: False, lambda: None, lambda: True, lambda: None, sandbox=True), "escalate")

    def test_non_boolean_verifier_cannot_approve_recovery(self):
        state = {"healthy": False}
        result = self.supervisor.recover(
            "browser", lambda: state["healthy"],
            lambda: state.update(healthy=True), lambda: "healthy",
            lambda: state.update(healthy=False), sandbox=True,
        )
        self.assertEqual(result, "escalate")
        self.assertFalse(state["healthy"])

    def test_fault_advisory_never_authorizes_repair(self):
        events = [{"subsystem": "browser", "state": "probe_error"}] * 3
        alerts = summarize_faults(events)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].action, "investigate_recurrence")
        self.assertEqual(summarize_faults(events[:2]), [])

    def test_multiprocess_writers_preserve_chain(self):
        ctx = multiprocessing.get_context("spawn")
        workers = [
            ctx.Process(target=_append_in_process, args=(str(self.ledger.path), 10))
            for _ in range(3)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=20)
            if worker.is_alive():
                worker.terminate()
                worker.join()
                self.fail("ledger writer stalled")
            self.assertEqual(worker.exitcode, 0)
        self.assertEqual(len(self.ledger.path.read_text().splitlines()), 30)
        self.assertEqual(len(self.ledger.verify()), 64)

    def test_threaded_evidence_writers_preserve_chain(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda i: self.ledger.append({"index": i}), range(40)))
        self.assertEqual(len(self.ledger.path.read_text().splitlines()), 40)
        self.assertEqual(len(self.ledger.verify()), 64)

    def test_interrupted_repair_is_not_replayed_automatically(self):
        self.ledger.append({"subsystem": "browser", "state": "repair_started", "attempt": 1})
        self.assertEqual(EvidenceLedger(self.ledger.path).pending_recoveries(), {"browser"})
        calls = []
        result = self.supervisor.recover(
            "browser", lambda: False, lambda: calls.append("repair"),
            lambda: True, lambda: None, sandbox=True,
        )
        self.assertEqual(result, "escalate")
        self.assertEqual(calls, [])

    def test_completed_repair_clears_pending_state(self):
        self.ledger.append({"subsystem": "math", "state": "repair_started"})
        self.ledger.append({"subsystem": "math", "state": "verified_recovery"})
        self.assertEqual(self.ledger.pending_recoveries(), set())

    def test_restart_reads_previous_evidence(self):
        first = self.ledger.append({"state": "fault_detected"})
        restarted = EvidenceLedger(self.ledger.path)
        second = restarted.append({"state": "escalate"})
        self.assertEqual(second["previous_hash"], first["hash"])
        self.assertEqual(restarted.verify(), second["hash"])

    def test_healthy_component_never_repaired(self):
        called = []
        result = self.supervisor.recover(
            "research", lambda: True, lambda: called.append("repair"),
            lambda: True, lambda: None, sandbox=True,
        )
        self.assertEqual(result, "healthy")
        self.assertEqual(called, [])

    def test_rollback_failure_escalates(self):
        def fail():
            raise RuntimeError("rollback failure")
        result = self.supervisor.recover(
            "models", lambda: False, lambda: None, lambda: False,
            fail, sandbox=True,
        )
        self.assertEqual(result, "escalate")
        self.assertIn("rollback_failed", self.states())

    def test_probe_exception_is_recorded(self):
        def bad_probe():
            raise OSError("probe unavailable")
        result = self.supervisor.recover(
            "memory", bad_probe, lambda: None, lambda: False,
            lambda: None, sandbox=True,
        )
        self.assertEqual(result, "escalate")
        self.assertIn("probe_error", self.states())
        self.assertNotIn("verified_recovery", self.states())

    def test_same_callable_rejected_as_independent_verifier(self):
        state = {"healthy": False}
        def probe():
            return state["healthy"]
        result = self.supervisor.recover(
            "cad", probe, lambda: state.update(healthy=True),
            probe, lambda: state.update(healthy=False), sandbox=True,
        )
        self.assertEqual(result, "escalate")
        self.assertFalse(state["healthy"])


if __name__ == "__main__":
    unittest.main()
