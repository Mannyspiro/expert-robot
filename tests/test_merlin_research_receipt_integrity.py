"""Fail-closed readback and ambiguous-crash tests for Merlin research receipts."""
from dataclasses import asdict
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from experimental_self_healing import EvidenceLedger
from merlin.scientific_loop import Prediction
from merlin_loop_persistence import checkpoint
from merlin_research_session import (
    ResearchFrame, ResearchReceipt, ResearchSession, SCHEMA, _digest,
)


def frame():
    return ResearchFrame(
        cycle_id="receipt-test", plan_id="MERLIN-PRODUCTION-MASTER-20261117",
        plan_version=6, source_commit="b" * 40,
        question="Does the result match a frozen scalar reference?",
        metric="residual", unit="ratio", baseline_ref="baseline:one",
        hypotheses=("reference fit", "reference mismatch"),
        predictions=(Prediction("residual", 0.0, 0.1, "ratio"),),
        falsifier="Observed absolute residual exceeds 0.1",
        stopping_rule="One fixed trial; no automatic retry",
        acceptance_rule="Compare to frozen reference using recorded units",
        source_refs=("ref:fixture",), unknowns=("External validity unproven",),
    )


def receipt(stage, status="recorded"):
    return ResearchReceipt(
        stage=stage, artifact_sha256="a" * 64,
        source_refs=("ref:fixture",), tool_name="fixture-only", tool_version="1",
        evidence_class="simulated", status=status,
        interpretation="Synthetic receipt; not independent verification",
        null_reason="No sample available" if stage == "experiment" else "",
        challenge_scope="one negative reference case" if stage == "challenge" else "",
        plan_update_ref="append-only:revision-1" if stage == "update" else "",
    )


class ReceiptIntegrityTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.ledger = EvidenceLedger(pathlib.Path(root.name) / "events.jsonl")
        self.frame = frame()
        self.session = ResearchSession.open(self.frame, self.ledger)

    def inject(self, *, claim_stage="observe", evidence_stage="observe",
               status="recorded", mutate=None, finish=True, authority=False):
        current = self.session.next_stage()
        self.assertEqual(current, claim_stage)
        name = self.frame.cycle_id + ":" + claim_stage
        self.session.scheduler.start(name)
        checkpoint(self.session.scheduler, self.ledger, plan_id=self.session.plan_key)
        payload = asdict(receipt(evidence_stage, status=status))
        if mutate is not None:
            mutate(payload)
        event = {
            "subsystem": "merlin_research_session", "schema": SCHEMA,
            "state": "stage_result", "cycle_id": self.frame.cycle_id,
            "frame_sha256": self.frame.sha256,
            "stage": claim_stage, "receipt_sha256": _digest(payload),
            "receipt": payload, "assessment": {"overall": "stage_recorded"},
            "independent_verification": authority, "promotion_authority": False,
        }
        result = self.ledger.append(event)
        if finish:
            self.session.scheduler.finish(
                name, passed=True, evidence="stage-result:" + result["hash"])
            checkpoint(self.session.scheduler, self.ledger, plan_id=self.session.plan_key)
        return result

    def test_forged_success_from_blocked_receipt_rejected(self):
        self.inject(status="blocked")
        with self.assertRaises(ValueError):
            ResearchSession.open(self.frame, self.ledger)

    def test_stage_label_mismatch_rejected(self):
        self.inject(evidence_stage="explain")
        with self.assertRaises(ValueError):
            ResearchSession.open(self.frame, self.ledger)

    def test_missing_required_receipt_field_rejected_even_with_matching_digest(self):
        self.inject(mutate=lambda p: p.pop("interpretation"))
        with self.assertRaises(ValueError):
            ResearchSession.open(self.frame, self.ledger)

    def test_unknown_evidence_class_rejected(self):
        self.inject(mutate=lambda p: p.update(evidence_class="verified_truth"))
        with self.assertRaises(ValueError):
            ResearchSession.open(self.frame, self.ledger)

    def test_authority_escalation_flag_fails_closed(self):
        self.inject(authority=True)
        with self.assertRaises(ValueError):
            ResearchSession.open(self.frame, self.ledger)

    def test_stage_receipt_after_crash_does_not_resume(self):
        # Simulate crash after ledger receipt, before scheduler's final checkpoint.
        self.inject(finish=False)
        recovered = ResearchSession.open(self.frame, self.ledger)
        self.assertEqual(recovered.status()["stages"]["observe"], "blocked")
        self.assertIsNone(recovered.next_stage())
        self.assertFalse(recovered.status()["procedural_record_complete"])
        with self.assertRaises(ValueError):
            recovered.record(receipt("observe"))

    def test_unpinned_plan_update_receipt_rejected_at_readback(self):
        for stage in ("observe", "explain", "predict", "experiment", "challenge"):
            self.session.record(receipt(stage))
        self.inject(claim_stage="update", evidence_stage="update",
                    mutate=lambda p: p.update(plan_update_ref=""))
        with self.assertRaises(ValueError):
            ResearchSession.open(self.frame, self.ledger)

    def test_orphan_result_without_checkpoint_rejected(self):
        r = receipt("observe")
        self.ledger.append({
            "subsystem": "merlin_research_session", "schema": SCHEMA,
            "state": "stage_result", "cycle_id": self.frame.cycle_id,
            "frame_sha256": self.frame.sha256,
            "stage": "observe", "receipt_sha256": r.sha256,
            "receipt": asdict(r), "assessment": {"overall": "stage_recorded"},
            "independent_verification": False, "promotion_authority": False,
        })
        with self.assertRaises(ValueError):
            ResearchSession.open(self.frame, self.ledger)


if __name__ == "__main__":
    unittest.main()
