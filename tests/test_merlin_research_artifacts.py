"""Real local MerlinRegistry integration for bounded research-stage evidence."""
from dataclasses import replace
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from experimental_self_healing import EvidenceLedger
from merlin.project_registry import MerlinRegistry
from merlin.scientific_loop import Prediction
from merlin_research_session import ResearchFrame, ResearchReceipt, ResearchSession


def source_frame():
    return ResearchFrame(
        cycle_id="registry-fixture", plan_id="MERLIN-PRODUCTION-MASTER-20261117",
        plan_version=6, source_commit="c" * 40,
        question="Does measured source content match its pinned ledger identity?",
        metric="bytes_count", unit="byte", baseline_ref="fixture:canonical-v1",
        hypotheses=("content matches", "content differs"),
        predictions=(Prediction("bytes_count", 13.0, 0.0, "byte"),),
        falsifier="SHA-256 mismatch, cross-project ID, or unexpected byte count",
        stopping_rule="One fixed readback per checked reference",
        acceptance_rule="Exact source version and bytes match pinned digest",
        source_refs=("public:fixture",),
        unknowns=("Storage integrity is not independent scientific correctness",),
    )


def stage_receipt(digest):
    return ResearchReceipt(
        stage="observe", artifact_sha256=digest,
        source_refs=("public:fixture",), tool_name="registry-readback",
        tool_version="1", evidence_class="observed", status="recorded",
        interpretation="Local exact-byte fixture, not domain validation",
    )


class RegistryBindingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        self.project = "merlin-research-test"
        self.registry = MerlinRegistry(self.root / "registry")
        self.registry.register_project(self.project, "Research artifact test")
        self.ledger = EvidenceLedger(self.root / "events.jsonl")
        self.frame = source_frame()
        self.session = ResearchSession.open(self.frame, self.ledger)
        self.data = b"hello-merlin!"
        self.registry.put_artifact(self.project, "sources/observation.bin", self.data)
        self.ref = self.registry.artifact_ref(self.project, "sources/observation.bin")

    def bind(self, **kwargs):
        return self.session.record(
            stage_receipt(self.ref["sha256"]), artifact_ref=self.ref,
            registry=self.registry, project_id=self.project, **kwargs)

    def test_exact_artifact_version_round_trip_and_readback(self):
        result = self.bind()
        self.assertEqual(result["state"], "passed")
        self.assertFalse(result["scientific_claim_established"])
        other = ResearchSession.open(self.frame, self.ledger)
        summary = other.verify_registry_bindings(self.registry, project_id=self.project)
        self.assertEqual(summary["verified_registry_blob_count"], 1)
        self.assertEqual(summary["bound_stages"][0]["artifact_ref"], self.ref)
        self.assertFalse(summary["independent_scientific_verification"])
        self.assertFalse(summary["promotion_authority"])
        self.assertEqual(other.next_stage(), "explain")

    def test_old_version_remains_bound_after_new_publication(self):
        self.bind()
        self.registry.put_artifact(self.project, "sources/observation.bin", b"updated content")
        reread = ResearchSession.open(self.frame, self.ledger)
        summary = reread.verify_registry_bindings(self.registry, project_id=self.project)
        self.assertEqual(summary["bound_stages"][0]["artifact_ref"]["version"], 1)
        self.assertEqual(summary["verified_registry_blob_count"], 1)

    def test_different_project_fails_before_task_starts(self):
        with self.assertRaises(ValueError):
            self.session.record(stage_receipt(self.ref["sha256"]),
                                artifact_ref=self.ref, registry=self.registry,
                                project_id="other-project")
        self.assertEqual(self.session.next_stage(), "observe")

    def test_receipt_digest_does_not_match_artifact_ref(self):
        with self.assertRaises(ValueError):
            self.session.record(stage_receipt("0" * 64),
                                artifact_ref=self.ref, registry=self.registry,
                                project_id=self.project)
        self.assertEqual(self.session.next_stage(), "observe")

    def test_partial_artifact_binding_rejected(self):
        for kwargs in (
            {"artifact_ref": self.ref},
            {"registry": self.registry},
            {"project_id": self.project},
            {"artifact_ref": self.ref, "project_id": self.project},
            {"artifact_ref": self.ref, "registry": self.registry},
        ):
            with self.subTest(kwargs=sorted(kwargs)):
                with self.assertRaises(ValueError):
                    self.session.record(stage_receipt(self.ref["sha256"]), **kwargs)
        self.assertEqual(self.session.next_stage(), "observe")

    def test_bad_artifact_ref_schema_fails_closed(self):
        bad = dict(self.ref)
        bad.pop("version")
        with self.assertRaises(ValueError):
            self.session.record(stage_receipt(self.ref["sha256"]),
                                artifact_ref=bad, registry=self.registry,
                                project_id=self.project)

    def test_tampered_blob_detected_during_readback(self):
        self.bind()
        path = (self.registry.blobs / self.ref["sha256"][:2] /
                self.ref["sha256"][2:])
        path.write_bytes(b"tampered")
        reread = ResearchSession.open(self.frame, self.ledger)
        with self.assertRaises((RuntimeError, ValueError, OSError)):
            reread.verify_registry_bindings(self.registry, project_id=self.project)
        self.assertFalse(reread.status()["independent_verification"])

    def test_undersized_read_limit_rejected(self):
        self.bind()
        reread = ResearchSession.open(self.frame, self.ledger)
        with self.assertRaises((ValueError, RuntimeError)):
            reread.verify_registry_bindings(self.registry, project_id=self.project,
                                            max_bytes=2)
        with self.assertRaises(ValueError):
            reread.verify_registry_bindings(self.registry, project_id=self.project,
                                            max_bytes=0)

    def test_readback_in_wrong_project_rejected(self):
        self.bind()
        other = ResearchSession.open(self.frame, self.ledger)
        with self.assertRaises(ValueError):
            other.verify_registry_bindings(self.registry, project_id="other-project")

    def test_unbound_record_is_not_reported_as_verified(self):
        self.session.record(stage_receipt(self.ref["sha256"]))
        reread = ResearchSession.open(self.frame, self.ledger)
        summary = reread.verify_registry_bindings(self.registry, project_id=self.project)
        self.assertEqual(summary["verified_registry_blob_count"], 0)
        self.assertEqual(summary["unbound_stages"], ["observe"])
        self.assertFalse(summary["all_six_stages_bound"])

    def test_cross_process_registry_evidence_readback(self):
        self.bind()
        program = (
            "import pathlib,sys; "
            "sys.path.insert(0,sys.argv[3]); "
            "sys.path.insert(0,sys.argv[4]); "
            "from merlin_research_session import ResearchSession; "
            "from experimental_self_healing import EvidenceLedger; "
            "from merlin.project_registry import MerlinRegistry; "
            "from test_merlin_research_artifacts import source_frame; "
            "r=ResearchSession.open(source_frame(),EvidenceLedger(pathlib.Path(sys.argv[1]))); "
            "v=r.verify_registry_bindings(MerlinRegistry(pathlib.Path(sys.argv[2])),"
            "project_id='merlin-research-test'); "
            "assert v['verified_registry_blob_count']==1 and r.next_stage()=='explain'"
        )
        result = subprocess.run(
            [sys.executable, "-c", program,
             str(self.ledger.path), str(self.registry.root),
             str(ROOT / "python"), str(ROOT / "tests")],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
