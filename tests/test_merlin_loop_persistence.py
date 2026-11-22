"""Persistence round-trip and fail-closed restart tests."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python"))
from experimental_self_healing import EvidenceLedger
from merlin_loop_coordinator import Loop, LoopCoordinator
from merlin_loop_persistence import checkpoint, restore


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = EvidenceLedger(pathlib.Path(self.tmp.name) / "events.jsonl")

    def test_round_trip_and_plan_isolation(self):
        c = LoopCoordinator()
        c.add(Loop("root", "plan"))
        c.start("root")
        c.add(Loop("child", "research", parent="root"))
        c.start("child")
        c.finish("child", passed=True, evidence="receipt:1")
        c.finish("root", passed=True, evidence="receipt:2")
        checkpoint(c, self.ledger, plan_id="p1")
        self.assertEqual(restore(self.ledger, plan_id="p1").snapshot(), c.snapshot())
        self.assertEqual(restore(self.ledger, plan_id="p2").snapshot(), {})

    def test_running_blocked_after_restart(self):
        c = LoopCoordinator()
        c.add(Loop("root", "plan"))
        c.start("root")
        checkpoint(c, self.ledger, plan_id="p")
        restored = restore(self.ledger, plan_id="p")
        self.assertEqual(restored.loops["root"].state, "blocked")
        self.assertIn("interrupted_execution_requires_review", restored.loops["root"].evidence)
        with self.assertRaises(ValueError):
            restored.start("root")

    def test_restart_from_separate_process(self):
        c = LoopCoordinator()
        c.add(Loop("root", "plan"))
        c.start("root")
        c.add(Loop("child", "research", parent="root"))
        c.start("child")
        checkpoint(c, self.ledger, plan_id="p")
        script = (
            "import pathlib, sys; "
            "sys.path.insert(0, sys.argv[2]); "
            "from experimental_self_healing import EvidenceLedger; "
            "from merlin_loop_persistence import restore; "
            "c = restore(EvidenceLedger(pathlib.Path(sys.argv[1])), plan_id='p'); "
            "assert c.loops['root'].state == 'blocked'; "
            "assert c.loops['child'].state == 'blocked'"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script, str(self.ledger.path),
             str(pathlib.Path(__file__).resolve().parents[1] / "python")],
            capture_output=True, text=True, timeout=15, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_latest_checkpoint_wins(self):
        c = LoopCoordinator()
        c.add(Loop("root", "plan"))
        checkpoint(c, self.ledger, plan_id="p")
        c.start("root")
        c.finish("root", passed=True, evidence="receipt")
        checkpoint(c, self.ledger, plan_id="p")
        self.assertEqual(restore(self.ledger, plan_id="p").loops["root"].state, "passed")

    def test_tampering_rejected(self):
        c = LoopCoordinator()
        checkpoint(c, self.ledger, plan_id="p")
        self.ledger.path.write_text(self.ledger.path.read_text().replace('"checkpoint"', '"compromised"'))
        with self.assertRaises(ValueError):
            restore(self.ledger, plan_id="p")

    def test_interrupted_parent_and_child_restore_blocked(self):
        c = LoopCoordinator()
        c.add(Loop("root", "plan"))
        c.start("root")
        c.add(Loop("child", "research", parent="root"))
        c.start("child")
        checkpoint(c, self.ledger, plan_id="p")
        restored = restore(self.ledger, plan_id="p")
        self.assertEqual(restored.loops["root"].state, "blocked")
        self.assertEqual(restored.loops["child"].state, "blocked")

    def test_passed_parent_with_incomplete_child_rejected(self):
        self.ledger.append({"subsystem": "merlin_loop_coordinator", "state": "checkpoint",
                            "schema": "merlin-loop-checkpoint/1", "plan_id": "p", "max_depth": 3,
                            "loops": {
                                "root": {"kind": "plan", "parent": None, "dependencies": [],
                                         "budget": 1, "state": "passed", "attempts": 1,
                                         "evidence": ["receipt"]},
                                "child": {"kind": "research", "parent": "root", "dependencies": [],
                                          "budget": 1, "state": "pending", "attempts": 0,
                                          "evidence": []}}})
        with self.assertRaises(ValueError):
            restore(self.ledger, plan_id="p")

    def test_blocked_checkpoint_requires_reason(self):
        self.ledger.append({"subsystem": "merlin_loop_coordinator", "state": "checkpoint",
                            "schema": "merlin-loop-checkpoint/1", "plan_id": "p", "max_depth": 3,
                            "loops": {"root": {"kind": "plan", "parent": None,
                                                "dependencies": [], "budget": 1,
                                                "state": "blocked", "attempts": 0,
                                                "evidence": []}}})
        with self.assertRaises(ValueError):
            restore(self.ledger, plan_id="p")

    def test_retried_pending_checkpoint_requires_failure_evidence(self):
        self.ledger.append({"subsystem": "merlin_loop_coordinator", "state": "checkpoint",
                            "schema": "merlin-loop-checkpoint/1", "plan_id": "p", "max_depth": 3,
                            "loops": {"root": {"kind": "research", "parent": None,
                                                "dependencies": [], "budget": 2,
                                                "state": "pending", "attempts": 1,
                                                "evidence": []}}})
        with self.assertRaises(ValueError):
            restore(self.ledger, plan_id="p")

    def test_missing_dependency_fails_closed(self):
        self.ledger.append({"subsystem": "merlin_loop_coordinator", "state": "checkpoint",
                            "schema": "merlin-loop-checkpoint/1", "plan_id": "p", "max_depth": 3,
                            "loops": {"child": {"kind": "research", "parent": "missing",
                                                "dependencies": [], "budget": 1,
                                                "state": "pending", "attempts": 0, "evidence": []}}})
        with self.assertRaises(ValueError):
            restore(self.ledger, plan_id="p")


if __name__ == "__main__":
    unittest.main()
