"""Research checkpoint to Second Brain review candidate tests."""
from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
SPEC=importlib.util.spec_from_file_location("second_brain_review",ROOT/"scripts"/"merlin_second_brain_research_review.py")
assert SPEC and SPEC.loader
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
from merlin_research_episode import run_episode


class ResearchReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.checkpoint=Path(self.tmp.name)/"checkpoint.json"

    def test_checked_receipts_have_exact_provenance_and_no_truth_promotion(self):
        run_episode(self.checkpoint,3)
        report=module.preview(self.checkpoint)
        self.assertEqual(len(report["receipts"]),3)
        self.assertFalse(report["automatically_promoted"])
        self.assertFalse(report["scientific_truth_established"])
        self.assertTrue(report["review_required"])
        text=module.markdown(report)
        self.assertIn(report["checkpoint_sha256"],text)
        self.assertIn("Unreviewed",text)
        self.assertNotIn("synthetic_simulated_recurrence",text)

    def test_corrupt_checkpoint_rejected(self):
        run_episode(self.checkpoint,1)
        self.checkpoint.write_text('{"sha256":"forged"}')
        with self.assertRaises(ValueError):
            module.preview(self.checkpoint)

    def test_symlink_checkpoint_rejected(self):
        target=Path(self.tmp.name)/"real.json"
        run_episode(target,1)
        self.checkpoint.symlink_to(target)
        with self.assertRaises(ValueError):
            module.preview(self.checkpoint)


if __name__=="__main__":
    unittest.main()
