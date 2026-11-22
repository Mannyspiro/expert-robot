"""Offline source-cited research: canonical raw artifacts, arithmetic control, restart."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "python"))
import merlin_cited_research_cycle as c
from experimental_self_healing import EvidenceLedger
from merlin.project_registry import MerlinRegistry
from merlin_loop_persistence import checkpoint
from merlin_research_session import ResearchSession


COMMIT = "a" * 40
SOURCE = b"class Fraction:\n    pass\n" + (b"# representative public technical source\n" * 10)


class PublicSourceResearchCycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.capture = self.root / "source"
        self.capture.mkdir()
        self.output = self.root / "research"
        self.write_capture(SOURCE)

    def write_capture(self, body, overrides=None):
        digest = hashlib.sha256(body).hexdigest()
        data = {
            "schema": "merlin-public-https-source-acceptance/1",
            "source_commit": COMMIT, "source_url": c.URL, "final_url": c.URL,
            "status": 200, "retrieval_kind": "https_http", "raw_bytes": len(body),
            "raw_path": "public-source-raw.py.txt", "raw_sha256": digest,
            "source_observed": True, "private_context_included": False,
            "promotion_authority": False,
            "observed_at_utc": "2026-11-21T12:00:00+00:00",
        }
        data.update(overrides or {})
        (self.capture / "public-source-raw.py.txt").write_bytes(body)
        (self.capture / "receipt.json").write_text(json.dumps(data, sort_keys=True))

    def invoke(self):
        with patch.object(c, "source_commit", return_value=COMMIT):
            return c.run(self.capture, self.output)

    def test_six_real_registry_bound_stages_and_alternate_integer_check(self):
        result = self.invoke()
        self.assertEqual(result["public_source_sha256"], hashlib.sha256(SOURCE).hexdigest())
        self.assertTrue(result["independent_exact_arithmetic_reference"])
        self.assertTrue(result["negative_control_rejected"])
        self.assertTrue(result["exact_artifact_readback"]["all_six_stages_bound"])
        self.assertEqual(result["exact_artifact_readback"]["verified_registry_blob_count"], 6)
        self.assertEqual(len(result["research_stages"]), 6)
        self.assertTrue(all(v == "passed" for v in result["research_stages"].values()))
        self.assertFalse(result["scientific_claim_established"])
        self.assertFalse(result["model_inference_performed"])
        self.assertFalse(result["promotion_authority"])
        self.assertTrue((self.output / "summary.json").is_file())

    def test_completed_cycle_restarts_without_rewriting_ledger(self):
        self.invoke()
        before = (self.output / "research-ledger.jsonl").read_bytes()
        first = json.loads((self.output / "summary.json").read_text())
        second = self.invoke()
        self.assertEqual((self.output / "research-ledger.jsonl").read_bytes(), before)
        self.assertEqual(first, second)

    def test_fetch_input_sha_mismatch_rejected_before_any_research_state(self):
        self.write_capture(SOURCE, {"source_commit": "f" * 40})
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertFalse((self.output / "research-ledger.jsonl").exists())

    def test_tampered_source_digest_rejected(self):
        self.write_capture(SOURCE, {"raw_sha256": "0" * 64})
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertFalse((self.output / "summary.json").exists())

    def test_false_live_source_report_rejected(self):
        self.write_capture(SOURCE, {"source_observed": False})
        with self.assertRaises(ValueError):
            self.invoke()

    def test_missing_retrieval_receipt_fails_closed(self):
        (self.capture / "receipt.json").unlink()
        with self.assertRaises(ValueError):
            self.invoke()

    def test_source_python_is_data_not_executed(self):
        marker = self.root / "source_executed_canary"
        untrusted = SOURCE + (f"open({str(marker)!r}, 'w').write('executed')\n").encode()
        self.write_capture(untrusted)
        self.invoke()
        self.assertFalse(marker.exists())

    def test_interrupted_stage_blocks_future_automatic_replay(self):
        report = self.invoke()
        self.assertTrue(report["exact_artifact_readback"]["all_six_stages_bound"])
        # Separate synthetic interrupted cycle: corrupting an actual completed
        # hash-linked event is not needed; begin an independent pinned ledger.
        second_dir = self.root / "interrupted"
        second_dir.mkdir()
        registry = MerlinRegistry(second_dir / "registry")
        registry.register_project(c.PROJECT, "Source research fixture")
        source_ref = c.store_once(registry, c.SOURCE_PATH, SOURCE, "text/plain")
        ledger = EvidenceLedger(second_dir / "research-ledger.jsonl")
        session = ResearchSession.open(c.frame_for(COMMIT, source_ref), ledger)
        session.scheduler.start(c.CYCLE + ":observe")
        checkpoint(session.scheduler, ledger, plan_id=session.plan_key)
        with self.assertRaises(RuntimeError):
            recovered = ResearchSession.open(c.frame_for(COMMIT, source_ref), ledger)
            if recovered.next_stage() is None:
                raise RuntimeError("interrupted stage requires review")

    def test_real_measurement_has_zero_residual_and_negative_control_differs(self):
        result = c.arithmetic()
        self.assertEqual(result["scaled_residual"], 0)
        self.assertEqual(result["independent_reference_residual"], 0)
        self.assertNotEqual(result["counterexample_residual"], 0)
        self.assertEqual(result["runtime_result"], "1/2")


if __name__ == "__main__":
    unittest.main()
