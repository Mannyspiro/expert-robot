"""Synthetic local regressions for the scheduler/callback ownership boundary.

These checks do not establish independent scientific verification, sandboxing,
external-effect exactly-once execution, or production integration.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest

from merlin.branch_research import Branch, BranchResearch
import merlin.branch_research as subject


PLAN = (
    Branch("root-a", "First root", 5),
    Branch("root-b", "Second root", 4),
    Branch("dependent", "Follow both roots", 8, ("root-a", "root-b")),
    Branch("explore", "Exploratory sibling", 1, ("root-b",), True),
    Branch("joint", "Join branches", 4, ("dependent", "explore")),
)
PAIR = (Branch("root", "Root", 2), Branch("child", "Child", 1, ("root",)))


def measured(key, inputs):
    return {"passed": True, "detail": key, "nested": {"values": [1, 2]}}


class CallbackOwnership(unittest.TestCase):
    def assert_mutation_isolated(self, mutate):
        with TemporaryDirectory() as temp:
            path = Path(temp)
            clean = BranchResearch(path / "clean.sqlite3", PAIR).step(measured, budget=2)
            def evaluate(key, inputs):
                if key == "child":
                    mutate(inputs)
                return measured(key, inputs)
            runner = BranchResearch(path / "mutated.sqlite3", PAIR)
            result = runner.step(evaluate, budget=2)
            self.assertEqual(result, clean)
            self.assertEqual(BranchResearch(runner.database, PAIR).status(), clean)
            self.assertEqual(runner.step(lambda *_: self.fail("Repeated committed work")), clean)

    def test_overwritten_parent_hash_is_isolated(self):
        self.assert_mutation_isolated(lambda rows: rows["root"].__setitem__("receipt_sha256", "0" * 64))

    def test_cleared_callback_mapping_is_isolated(self):
        self.assert_mutation_isolated(lambda rows: rows.clear())

    def test_added_parent_is_isolated(self):
        self.assert_mutation_isolated(lambda rows: rows.__setitem__("invented", deepcopy(rows["root"])))

    def test_replaced_parent_is_isolated(self):
        self.assert_mutation_isolated(lambda rows: rows.__setitem__("root", {"receipt_sha256": "0" * 64}))

    def test_deleted_parent_hash_is_isolated(self):
        self.assert_mutation_isolated(lambda rows: rows["root"].pop("receipt_sha256"))

    def test_cleared_parent_receipt_is_isolated(self):
        self.assert_mutation_isolated(lambda rows: rows["root"].clear())

    def test_nested_evidence_mutation_is_isolated(self):
        def mutate(rows):
            rows["root"]["evidence"]["nested"]["values"].append(99)
            rows["root"]["status"] = "failed"
            rows["root"]["prerequisite_receipts"]["invented"] = "0" * 64
        self.assert_mutation_isolated(mutate)

    def test_multiple_parent_identity_and_chronological_parent_stay_distinct(self):
        with TemporaryDirectory() as temp:
            state = Path(temp)
            clean = BranchResearch(state / "clean.sqlite3", PLAN)
            clean.step(measured, budget=4)
            expected = clean.step(measured)
            runner = BranchResearch(state / "candidate.sqlite3", PLAN)
            def mutate(key, inputs):
                for row in inputs.values():
                    row["receipt_sha256"] = "0" * 64
                inputs.clear()
                return measured(key, inputs)
            runner.step(mutate, budget=2)
            result = BranchResearch(runner.database, PLAN).step(mutate, budget=4)
            self.assertEqual(result, expected)
            rows = {row["branch"]: row for row in result["receipts"]}
            self.assertEqual(rows["dependent"]["parent_sha256"], rows["explore"]["receipt_sha256"])
            self.assertEqual(set(rows["dependent"]["prerequisite_receipts"]), {"root-a", "root-b"})


class TransactionBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.runner = BranchResearch(self.path, PAIR)

    def test_callback_exception_rolls_back_current_branch_and_preserves_prior(self):
        prior = self.runner.step(measured)
        def fail(key, inputs):
            inputs.clear()
            raise RuntimeError("synthetic failure before commit")
        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            self.runner.step(fail)
        self.assertEqual(BranchResearch(self.path, PAIR).status(), prior)
        result = self.runner.step(measured)
        self.assertEqual(result["checkpoint"]["cursor"], 2)
        self.assertEqual(result["receipts"][0], prior["receipts"][0])

    def test_invalid_evidence_rolls_back_and_preserves_prior(self):
        prior = self.runner.step(measured)
        invalid = (None, [], {}, {"passed": 1, "detail": "x"},
                   {"passed": True, "detail": None},
                   {"passed": True, "detail": "x", "nonfinite": float("nan")},
                   {"passed": True, "detail": "x", "non_json": object()})
        for evidence in invalid:
            with self.subTest(evidence=repr(evidence)):
                with self.assertRaises((ValueError, TypeError)):
                    self.runner.step(lambda *_: evidence)
                self.assertEqual(self.runner.status(), prior)
        self.assertEqual(self.runner.step(measured)["checkpoint"]["cursor"], 2)

    def test_oversized_evidence_rolls_back(self):
        prior = self.runner.step(measured)
        with self.assertRaisesRegex(ValueError, "recorded budget"):
            self.runner.step(lambda *_: {"passed": True, "detail": "x" * (64 * 1024)})
        self.assertEqual(self.runner.status(), prior)

    def test_budget_rejects_invalid_values_without_model_contact(self):
        for value in (0, 5, -1, True, 1.0, "1", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.runner.step(lambda *_: self.fail("Evaluator invoked"), budget=value)
        self.assertFalse(self.path.exists())

    def test_changed_plan_fails_closed_before_evaluation(self):
        prior = self.runner.step(measured)
        altered = (Branch("root", "Changed title", 2), PAIR[1])
        with self.assertRaisesRegex(RuntimeError, "identity differs"):
            BranchResearch(self.path, altered).step(lambda *_: self.fail("Evaluator invoked"))
        self.assertEqual(self.runner.status(), prior)

    def test_persisted_evidence_tampering_fails_closed(self):
        self.runner.step(measured)
        with sqlite3.connect(self.path) as db:
            body = json.loads(db.execute("SELECT body FROM branch_receipts").fetchone()[0])
            body["evidence"]["detail"] = "tampered"
            db.execute("UPDATE branch_receipts SET body=?", (json.dumps(body),))
        with self.assertRaisesRegex(RuntimeError, "identity differs"):
            self.runner.step(lambda *_: self.fail("Evaluator invoked"))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM branch_receipts").fetchone()[0], 1)

    def test_mutating_returned_status_does_not_change_storage(self):
        returned = self.runner.step(measured)
        expected = deepcopy(returned)
        returned["receipts"][0]["evidence"]["nested"]["values"].append(100)
        returned["receipts"][0]["receipt_sha256"] = "0" * 64
        self.assertEqual(self.runner.status(), expected)

    def test_two_callers_do_not_repeat_committed_evaluations(self):
        barrier = threading.Barrier(2)
        calls = []
        lock = threading.Lock()
        def run():
            worker = BranchResearch(self.path, PLAN)
            def evaluate(key, inputs):
                with lock:
                    calls.append(key)
                return measured(key, inputs)
            barrier.wait(timeout=5)
            return worker.step(evaluate, budget=4)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run) for _ in range(2)]
            for future in futures:
                future.result(timeout=10)
        self.assertEqual(calls, ["root-a", "root-b", "explore", "dependent", "joint"])
        self.assertEqual(BranchResearch(self.path, PLAN).status()["checkpoint"]["cursor"], 5)

    def test_process_exit_before_commit_allows_retry_not_exactly_once_effects(self):
        prior = self.runner.step(measured)
        marker = Path(self.temp.name) / "external-effect.txt"
        code = '''
import os
from pathlib import Path
from merlin.branch_research import Branch, BranchResearch
plan = (Branch("root", "Root", 2), Branch("child", "Child", 1, ("root",)))
def interrupted(key, inputs):
    with Path(os.environ["MARKER"]).open("a") as stream:
        stream.write(key + "\\n")
        stream.flush()
        os.fsync(stream.fileno())
    os._exit(73)
BranchResearch(os.environ["DATABASE"], plan).step(interrupted)
'''
        env = {**os.environ, "PYTHONPATH": str(Path(subject.__file__).resolve().parents[1]),
               "DATABASE": str(self.path), "MARKER": str(marker)}
        child = subprocess.run([sys.executable, "-c", code], env=env, timeout=10,
                               capture_output=True, text=True)
        self.assertEqual(child.returncode, 73, child.stderr)
        self.assertEqual(BranchResearch(self.path, PAIR).status(), prior)
        def retry(key, inputs):
            with marker.open("a") as stream:
                stream.write(key + "\n")
            return measured(key, inputs)
        result = self.runner.step(retry)
        self.assertEqual(result["checkpoint"]["cursor"], 2)
        self.assertEqual(marker.read_text().splitlines(), ["child", "child"])

    def test_no_side_effect_from_status_on_missing_database(self):
        self.assertEqual(self.runner.status()["checkpoint"]["cursor"], 0)
        self.assertFalse(self.path.exists())

    def test_invalid_dags_fail_before_creating_database(self):
        invalid = ((), (PAIR[0], PAIR[0]),
                   (Branch("root", "Root", 1, ("missing",)),),
                   (Branch("a", "A", 1, ("b",)), Branch("b", "B", 1, ("a",))),
                   (Branch("root", "Root", 1, ("root",)),),
                   tuple(Branch(str(i), str(i), i) for i in range(33)))
        for plan in invalid:
            with self.subTest(plan=plan):
                with self.assertRaises(ValueError):
                    BranchResearch(self.path, plan)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
