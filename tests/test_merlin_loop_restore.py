"""Snapshot recovery tests: interrupted work never resumes automatically."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from merlin_loop_coordinator import Loop, LoopCoordinator


class RestoreTests(unittest.TestCase):
    def test_interrupted_running_work_is_blocked(self):
        c = LoopCoordinator()
        c.add(Loop("plan", "plan"))
        c.start("plan")
        recovered = LoopCoordinator.restore(c.snapshot())
        self.assertEqual(recovered.loops["plan"].state, "blocked")
        self.assertEqual(recovered.next_steps(), ())
        self.assertIn("interrupted:requires-review", recovered.loops["plan"].evidence)

    def test_passed_dependency_stays_passed(self):
        c = LoopCoordinator()
        c.add(Loop("first", "research"))
        c.start("first")
        c.finish("first", passed=True, evidence="artifact:1")
        c.add(Loop("second", "research", dependencies=("first",)))
        restored = LoopCoordinator.restore(c.snapshot())
        self.assertEqual(restored.next_steps(), ("second",))

    def test_invalid_cycle_rejected(self):
        with self.assertRaises(ValueError):
            LoopCoordinator.restore({"a": {"kind": "plan", "parent": "b", "dependencies": [],
                "budget": 1, "state": "pending", "attempts": 0, "evidence": []},
                "b": {"kind": "plan", "parent": "a", "dependencies": [],
                "budget": 1, "state": "pending", "attempts": 0, "evidence": []}})


if __name__ == "__main__":
    unittest.main()
