from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from merlin.branch_research import Branch, BranchResearch


PLAN = (
    Branch("root-a", "First root", 5),
    Branch("root-b", "Second root", 4),
    Branch("dependent", "Follow the first root", 8, ("root-a", "root-b")),
    Branch("explore", "Exploratory sibling", 1, ("root-b",), True),
    Branch("joint", "Join branches", 4, ("dependent", "explore")),
)


class DurableBranches(unittest.TestCase):
    def test_restart_preserves_order_and_no_duplicate_work(self):
        with TemporaryDirectory() as tmp:
            state = Path(tmp)
            calls = []
            def evaluate(key, inputs):
                calls.append(key)
                return {"passed": True, "detail": key, "links": sorted(inputs)}
            paused = BranchResearch(state / "paused.sqlite3", PLAN)
            self.assertEqual(paused.step(evaluate, budget=2)["checkpoint"]["cursor"], 2)
            del paused
            resumed = BranchResearch(state / "paused.sqlite3", PLAN)
            result = resumed.step(evaluate, budget=4)
            self.assertEqual(calls, ["root-a", "root-b", "explore", "dependent", "joint"])
            self.assertEqual(resumed.step(evaluate), result)
            self.assertEqual(len(calls), 5)
            clean = BranchResearch(state / "clean.sqlite3", PLAN)
            clean.step(evaluate, budget=4)
            self.assertEqual(clean.step(evaluate)["receipts"], result["receipts"])

    def test_failed_prerequisite_blocks_join_and_earns_no_xp(self):
        with TemporaryDirectory() as tmp:
            runner = BranchResearch(Path(tmp) / "state.sqlite3", PLAN)
            def evaluate(key, inputs):
                return {"passed": key != "root-a", "detail": key}
            result = runner.step(evaluate, budget=4)
            self.assertEqual(result["progression"]["completed"], 2)
            self.assertEqual(result["progression"]["xp"], 20)
            self.assertEqual({x["id"]: x["status"] for x in result["quests"]}["joint"], "waiting")
            self.assertIsNone(result["selected"])
