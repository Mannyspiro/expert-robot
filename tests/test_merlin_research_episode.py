"""Cross-invocation local research episode with integrity and budget negatives."""
from pathlib import Path
import copy
import importlib.util
import json
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("merlin_simulated_episode",ROOT/"scripts"/"merlin_research_episode.py")
assert SPEC and SPEC.loader
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

class ResearchEpisodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"research.json"

    def test_one_step_then_restart_uses_original_receipt(self):
        first=module.run_episode(self.path,1)
        self.assertEqual(first["summary"]["steps_used"],1)
        self.assertEqual(first["summary"]["queued"],["recurrence_identity","simulated_channel"])
        second=module.run_episode(self.path,1)
        self.assertEqual(second["summary"]["steps_used"],2)
        self.assertEqual(second["latest_receipts"][0]["task_id"],"recurrence_identity")
        self.assertFalse(second["production_qualified"])
        self.assertFalse(second["proof_or_model_gain_established"])

    def test_complete_all_three_and_do_not_restart_automatically(self):
        done=module.run_episode(self.path,3)
        self.assertEqual(done["summary"]["status"],"ended_with_unverified_claims")
        self.assertEqual(done["summary"]["steps_used"],3)
        self.assertEqual([r["status"] for r in done["latest_receipts"]],["checked"]*3)
        noop=module.run_episode(self.path,1)
        self.assertEqual(noop["latest_receipts"],[])
        self.assertEqual(noop["summary"]["steps_used"],3)
        self.assertFalse(noop["background_worker_running"])

    def test_corrupt_checkpoint_refused(self):
        module.run_episode(self.path,1)
        self.path.write_text('{"schema":"merlin-research-subloops/1","sha256":"forged"}')
        with self.assertRaises(ValueError):
            module.run_episode(self.path,1)

    def test_duplicate_checkpoint_keys_denied(self):
        self.path.write_text('{"schema":"one","schema":"two"}')
        with self.assertRaises(ValueError):
            module.run_episode(self.path,1)

    def test_symlink_to_external_checkpoint_denied(self):
        external=Path(self.tmp.name)/"target"
        external.write_text("outside")
        self.path.symlink_to(external)
        with self.assertRaises(ValueError):
            module.run_episode(self.path,1)
        self.assertEqual(external.read_text(),"outside")

    def test_invalid_step_budget_denied(self):
        for steps in (0,4,True):
            with self.subTest(steps=steps),self.assertRaises(ValueError):
                module.run_episode(self.path,steps)

if __name__=="__main__":
    unittest.main()
