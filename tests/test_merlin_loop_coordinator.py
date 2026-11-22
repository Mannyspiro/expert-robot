"""Boundary and dependency tests for Merlin's bounded loop coordinator."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python"))
from merlin_loop_coordinator import Loop, LoopCoordinator


class CoordinatorTests(unittest.TestCase):
    def test_parent_child_evidence_and_completion(self):
        c = LoopCoordinator()
        c.add(Loop("plan", "plan"))
        c.start("plan")
        c.add(Loop("research", "research", parent="plan", budget=2))
        c.start("research")
        with self.assertRaises(ValueError):
            c.finish("plan", passed=True, evidence="premature")
        c.finish("research", passed=True, evidence="receipt:1")
        c.finish("plan", passed=True, evidence="receipt:2")
        self.assertEqual(c.snapshot()["plan"]["state"], "passed")

    def test_dependencies_require_success(self):
        c = LoopCoordinator()
        c.add(Loop("a", "research"))
        c.add(Loop("b", "subloop", dependencies=("a",)))
        with self.assertRaises(ValueError):
            c.start("b")
        c.start("a")
        c.finish("a", passed=True, evidence="receipt")
        c.start("b")
        self.assertEqual(c.snapshot()["b"]["state"], "running")

    def test_bounded_retry(self):
        c = LoopCoordinator()
        c.add(Loop("r", "research", budget=2))
        c.start("r")
        c.finish("r", passed=False, evidence="failure")
        c.retry("r")
        c.start("r")
        c.finish("r", passed=False, evidence="failure2")
        with self.assertRaises(ValueError):
            c.retry("r")
        self.assertEqual(c.snapshot()["r"]["attempts"], 2)

    def test_max_depth(self):
        c = LoopCoordinator(max_depth=1)
        c.add(Loop("a", "plan"))
        c.add(Loop("b", "research", parent="a"))
        with self.assertRaises(ValueError):
            c.add(Loop("c", "subloop", parent="b"))

    def test_missing_evidence_rejected(self):
        c = LoopCoordinator()
        c.add(Loop("a", "plan"))
        c.start("a")
        with self.assertRaises(ValueError):
            c.finish("a", passed=True, evidence="")

    def test_duplicate_or_unknown_dependencies_rejected(self):
        c = LoopCoordinator()
        c.add(Loop("a", "plan"))
        for deps in (("missing",), ("a", "a")):
            with self.assertRaises(ValueError):
                c.add(Loop("b", "research", dependencies=deps))

    def test_terminal_parent_cannot_gain_new_child(self):
        c = LoopCoordinator()
        c.add(Loop("plan", "plan"))
        c.start("plan")
        c.finish("plan", passed=True, evidence="receipt")
        with self.assertRaises(ValueError):
            c.add(Loop("late", "research", parent="plan"))

    def test_invalid_budget_types_fail_closed(self):
        for budget in (True, 1.5, "2", None):
            c = LoopCoordinator()
            with self.assertRaises(ValueError):
                c.add(Loop("invalid", "research", budget=budget))

    def test_parent_failure_waits_for_running_child(self):
        c = LoopCoordinator()
        c.add(Loop("root", "plan"))
        c.start("root")
        c.add(Loop("child", "research", parent="root"))
        c.start("child")
        with self.assertRaises(ValueError):
            c.finish("root", passed=False, evidence="abort")
        self.assertEqual(c.loops["root"].state, "running")
        c.finish("child", passed=False, evidence="failure")
        c.finish("root", passed=False, evidence="failure propagated")
        self.assertEqual(c.loops["root"].state, "failed")

    def test_block_requires_string_evidence(self):
        c = LoopCoordinator()
        c.add(Loop("root", "plan"))
        for reason in (None, 3, "", "   "):
            with self.assertRaises(ValueError):
                c.block("root", reason)
        self.assertEqual(c.loops["root"].state, "pending")

    def test_failed_child_prevents_parent_success(self):
        c = LoopCoordinator()
        c.add(Loop("a", "plan"))
        c.start("a")
        c.add(Loop("b", "research", parent="a"))
        c.start("b")
        c.finish("b", passed=False, evidence="failed check")
        with self.assertRaises(ValueError):
            c.finish("a", passed=True, evidence="unsupported claim")


if __name__ == "__main__":
    unittest.main()
