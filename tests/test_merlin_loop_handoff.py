"""Handoff ordering and blockers for bounded Merlin loops."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from merlin_loop_coordinator import Loop, LoopCoordinator


class HandoffTests(unittest.TestCase):
    def test_dependency_and_parent_handoff(self):
        c = LoopCoordinator()
        c.add(Loop("plan", "plan"))
        c.add(Loop("research", "research", parent="plan"))
        c.add(Loop("verify", "subloop", parent="plan", dependencies=("research",)))
        self.assertEqual(c.handoff()["next_steps"], ["plan"])
        c.start("plan")
        self.assertEqual(c.handoff()["next_steps"], ["research"])
        self.assertEqual(c.handoff()["blocked_pending"]["verify"]["dependencies"], ["research"])
        c.start("research")
        self.assertEqual(c.handoff()["running"], ["plan", "research"])
        c.finish("research", passed=True, evidence="verified:artifact")
        self.assertEqual(c.handoff()["next_steps"], ["verify"])
        c.start("verify")
        c.finish("verify", passed=True, evidence="verified:test")
        c.finish("plan", passed=True, evidence="verified:plan")
        self.assertEqual(c.handoff()["next_steps"], [])

    def test_failure_never_auto_retries(self):
        c = LoopCoordinator()
        c.add(Loop("task", "research", budget=2))
        c.start("task")
        c.finish("task", passed=False, evidence="failure:log")
        self.assertEqual(c.handoff()["next_steps"], [])
        self.assertEqual(c.handoff()["failed"], ["task"])
        c.retry("task")
        self.assertEqual(c.handoff()["next_steps"], ["task"])


if __name__ == "__main__":
    unittest.main()
