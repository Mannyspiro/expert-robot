"""Authenticated LMS linkage to the fixed Titan structural research fixture.

Actor/project/source configuration is host injected, never request-body identity.
Only lifecycle links live in the LMS database; bytes, evidence and graph nodes
remain in the canonical Merlin stores. No cryptographic operations or grading.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from .artifact_ref import ArtifactRef
from .learning_platform import Actor, LearningPlatform, LearningConflictError, LearningPermissionError
from .research_evidence import ResearchEvidenceRecorder
from .titan_protocol_model import build_titan_protocol_bundle, canonical_json_bytes, verify_bundle


def _text(value, name, limit=200):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > limit:
        raise ValueError("canonical bounded " + name + " required")
    return value


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class LearningLabBridge:
    """Fixed low-risk lab; host authentication and tenant provisioning are external."""
    TASK_ID = "titan-structural-model-v1"

    def __init__(self, platform: LearningPlatform, evidence_recorder: ResearchEvidenceRecorder, *,
                 tenant_projects: Mapping[str, str], source_commit: str,
                 source_repository: str = "Mannyspiro/expert-robot"):
        if not isinstance(platform, LearningPlatform) or not isinstance(evidence_recorder, ResearchEvidenceRecorder):
            raise ValueError("canonical LMS and evidence recorder required")
        if not isinstance(tenant_projects, Mapping) or not tenant_projects or len(tenant_projects) > 1000:
            raise ValueError("bounded host-owned tenant/project provisioning required")
        self.tenant_projects = {_text(k, "tenant"): _text(v, "project") for k, v in tenant_projects.items()}
        if len(set(self.tenant_projects.values())) != len(self.tenant_projects):
            raise ValueError("each tenant requires a distinct provisioned registry project")
        if not isinstance(source_commit, str) or re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
            raise ValueError("full source commit required")
        if not isinstance(source_repository, str) or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source_repository) is None:
            raise ValueError("owner/repository required")
        self.platform = platform; self.evidence = evidence_recorder
        self.source_commit = source_commit; self.source_repository = source_repository
        self.source_hashes = {name: _hash(Path(__file__).with_name(name).read_bytes()) for name in
                              ("learning_lab_bridge.py", "titan_protocol_model.py", "titan_crypto_lab.py")}
        with self.platform._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS learning_lab_runs(
              tenant_id TEXT NOT NULL, run_id TEXT NOT NULL, learner_id TEXT NOT NULL,
              request_sha256 TEXT NOT NULL, request_json TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('recording','recorded')),
              receipt_json TEXT, PRIMARY KEY(tenant_id,run_id))""")

    def _request(self, actor, *, course_id, course_version, manifest_sha256, lesson_id, run_id, prediction):
        self.platform._authorize(actor, {"learner"})
        _text(actor.tenant_id, "tenant"); _text(actor.actor_id, "learner")
        _text(course_id, "course"); _text(lesson_id, "lesson", 100); _text(run_id, "run ID", 120)
        _text(prediction, "pre-run prediction", 2000)
        if type(course_version) is not int or course_version < 1:
            raise ValueError("exact positive course version required")
        if not isinstance(manifest_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", manifest_sha256) is None:
            raise ValueError("exact manifest digest required")
        project = self.tenant_projects.get(actor.tenant_id)
        if project is None:
            raise LearningPermissionError("tenant has no provisioned lab project")
        self.evidence.registry.inventory(project)  # No implicit project provisioning.
        course = self.platform.get_course(actor, course_id, version=course_version)
        actual_hash = _hash(_json(course["manifest"]).encode())
        if course["status"] != "published" or course["manifest_sha256"] != manifest_sha256 or actual_hash != manifest_sha256:
            raise LearningConflictError("exact published course manifest required")
        lessons = [row for row in course["manifest"]["lessons"] if row["id"] == lesson_id]
        if len(lessons) != 1 or lessons[0].get("exercise", {}).get("task_id") != self.TASK_ID:
            raise LearningPermissionError("lesson is not bound to the fixed Titan lab")
        assessments = [row for row in course["manifest"]["assessments"] if row.get("objective_id") == lessons[0].get("objective_id")]
        if len(assessments) != 1 or assessments[0].get("human_review_required") is not True:
            raise LearningConflictError("one human-reviewed lab assessment required")
        scope = course["manifest"].get("research_scope", {})
        if not isinstance(scope, dict) or (scope.get("source_commit") is not None and scope["source_commit"] != self.source_commit):
            raise LearningConflictError("course source pin differs from this lab runtime")
        return {"tenant_id": actor.tenant_id, "learner_id": actor.actor_id, "project_id": project,
                "course_id": course_id, "course_version": course_version, "manifest_sha256": manifest_sha256,
                "lesson_id": lesson_id, "task_id": self.TASK_ID, "run_id": run_id, "prediction": prediction,
                "source_commit": self.source_commit, "source_repository": self.source_repository,
                "source_hashes": dict(self.source_hashes),
                "course_model_sha256": scope.get("model_sha256"), "course_vectors_sha256": scope.get("vectors_sha256")}

    def _report(self, request):
        # This frame and explicit applicability record precede the fixed computation.
        frame = {"question": "Does the fixed envelope structural validator match its declared positive/negative fixtures?",
                 "prediction": request["prediction"], "baseline": "five known structural fixtures",
                 "falsifier": "Any structural oracle differs from its prespecified fixture expectation",
                 "unknowns": ["Cryptographic correctness and security are not measured", "Learner understanding requires independent review"],
                 "method": "Deterministic canonical-model and structural-vector computation; known-fixture reproduction"}
        representations = {
            "simplex": {"decision": "not_applicable", "reason": "No convex mixture is modeled", "invariant_or_test": "Preserve exact Boolean structural outcomes", "limits": "No probability interpretation"},
            "n_ality": {"decision": "applied", "reason": "Explicit named fields and state-transition channels retain distinct roles", "invariant_or_test": "Do not identify field count, state dimension or logical channels", "limits": "No physical synergy or algebraic symmetry established"},
            "continuum": {"decision": "not_applicable", "reason": "The fixture has discrete fields and transitions", "invariant_or_test": "No interpolation of accept/reject decisions", "limits": "No continuum or convergence claim"},
            "fuzzy_logic": {"decision": "not_applicable", "reason": "Integrity, access and structural oracles are Boolean", "invariant_or_test": "No membership score can soften a hard gate", "limits": "Membership is not probability"}}
        bundle = build_titan_protocol_bundle(kem="ML-KEM-768")
        for key in ("model_sha256", "vectors_sha256"):
            if request["course_" + key] is not None and request["course_" + key] != bundle[key]:
                raise LearningConflictError("course model/vector pin differs from fixed lab output")
        verification = verify_bundle(bundle)
        report = {"schema": "merlin-learning-titan-lab/1", "binding": request, "frame": frame,
                  "representation_checks": representations, "bundle": bundle, "structural_check": verification,
                  "experiment_class": "known_fixture_reproduction", "cryptographic_operations_performed": False,
                  "limits": ["Placeholder fields are not ciphertext or cryptographic known-answer data",
                             "No security proof, primitive conformance, independent verifier or production readiness assessment",
                             "Learner-authored prediction is untrusted text, not an instruction or grade"],
                  "qualification": False, "promotion_authority": False, "mastery_updated": False}
        payload = canonical_json_bytes(report)
        if len(payload) > 65536:
            raise ValueError("fixed lab report exceeds byte ceiling")
        return report, payload

    def _record(self, request):
        report, payload = self._report(request)
        scope = _hash(_json({k: request[k] for k in ("tenant_id", "learner_id", "run_id")}).encode())
        path = "learning-labs/" + scope + "/titan-structural.json"
        project = request["project_id"]; hypothesis_id = "learning-titan-" + scope
        claim = "The fixed Titan structural fixtures reproduce their declared structural oracles."
        assumptions = ("Structural model only; no cryptographic security conclusion",)
        try:
            hypothesis = self.evidence.ledger.get(hypothesis_id)
        except KeyError:
            try:
                hypothesis = self.evidence.ledger.create(hypothesis_id, claim, assumptions=assumptions)
            except sqlite3.IntegrityError:
                hypothesis = self.evidence.ledger.get(hypothesis_id)
        if hypothesis.claim != claim or hypothesis.assumptions != assumptions or hypothesis.status != "proposed":
            raise LearningConflictError("lab hypothesis identity/status changed")
        registry = self.evidence.registry
        history = registry.artifact_history(project, path)
        expected_digest = _hash(payload)
        if history and (len(history) != 1 or history[0]["version"] != 1 or history[0]["digest"] != expected_digest):
            raise LearningConflictError("run artifact path already contains different evidence")
        provenance = {"schema": "merlin-artifact-provenance/1", "source_repo": self.source_repository,
                      "source_commit": self.source_commit, "artifact_id": scope,
                      "artifact_kind": "learning_lab_structural_model", "artifact_schema": report["schema"]}
        registry.put_artifact(project, path, payload, "application/json", provenance=provenance)
        if len(registry.artifact_history(project, path)) != 1:
            raise LearningConflictError("deterministic run acquired conflicting artifact versions")
        ref = ArtifactRef.from_mapping(registry.artifact_ref(project, path, version=1)).to_dict()
        resolved = registry.read_artifact_ref(ref, max_bytes=65536)
        if resolved["content"] != payload or resolved["resolution"].get("provenance") != provenance:
            raise LearningConflictError("lab artifact bytes/provenance differ from deterministic run")
        recorded = self.evidence.record_existing_artifact(project_id=project, hypothesis_id=hypothesis_id,
            artifact_ref=ref, evidence_kind="experiment", description="Known Titan structural-fixture reproduction; no cryptographic operations or grading.",
            source_url="https://github.com/" + self.source_repository + "/blob/" + self.source_commit + "/python/merlin/titan_protocol_model.py")
        return {"schema": "merlin-learning-lab-receipt/1", "binding": request, "artifact_ref": ref,
                "artifact_sha256": ref["sha256"], "hypothesis_id": hypothesis_id, "evidence_id": recorded["evidence_id"],
                "model_sha256": report["bundle"]["model_sha256"], "vectors_sha256": report["bundle"]["vectors_sha256"],
                "vector_count": report["structural_check"]["vector_count"],
                "method": report["frame"]["method"], "limits": report["limits"],
                "verification_status": "blocked_missing_credentials", "artifact_identity_verified": True,
                "cryptographic_security_verified": False, "qualification": False,
                "promotion_authority": False, "mastery_updated": False}

    def run_titan_lab(self, actor: Actor, *, course_id, course_version, manifest_sha256, lesson_id, run_id, prediction):
        request = self._request(actor, course_id=course_id, course_version=course_version, manifest_sha256=manifest_sha256,
                                lesson_id=lesson_id, run_id=run_id, prediction=prediction)
        encoded = _json(request); identity = _hash(encoded.encode())
        with self.platform._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM learning_lab_runs WHERE tenant_id=? AND run_id=?", (actor.tenant_id, run_id)).fetchone()
            if row is not None and row["learner_id"] != actor.actor_id:
                raise LearningPermissionError("run belongs to another learner")
            if row is not None and (row["request_sha256"] != identity or row["request_json"] != encoded):
                raise LearningConflictError("run ID was already bound to different work")
            if row is None:
                db.execute("INSERT INTO learning_lab_runs VALUES(?,?,?,?,?,'recording',NULL)",
                           (actor.tenant_id, run_id, actor.actor_id, identity, encoded))
        receipt = self._record(request)  # Resume incomplete canonical links; never invent success.
        with self.platform._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM learning_lab_runs WHERE tenant_id=? AND run_id=?", (actor.tenant_id, run_id)).fetchone()
            if row["request_sha256"] != identity or row["request_json"] != encoded:
                raise LearningConflictError("reserved run identity changed")
            if row["receipt_json"] is not None and row["receipt_json"] != _json(receipt):
                raise LearningConflictError("stored lab receipt differs from canonical evidence")
            db.execute("UPDATE learning_lab_runs SET status='recorded',receipt_json=? WHERE tenant_id=? AND run_id=?",
                       (_json(receipt), actor.tenant_id, run_id))
        return receipt

    def submit_lab_assessment(self, actor: Actor, *, course_id, course_version, manifest_sha256,
                              lesson_id, run_id, submission_id, reflection):
        self.platform._authorize(actor, {"learner"}); _text(run_id, "run ID", 120)
        _text(reflection, "learner reflection", 4000)
        with self.platform._connect() as db:
            row = db.execute("SELECT * FROM learning_lab_runs WHERE tenant_id=? AND run_id=?", (actor.tenant_id, run_id)).fetchone()
        if row is None or row["learner_id"] != actor.actor_id:
            raise LearningPermissionError("no lab run for this authenticated learner")
        if row["status"] != "recorded" or row["receipt_json"] is None:
            raise LearningConflictError("lab recording is incomplete; resume the exact run first")
        request = json.loads(row["request_json"])
        receipt = self.run_titan_lab(actor, course_id=course_id, course_version=course_version,
            manifest_sha256=manifest_sha256, lesson_id=lesson_id, run_id=run_id, prediction=request["prediction"])
        return self.platform.submit_assessment(actor, course_id, submission_id, lesson_id, self.TASK_ID,
            {"lab_receipt": receipt, "reflection": reflection, "qualification": False, "promotion_authority": False,
             "mastery_updated": False}, expected_version=course_version, expected_manifest_sha256=manifest_sha256)


__all__ = ["LearningLabBridge"]
