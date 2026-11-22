"""Regression and end-to-end checks for the durable scientific research session.

These use an actual local hash-linked ledger, not any simulated AI/model success.
"""
from dataclasses import asdict, replace
from hashlib import sha256
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from experimental_self_healing import EvidenceLedger
from merlin.scientific_loop import Observation, Prediction
from merlin_research_session import (
    ResearchFrame, ResearchReceipt, ResearchSession, STAGES, SCHEMA, _digest,
)
from merlin_loop_persistence import checkpoint


def frame(cycle_id="science-test"):
    return ResearchFrame(
        cycle_id=cycle_id, plan_id="MERLIN-PRODUCTION-MASTER-20261117",
        plan_version=6, source_commit="a" * 40,
        question="Does this bounded method reproduce the reference measurement?",
        metric="latency_s", unit="s", baseline_ref="fixture:baseline-v1",
        hypotheses=("latency improves", "latency is unchanged"),
        predictions=(Prediction("latency_s", 2.0, 0.2, "s"),),
        falsifier="An independently recorded measurement outside [1.8,2.2] s",
        stopping_rule="One declared fixture per hypothesis, no hidden retries",
        acceptance_rule="All predicted intervals contain the reported interval",
        source_refs=("source:public-fixture-v1",),
        unknowns=("Independent validation is not performed by this adapter",),
    )


def receipt(stage, *, status="recorded", observation=None, null_reason=""):
    digest = sha256(("raw:" + stage).encode()).hexdigest()
    if observation is not None:
        digest = observation.artifact_sha256
    return ResearchReceipt(
        stage=stage, artifact_sha256=digest,
        source_refs=("source:public-fixture-v1",),
        tool_name="pytest-style-stdlib-unittest", tool_version="1",
        evidence_class="simulated", status=status,
        interpretation="This only records a fixture; no physical claim.",
        observation=observation, null_reason=null_reason,
        challenge_scope=("Checked one declared counterexample and a negative fixture"
                         if stage == "challenge" else ""),
        plan_update_ref=("plan:append-only-revision-1" if stage == "update" else ""),
    )


def observation_for_experiment():
    return Observation(
        observation_id="obs-fixture-1", question="Measured fixture latency?",
        method="deterministic-fixture",
        measurements={"latency_s": 2.05},
        units={"latency_s": "s"},
        uncertainty={"latency_s": 0.02},
        conditions={"source": "synthetic_fixture", "runs": "1"},
        source_refs=("source:public-fixture-v1",),
        observed_at="2026-11-21T00:00:00Z",
        artifact_sha256=sha256(b"raw:experiment").hexdigest(),
    )


class DurableResearchSessionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ledger = EvidenceLedger(pathlib.Path(tmp.name) / "events.jsonl")
        self.original = frame()

    def test_all_six_stages_checkpoint_and_reopen(self):
        cycle = ResearchSession.open(self.original, self.ledger)
        self.assertEqual(cycle.next_stage(), "observe")
        for stage in STAGES:
            result = cycle.record(receipt(
                stage, observation=observation_for_experiment() if stage == "experiment" else None))
            self.assertEqual(result["stage"], stage)
            self.assertEqual(result["state"], "passed")
            self.assertFalse(result["scientific_claim_established"])
            self.assertFalse(result["promotion_authority"])
            cycle = ResearchSession.open(self.original, self.ledger)
            self.assertEqual(cycle.status()["stages"][stage], "passed")
            if stage == "experiment":
                self.assertEqual(result["assessment"]["overall"], "consistent_with_prediction")
        self.assertIsNone(cycle.next_stage())
        self.assertTrue(cycle.status()["procedural_record_complete"])
        self.assertFalse(cycle.status()["independent_verification"])
        self.assertFalse(cycle.status()["scientific_claim_established"])
        self.assertEqual(self.ledger.verify(), cycle.ledger.verify())

    def test_result_durable_across_another_python_process(self):
        cycle = ResearchSession.open(self.original, self.ledger)
        cycle.record(receipt("observe"))
        program = (
            "import pathlib,sys; sys.path.insert(0,sys.argv[2]); "
            "from experimental_self_healing import EvidenceLedger; "
            "from merlin_research_session import ResearchSession; "
            "from merlin.scientific_loop import Prediction; "
            "from merlin_research_session import ResearchFrame; "
            "f=ResearchFrame(cycle_id='science-test', "
            "plan_id='MERLIN-PRODUCTION-MASTER-20261117',plan_version=6,"
            "source_commit='a'*40,question='Does this bounded method reproduce the reference measurement?',"
            "metric='latency_s',unit='s',baseline_ref='fixture:baseline-v1',"
            "hypotheses=('latency improves','latency is unchanged'),"
            "predictions=(Prediction('latency_s',2.0,0.2,'s'),),"
            "falsifier='An independently recorded measurement outside [1.8,2.2] s',"
            "stopping_rule='One declared fixture per hypothesis, no hidden retries',"
            "acceptance_rule='All predicted intervals contain the reported interval',"
            "source_refs=('source:public-fixture-v1',),"
            "unknowns=('Independent validation is not performed by this adapter',)); "
            "s=ResearchSession.open(f,EvidenceLedger(pathlib.Path(sys.argv[1]))); "
            "assert s.next_stage()=='explain'"
        )
        completed = subprocess.run(
            [sys.executable, "-c", program, str(self.ledger.path), str(ROOT / "python")],
            capture_output=True, text=True, timeout=20, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_null_experiment_recorded_without_fabricating_measurement(self):
        cycle = ResearchSession.open(self.original, self.ledger)
        for stage in STAGES:
            result = cycle.record(receipt(
                stage, null_reason="Expected source was unavailable" if stage == "experiment" else ""))
        self.assertTrue(cycle.status()["procedural_record_complete"])
        self.assertEqual(self.ledger.verify(), cycle.ledger.verify())
        self.assertFalse(cycle.status()["scientific_claim_established"])
        result_entries = [
            row["event"] for row in __import__("json").loads("[" + ",".join(
                self.ledger.path.read_text().splitlines()) + "]")
            if row["event"].get("state") == "stage_result"
            and row["event"].get("stage") == "experiment"]
        self.assertEqual(len(result_entries), 1)
        self.assertEqual(result_entries[0]["assessment"]["overall"], "null_result")
        self.assertIsNone(result_entries[0]["receipt"]["observation"])

    def test_blocked_result_stops_all_dependents(self):
        cycle = ResearchSession.open(self.original, self.ledger)
        result = cycle.record(receipt("observe", status="blocked"))
        self.assertEqual(result["state"], "failed")
        self.assertIsNone(cycle.next_stage())
        with self.assertRaises(ValueError):
            cycle.record(receipt("explain"))
        reopened = ResearchSession.open(self.original, self.ledger)
        self.assertEqual(reopened.status()["stages"]["observe"], "failed")
        self.assertIsNone(reopened.next_stage())

    def test_running_restart_blocks_without_automatic_retry(self):
        cycle = ResearchSession.open(self.original, self.ledger)
        cycle.scheduler.start("science-test:observe")
        checkpoint(cycle.scheduler, self.ledger, plan_id=cycle.plan_key)
        restored = ResearchSession.open(self.original, self.ledger)
        self.assertEqual(restored.status()["stages"]["observe"], "blocked")
        self.assertIsNone(restored.next_stage())
        self.assertFalse(restored.status()["procedural_record_complete"])
        self.assertEqual(restored.scheduler.loops["science-test:observe"].attempts, 1)

    def test_stale_writer_cannot_overwrite_stage(self):
        first = ResearchSession.open(self.original, self.ledger)
        second = ResearchSession.open(self.original, self.ledger)
        first.record(receipt("observe"))
        with self.assertRaises(RuntimeError):
            second.record(receipt("observe"))
        reopened = ResearchSession.open(self.original, self.ledger)
        self.assertEqual(reopened.next_stage(), "explain")

    def test_frame_identity_freezes_question_and_plan_version(self):
        ResearchSession.open(self.original, self.ledger)
        for changed in (
            replace(self.original, question="Rewrite the original question"),
            replace(self.original, plan_version=7),
            replace(self.original, external_spend_ceiling_usd=1),
        ):
            with self.assertRaises(ValueError):
                ResearchSession.open(changed, self.ledger)
        self.assertEqual(ResearchSession.open(self.original, self.ledger).next_stage(), "observe")

    def test_rejects_out_of_order_and_duplicate_stage(self):
        cycle = ResearchSession.open(self.original, self.ledger)
        with self.assertRaises(ValueError):
            cycle.record(receipt("experiment", observation=observation_for_experiment()))
        cycle.record(receipt("observe"))
        with self.assertRaises(ValueError):
            cycle.record(receipt("observe"))

    def test_measurement_requires_exact_raw_digest_and_registered_sources(self):
        cycle = ResearchSession.open(self.original, self.ledger)
        for stage in ("observe", "explain", "predict"):
            cycle.record(receipt(stage))
        obs = observation_for_experiment()
        bad = replace(obs, artifact_sha256="f" * 64)
        with self.assertRaises(ValueError):
            cycle.record(replace(receipt("experiment", observation=obs),
                                 observation=bad))
        with self.assertRaises(ValueError):
            cycle.record(replace(receipt("experiment", observation=obs),
                                 source_refs=("different:source",)))
        self.assertEqual(cycle.next_stage(), "experiment")

    def test_invalid_experiment_missing_both_null_and_measurement(self):
        cycle = ResearchSession.open(self.original, self.ledger)
        for stage in ("observe", "explain", "predict"):
            cycle.record(receipt(stage))
        with self.assertRaises(ValueError):
            cycle.record(receipt("experiment"))
        with self.assertRaises(ValueError):
            cycle.record(receipt("experiment", observation=observation_for_experiment(),
                                 null_reason="both"))
        self.assertEqual(cycle.next_stage(), "experiment")

    def test_inconsistent_source_frame_is_rejected(self):
        invalid = replace(self.original, source_commit="inexact")
        with self.assertRaises(ValueError):
            ResearchSession.open(invalid, self.ledger)

    def test_ledger_tampering_fails_closed(self):
        cycle = ResearchSession.open(self.original, self.ledger)
        cycle.record(receipt("observe"))
        path = self.ledger.path
        path.write_text(path.read_text().replace("science-test", "science-fake", 1))
        with self.assertRaises(ValueError):
            ResearchSession.open(self.original, self.ledger)

    def test_fake_stage_receipt_cannot_replace_a_pending_stage(self):
        cycle = ResearchSession.open(self.original, self.ledger)
        r = receipt("observe")
        self.ledger.append({"subsystem": "merlin_research_session",
                            "schema": SCHEMA, "state": "stage_result",
                            "cycle_id": self.original.cycle_id,
                            "frame_sha256": self.original.sha256, "stage": "observe",
                            "receipt_sha256": _digest(asdict(r)),
                            "receipt": asdict(r), "assessment": {"overall": "stage_recorded"},
                            "independent_verification": False,
                            "promotion_authority": False})
        with self.assertRaises(ValueError):
            ResearchSession.open(self.original, self.ledger)

    def test_plan_references_do_not_grant_release_authority(self):
        cycle = ResearchSession.open(self.original, self.ledger)
        for stage in STAGES:
            cycle.record(receipt(stage, observation=observation_for_experiment() if stage == "experiment" else None))
        status = ResearchSession.open(self.original, self.ledger).status()
        self.assertEqual(status["parent_plan"]["version"], 6)
        self.assertEqual(status["source_commit"], "a" * 40)
        self.assertFalse(status["promotion_authority"])
        self.assertFalse(status["external_spend_allowed"])


if __name__ == "__main__":
    unittest.main()
