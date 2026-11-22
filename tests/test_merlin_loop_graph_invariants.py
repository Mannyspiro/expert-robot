"""Negative controls for Merlin's loop graph and restart invariants."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python"))
from experimental_self_healing import EvidenceLedger
from merlin_loop_coordinator import Loop, LoopCoordinator
from merlin_loop_persistence import checkpoint, restore as restore_checkpoint


def record(*, kind="research", parent=None, dependencies=(), budget=1,
           state="pending", attempts=0, evidence=()):
    return {"kind": kind, "parent": parent, "dependencies": list(dependencies),
            "budget": budget, "state": state, "attempts": attempts,
            "evidence": list(evidence)}


class RestoreGraphInvariantTests(unittest.TestCase):
    def _both_restore_paths_reject(self, loops):
        with self.subTest(reader="snapshot"):
            with self.assertRaises(ValueError):
                LoopCoordinator.restore(loops)
        with self.subTest(reader="hash_linked_ledger"):
            with tempfile.TemporaryDirectory() as temp:
                ledger = EvidenceLedger(pathlib.Path(temp) / "evidence.jsonl")
                ledger.append({"subsystem": "merlin_loop_coordinator",
                               "state": "checkpoint", "schema": "merlin-loop-checkpoint/1",
                               "plan_id": "proof", "max_depth": 3, "loops": loops})
                with self.assertRaises(ValueError):
                    restore_checkpoint(ledger, plan_id="proof")

    def test_passed_task_cannot_depend_on_failed_task(self):
        self._both_restore_paths_reject({
            "source": record(state="failed", attempts=1, evidence=("failure:source",)),
            "candidate": record(dependencies=("source",), state="passed",
                                attempts=1, evidence=("claimed:success",)),
        })

    def test_passed_parent_requires_passed_children(self):
        self._both_restore_paths_reject({
            "plan": record(kind="plan", state="passed", attempts=1,
                           evidence=("claimed:complete",)),
            "child": record(parent="plan"),
        })

    def test_running_child_requires_running_parent(self):
        self._both_restore_paths_reject({
            "plan": record(kind="plan"),
            "child": record(parent="plan", state="running", attempts=1),
        })

    def test_running_requires_attempt(self):
        self._both_restore_paths_reject({"task": record(state="running", attempts=0)})

    def test_terminal_evidence_required(self):
        for state, attempts in (("passed", 1), ("failed", 1), ("blocked", 0)):
            with self.subTest(state=state):
                self._both_restore_paths_reject({"task": record(state=state, attempts=attempts)})

    def test_pending_retry_requires_failure_evidence(self):
        self._both_restore_paths_reject({"task": record(budget=2, attempts=1)})

    def test_child_cannot_depend_on_ancestor(self):
        c = LoopCoordinator()
        c.add(Loop("plan", "plan"))
        with self.assertRaises(ValueError):
            c.add(Loop("child", "research", parent="plan", dependencies=("plan",)))

    def test_completed_parent_child_round_trip(self):
        c = LoopCoordinator()
        c.add(Loop("plan", "plan"))
        c.start("plan")
        c.add(Loop("child", "research", parent="plan"))
        c.start("child")
        c.finish("child", passed=True, evidence="receipt:child")
        c.finish("plan", passed=True, evidence="receipt:plan")
        self.assertEqual(LoopCoordinator.restore(c.snapshot()).snapshot(), c.snapshot())
        with tempfile.TemporaryDirectory() as temp:
            ledger = EvidenceLedger(pathlib.Path(temp) / "evidence.jsonl")
            checkpoint(c, ledger, plan_id="proof")
            self.assertEqual(restore_checkpoint(ledger, plan_id="proof").snapshot(), c.snapshot())

    def test_passed_dependency_valid_next_task(self):
        c = LoopCoordinator()
        c.add(Loop("source", "research"))
        c.start("source")
        c.finish("source", passed=True, evidence="receipt:source")
        c.add(Loop("next", "research", dependencies=("source",)))
        self.assertEqual(LoopCoordinator.restore(c.snapshot()).next_steps(), ("next",))


if __name__ == "__main__":
    unittest.main()
