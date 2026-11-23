"""Restart, locking and budget negative controls for explicit synthetic supervisor."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("merlin_supervisor",ROOT/"scripts"/"merlin_research_supervisor.py")
import sys
sys.path.insert(0,str(ROOT/"scripts"))
assert SPEC and SPEC.loader
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"research.json"

    def test_restart_resumes_without_repeating_completed_task(self):
        first=module.supervise(self.path,max_invocations=1)
        second=module.supervise(self.path,max_invocations=2)
        third=module.supervise(self.path,max_invocations=3)
        self.assertEqual(first["new_task_ids"],["root"])
        self.assertEqual(second["new_task_ids"],["recurrence_identity","simulated_channel"])
        self.assertEqual(third["new_task_ids"],[])
        self.assertEqual(third["steps_after"],3)
        self.assertFalse(third["exactly_once_external_execution_proven"])

    def test_budget_fails_closed(self):
        for budget in (0,4,True):
            with self.subTest(budget=budget),self.assertRaises(ValueError):
                module.supervise(self.path,max_invocations=budget)

    def test_lock_contention_does_not_advance_checkpoint(self):
        import fcntl
        lock_path=self.path.with_name(self.path.name+".lock")
        with open(lock_path,"w") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError,"already supervised"):
                module.supervise(self.path)
        self.assertFalse(self.path.exists())

    def test_symlink_checkpoint_denied(self):
        outside=Path(self.tmp.name)/"outside.json"
        outside.write_text("do not modify")
        self.path.symlink_to(outside)
        with self.assertRaises(ValueError):
            module.supervise(self.path)
        self.assertEqual(outside.read_text(),"do not modify")


if __name__=="__main__":
    unittest.main()
