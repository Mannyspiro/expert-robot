"""Executable native offline reference workflow and stale-report regression tests."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
SCRIPT = ROOT / "scripts" / "merlin_research_reference_demo.py"
sys.path.insert(0, str(PYTHON_ROOT))
sys.path.insert(0, str(ROOT))
from experimental_self_healing import EvidenceLedger
from merlin.project_registry import MerlinRegistry
from merlin_loop_persistence import checkpoint
from merlin_research_session import ResearchSession
from scripts.merlin_research_reference_demo import commit_sha, frame


class OfflineResearchDemoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.output = pathlib.Path(temp.name) / "evidence"

    def invoke(self, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--output", str(self.output)],
            cwd=ROOT, capture_output=True, text=True,
            env=env or os.environ.copy(), timeout=30, check=False,
        )

    def test_real_registry_cycle_and_negative_control(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((self.output / "summary.json").read_text())
        self.assertEqual(summary["status"], "software_fixture_passed")
        self.assertEqual(summary["registry_readback"]["verified_registry_blob_count"], 6)
        self.assertTrue(summary["registry_readback"]["all_six_stages_bound"])
        self.assertEqual(len(summary["stages"]), 6)
        self.assertTrue(all(s == "passed" for s in summary["stages"].values()))
        self.assertTrue(summary["control"]["rejected"])
        self.assertFalse(summary["scientific_claim_established"])
        self.assertFalse(summary["real_model_qualified"])
        self.assertFalse(summary["promotion_authority"])
        self.assertEqual(summary["external_spend_usd"], 0)

    def test_second_process_does_not_rerun_completed_experiment(self):
        self.assertEqual(self.invoke().returncode, 0)
        before = (self.output / "research-ledger.jsonl").read_bytes()
        second = self.invoke()
        self.assertEqual(second.returncode, 0, second.stderr)
        after = (self.output / "research-ledger.jsonl").read_bytes()
        self.assertEqual(before, after, "completed replay must be read-only")
        summary = json.loads((self.output / "summary.json").read_text())
        self.assertEqual(summary["registry_readback"]["verified_registry_blob_count"], 6)

    def test_corrupted_blob_removes_obsolete_success_summary(self):
        self.assertEqual(self.invoke().returncode, 0)
        registry = MerlinRegistry(self.output / "registry")
        ref = registry.artifact_ref("merlin-offline-research-fixture", "stages/experiment.json")
        path = registry.blobs / ref["sha256"][:2] / ref["sha256"][2:]
        path.write_bytes(b"corrupt")
        failed = self.invoke()
        self.assertNotEqual(failed.returncode, 0)
        self.assertFalse((self.output / "summary.json").exists())
        self.assertIn("BLOCKED", failed.stderr)

    def test_unreviewed_interrupted_execution_never_replays(self):
        self.output.mkdir(parents=True)
        ledger = EvidenceLedger(self.output / "research-ledger.jsonl")
        session = ResearchSession.open(frame(commit_sha()), ledger)
        session.scheduler.start("merlin-reference-fixture-v1:observe")
        checkpoint(session.scheduler, ledger, plan_id=session.plan_key)
        before = ledger.path.read_bytes()
        failed = self.invoke()
        self.assertNotEqual(failed.returncode, 0)
        self.assertFalse((self.output / "summary.json").exists())
        self.assertEqual(before, ledger.path.read_bytes())

    def test_wrong_exact_revision_fails_closed(self):
        env = os.environ.copy()
        env["MERLIN_EXPECTED_SHA"] = "0" * 40
        failed = self.invoke(env)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("pinned source", failed.stderr)
        self.assertFalse((self.output / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
