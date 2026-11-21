import ast
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from merlin.learning_platform import Actor, LearningPlatform, LearningConflictError, LearningPermissionError
from merlin.learning_lab_bridge import LearningLabBridge
from merlin.project_registry import MerlinRegistry
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.research_evidence import ResearchEvidenceRecorder
from merlin.titan_protocol_model import build_titan_protocol_bundle


class LearningLabBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.platform = LearningPlatform(root / "learning.sqlite3")
        self.registry = MerlinRegistry(root / "registry")
        self.registry.register_project("tenant-a-labs", "Synthetic lab evidence")
        self.registry.register_project("tenant-b-labs", "Separate synthetic evidence")
        self.recorder = ResearchEvidenceRecorder(self.registry, HypothesisLedger(root / "hypotheses.sqlite3"),
                                                MerlinKnowledgeGraph(root / "graph.sqlite3"))
        self.teacher = Actor("tenant-a", "teacher", "instructor")
        self.reviewer = Actor("tenant-a", "reviewer", "reviewer")
        self.learner = Actor("tenant-a", "student", "learner")
        self.other = Actor("tenant-a", "other-student", "learner")
        self.course = self.course_fixture(self.teacher, self.reviewer)
        self.platform.enroll(self.learner, self.course["course_id"])
        self.platform.enroll(self.other, self.course["course_id"])
        self.bridge = LearningLabBridge(self.platform, self.recorder,
            tenant_projects={"tenant-a": "tenant-a-labs", "tenant-b": "tenant-b-labs"}, source_commit="a" * 40)
        self.args = {"course_id": self.course["course_id"], "course_version": self.course["version"],
                     "manifest_sha256": self.course["manifest_sha256"], "lesson_id": "lab", "run_id": "run-1"}

    def course_fixture(self, teacher, reviewer, *, publish=True):
        course = self.platform.create_course(teacher, "titan-lab", "Titan structural model")
        manifest = course["manifest"]
        manifest["objectives"] = [{"id": "structure", "title": "Explain structural scope", "prerequisites": []}]
        manifest["lessons"] = [{"id": "lab", "title": "Fixed structural lab", "objective_id": "structure",
                                 "exercise": {"task_id": LearningLabBridge.TASK_ID}}]
        manifest["assessments"] = [{"id": "assessment", "title": "Explain results", "objective_id": "structure",
                                     "human_review_required": True, "rubric": [{"dimension": "limitations", "points": 1}]}]
        bundle = build_titan_protocol_bundle(kem="ML-KEM-768")
        manifest["research_scope"] = {"source_commit": "a" * 40, "model_sha256": bundle["model_sha256"],
                                      "vectors_sha256": bundle["vectors_sha256"]}
        course = self.platform.update_manifest(teacher, course["course_id"], manifest)
        if publish:
            self.platform.review_course(reviewer, course["course_id"], 1, "approved", "Synthetic review fixture")
            course = self.platform.publish_course(teacher, course["course_id"])
        return course

    def run_lab(self, actor=None, **changes):
        args = {**self.args, "prediction": "I predict one positive structural fixture and four explicit rejections", **changes}
        return self.bridge.run_titan_lab(actor or self.learner, **args)

    def submit(self, **changes):
        return self.bridge.submit_lab_assessment(self.learner, **{**self.args,
            "submission_id": "submission-1", "reflection": "Structural consistency does not establish cryptographic security", **changes})

    def test_exact_bytes_evidence_and_pending_assessment_without_grading(self):
        receipt = self.run_lab()
        raw = self.registry.read_artifact_ref(receipt["artifact_ref"])["content"]
        report = json.loads(raw)
        self.assertEqual(report["binding"]["learner_id"], self.learner.actor_id)
        self.assertEqual(set(report["representation_checks"]), {"simplex", "n_ality", "continuum", "fuzzy_logic"})
        self.assertEqual(receipt["vector_count"], 5)
        self.assertEqual(receipt["artifact_ref"]["version"], 1)
        self.assertEqual(self.recorder.ledger.get(receipt["hypothesis_id"]).status, "proposed")
        evidence = self.recorder.ledger.evidence(receipt["hypothesis_id"])
        self.assertEqual(len(evidence), 1); self.assertEqual(evidence[0].artifact_hash, receipt["artifact_sha256"])
        result = self.submit()
        self.assertEqual(result["status"], "pending_review")
        for value in (receipt, report):
            self.assertFalse(value["qualification"]); self.assertFalse(value["promotion_authority"])
            self.assertFalse(value["mastery_updated"])
        self.assertFalse(result["proof_qualified"]); self.assertFalse(result["mastery_updated"])
        with self.platform._connect() as db:
            response = json.loads(db.execute("SELECT response_json FROM learning_submissions").fetchone()[0])
            self.assertEqual(response["lab_receipt"]["artifact_ref"], receipt["artifact_ref"])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM learning_submission_reviews").fetchone()[0], 0)

    def test_exact_replay_is_one_version_one_evidence_and_one_submission(self):
        first = self.run_lab(); second = self.run_lab()
        self.assertEqual(first, second)
        self.assertEqual(len(self.registry.artifact_history("tenant-a-labs", first["artifact_ref"]["logical_path"])), 1)
        self.assertEqual(len(self.recorder.ledger.evidence(first["hypothesis_id"])), 1)
        self.submit(); self.assertTrue(self.submit()["duplicate"])

    def test_run_id_conflict_and_other_learner_are_rejected(self):
        self.run_lab()
        with self.assertRaises(LearningConflictError): self.run_lab(prediction="Different prediction")
        with self.assertRaises(LearningPermissionError): self.run_lab(self.other)

    def test_unenrolled_draft_role_and_forged_actor_are_denied(self):
        for actor in (Actor("tenant-a", "unenrolled", "learner"), self.teacher,
                      {"tenant_id": "tenant-a", "actor_id": "student", "role": "learner"}):
            with self.subTest(actor=actor), self.assertRaises(LearningPermissionError): self.run_lab(actor)
        with self.assertRaises((LearningPermissionError, KeyError)):
            self.run_lab(Actor("unprovisioned", "student", "learner"))
        with self.platform._connect() as db:
            db.execute("UPDATE learning_course_versions SET status='draft'")
        with self.assertRaises(LearningConflictError): self.run_lab()

    def test_exact_manifest_and_model_source_pins_are_enforced(self):
        with self.assertRaises(LearningConflictError): self.run_lab(manifest_sha256="0" * 64)
        with self.assertRaises(ValueError): self.run_lab(course_version=True)
        with self.assertRaises(LearningPermissionError): self.run_lab(lesson_id="missing")
        other_bridge = LearningLabBridge(self.platform, self.recorder, tenant_projects={"tenant-a": "tenant-a-labs"}, source_commit="b" * 40)
        with self.assertRaises(LearningConflictError):
            other_bridge.run_titan_lab(self.learner, **self.args, prediction="Fixed prediction")
        with patch("merlin.learning_lab_bridge.build_titan_protocol_bundle", return_value={"model_sha256": "0" * 64}):
            with self.assertRaises(LearningConflictError): self.run_lab()

    def test_course_manifest_tampering_is_rejected_even_if_declared_hash_unchanged(self):
        with self.platform._connect() as db:
            manifest = deepcopy(self.course["manifest"]); manifest["title"] = "tampered"
            db.execute("UPDATE learning_course_versions SET manifest_json=?", (json.dumps(manifest),))
        with self.assertRaises(LearningConflictError): self.run_lab()

    def test_crash_after_artifact_persistence_resumes_exact_run(self):
        original = self.recorder.record_existing_artifact
        with patch.object(self.recorder, "record_existing_artifact", side_effect=RuntimeError("simulated recording crash")):
            with self.assertRaises(RuntimeError): self.run_lab()
        with self.platform._connect() as db:
            self.assertEqual(db.execute("SELECT status FROM learning_lab_runs").fetchone()[0], "recording")
        with self.assertRaises(LearningConflictError): self.submit()
        receipt = self.run_lab()
        self.assertEqual(len(self.registry.artifact_history("tenant-a-labs", receipt["artifact_ref"]["logical_path"])), 1)
        self.assertEqual(len(self.recorder.ledger.evidence(receipt["hypothesis_id"])), 1)

    def test_simultaneous_exact_calls_preserve_one_canonical_run(self):
        barrier = threading.Barrier(2); results = []; errors = []
        put = self.registry.put_artifact
        def synchronized(*args, **kwargs):
            barrier.wait(timeout=3)
            return put(*args, **kwargs)
        def run():
            try: results.append(self.run_lab())
            except Exception as exc: errors.append(exc)
        with patch.object(self.registry, "put_artifact", side_effect=synchronized):
            threads = [threading.Thread(target=run) for _ in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(5)
        self.assertFalse(any(thread.is_alive() for thread in threads)); self.assertEqual(errors, [])
        self.assertEqual(len(results), 2); self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.recorder.ledger.evidence(results[0]["hypothesis_id"])), 1)

    def test_blob_and_stored_receipt_tampering_block_submission(self):
        receipt = self.run_lab(); ref = receipt["artifact_ref"]
        path = self.registry.blobs / ref["sha256"][:2] / ref["sha256"][2:]
        original = path.read_bytes(); path.write_bytes(b"tampered")
        with self.assertRaises(RuntimeError): self.submit()
        path.write_bytes(original)
        with self.platform._connect() as db:
            altered = deepcopy(receipt); altered["binding"]["learner_id"] = "another-learner"
            db.execute("UPDATE learning_lab_runs SET receipt_json=?", (json.dumps(altered),))
        with self.assertRaises(LearningConflictError): self.submit()
        with self.platform._connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM learning_submissions").fetchone()[0], 0)

    def test_another_tenant_gets_distinct_project_path_and_hypothesis(self):
        first = self.run_lab()
        teacher = Actor("tenant-b", "teacher", "instructor"); reviewer = Actor("tenant-b", "reviewer", "reviewer")
        learner = Actor("tenant-b", "student", "learner"); course = self.course_fixture(teacher, reviewer)
        self.platform.enroll(learner, course["course_id"])
        second = self.bridge.run_titan_lab(learner, **{**self.args, "course_id": course["course_id"],
            "manifest_sha256": course["manifest_sha256"]}, prediction="Fixed structural predictions")
        self.assertNotEqual(first["artifact_ref"]["project_id"], second["artifact_ref"]["project_id"])
        self.assertNotEqual(first["artifact_ref"]["logical_path"], second["artifact_ref"]["logical_path"])
        self.assertNotEqual(first["hypothesis_id"], second["hypothesis_id"])

    def test_no_caller_supplied_artifact_or_model_can_establish_a_lab(self):
        receipt = self.run_lab()
        with self.assertRaises(TypeError): self.run_lab(artifact_ref=receipt["artifact_ref"])
        with self.assertRaises(TypeError): self.submit(artifact_ref=receipt["artifact_ref"])
        receipt["binding"]["source_hashes"]["titan_crypto_lab.py"] = "0" * 64
        self.assertNotEqual(self.run_lab()["binding"]["source_hashes"]["titan_crypto_lab.py"], "0" * 64)

    def test_assessment_cannot_silently_attach_to_a_new_course_revision(self):
        self.run_lab()
        self.platform.create_revision(self.teacher, self.course["course_id"])
        with self.assertRaises(LearningConflictError): self.submit()
        with self.platform._connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM learning_submissions").fetchone()[0], 0)

    def test_provisioning_and_python_39_boundary(self):
        with self.assertRaises(ValueError):
            LearningLabBridge(self.platform, self.recorder, tenant_projects={"a": "same", "b": "same"}, source_commit="a" * 40)
        import merlin.learning_lab_bridge as module
        ast.parse(Path(module.__file__).read_text(), feature_version=(3, 9))


if __name__ == "__main__": unittest.main()
