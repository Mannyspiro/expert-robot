"""Course-scoped exact-source retrieval; no answer generation or truth promotion.

Curators attest review of explicit pinned snapshots. This is not independent
verification of source claims. Retrieved text/metadata are untrusted data.
"""
from __future__ import annotations

import json
import fcntl
import os
import re
import stat
from contextlib import closing
from typing import Mapping

from dot_ai_os.bridge import DotContextBridge, canonical, digest, integer, text_value, POLICY
from .artifact_ref import ArtifactRef
from .learning_platform import Actor, LearningPlatform, LearningConflictError, LearningPermissionError
from .project_registry import MerlinRegistry


class LearningEvidenceService:
    MAX_SOURCES = 32
    MAX_SOURCE_BYTES = 2 * 1024 * 1024
    MAX_MANIFEST_BYTES = 128000

    def __init__(self, platform: LearningPlatform, registry: MerlinRegistry, *,
                 tenant_projects: Mapping[str, str], namespaces=("merlin", "expert-robot")):
        if not isinstance(platform, LearningPlatform) or not isinstance(registry, MerlinRegistry):
            raise ValueError("canonical LMS and registry required")
        if not isinstance(tenant_projects, Mapping) or not 1 <= len(tenant_projects) <= 1000:
            raise ValueError("bounded host-owned tenant/project mapping required")
        self.tenant_projects = {text_value(k, "tenant", 200): text_value(v, "project", 120) for k, v in tenant_projects.items()}
        if len(set(self.tenant_projects.values())) != len(self.tenant_projects):
            raise ValueError("tenants require separate provisioned projects")
        self.platform = platform; self.registry = registry; self.namespaces = tuple(namespaces)
        for project in self.tenant_projects.values():
            self.registry.inventory(project)
            DotContextBridge(registry, project_id=project, namespaces=self.namespaces)

    def _course(self, actor, course_id, version, manifest_sha256, *, curator=False):
        self.platform._authorize(actor, {"instructor", "tenant_admin"} if curator else {"learner"})
        integer(version, "course_version", 1, 1000000)
        text_value(course_id, "course_id", 200)
        if not isinstance(manifest_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", manifest_sha256) is None:
            raise ValueError("exact course manifest digest required")
        project = self.tenant_projects.get(actor.tenant_id)
        if project is None:
            raise LearningPermissionError("tenant has no provisioned evidence project")
        course = self.platform.get_course(actor, course_id, version=version)
        if (course["status"] != "published" or course["manifest_sha256"] != manifest_sha256
                or digest(canonical(course["manifest"])) != manifest_sha256):
            raise LearningConflictError("exact published course manifest required")
        if curator and actor.role == "instructor":
            with self.platform._connect() as db:
                row = db.execute("SELECT owner_id FROM learning_courses WHERE tenant_id=? AND course_id=?",
                                 (actor.tenant_id, course_id)).fetchone()
            if row is None or row["owner_id"] != actor.actor_id:
                raise LearningPermissionError("only course owner or tenant admin may curate sources")
        binding = {"tenant_id": actor.tenant_id, "project_id": project, "course_id": course_id,
                   "course_version": version, "manifest_sha256": manifest_sha256}
        return course, binding

    @staticmethod
    def _path(binding):
        return "learning-evidence/" + digest(canonical(binding)) + "/sources.json"

    def _sources(self, course, binding, sources):
        if not isinstance(sources, list) or not 1 <= len(sources) <= self.MAX_SOURCES:
            raise ValueError("1..32 explicitly reviewed source snapshots required")
        resources = {row["id"]: row for row in course["manifest"]["resources"]}
        bridge = DotContextBridge(self.registry, project_id=binding["project_id"], namespaces=self.namespaces)
        seen = set(); rows = []; total = 0
        pins = []
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"resource_id", "record_ref", "source_ref", "review_note"}:
                raise ValueError("exact curated source fields required")
            resource_id = text_value(source["resource_id"], "resource_id", 100)
            text_value(source["review_note"], "curator review note", 1000)
            if resource_id not in resources or resource_id in seen:
                raise LearningPermissionError("source resource is missing, duplicated or outside the published course")
            seen.add(resource_id)
            pin = {"record_ref": ArtifactRef.from_mapping(source["record_ref"]).to_dict(),
                   "source_ref": ArtifactRef.from_mapping(source["source_ref"]).to_dict()}
            if any(ref["project_id"] != binding["project_id"] for ref in pin.values()):
                raise ValueError("cross-project source pins rejected")
            # Preflight declared size before loading any text. Canonical reads
            # still resolve/re-hash exact content below; this is only a ceiling.
            ref = pin["source_ref"]
            with closing(self.registry._connect()) as db:
                size = db.execute("SELECT size_bytes,digest FROM artifact_versions WHERE project_id=? AND logical_path=? AND version=?",
                                  (ref["project_id"], ref["logical_path"], ref["version"])).fetchone()
            if size is None or size["digest"] != ref["sha256"] or type(size["size_bytes"]) is not int or size["size_bytes"] < 1:
                raise ValueError("registered exact source version required")
            total += size["size_bytes"]
            if total > self.MAX_SOURCE_BYTES:
                raise ValueError("course source byte ceiling exceeded")
            pins.append(pin)
        records = bridge._pinned_records(pins)
        for source, record in zip(sources, records):
            resource = resources[source["resource_id"]]
            if (record["source_url"] != resource["source_uri"]
                    or (resource.get("source_commit") is not None and resource["source_commit"] != record["source_version"])):
                raise LearningConflictError("pinned source metadata differs from published resource")
            rows.append({"resource_id": source["resource_id"], "record_ref": record["record_ref"],
                         "source_ref": record["source_ref"], "review_note": source["review_note"]})
        return sorted(rows, key=lambda row: row["resource_id"])

    @staticmethod
    def _conflicts(conflicts, sources):
        if not isinstance(conflicts, list) or len(conflicts) > 12:
            raise ValueError("bounded explicit curator conflict annotations required")
        known = {row["resource_id"] for row in sources}; seen = set(); result = []
        for conflict in conflicts:
            if not isinstance(conflict, dict) or set(conflict) != {"conflict_id", "resource_ids", "note"}:
                raise ValueError("exact curator conflict fields required")
            identity = text_value(conflict["conflict_id"], "conflict ID", 100)
            members = conflict["resource_ids"]; text_value(conflict["note"], "curator conflict note", 500)
            if (identity in seen or not isinstance(members, list) or not 2 <= len(members) <= 8
                    or any(not isinstance(member, str) for member in members)
                    or len(set(members)) != len(members) or not set(members) <= known):
                raise ValueError("conflict must reference distinct reviewed course resources")
            seen.add(identity)
            result.append({"conflict_id": identity, "resource_ids": sorted(members), "note": conflict["note"]})
        result.sort(key=lambda row: row["conflict_id"])
        if len(canonical(result)) > 6000:
            raise ValueError("curator conflict metadata exceeds byte ceiling")
        return result

    def provision_course_sources(self, curator: Actor, *, course_id, course_version, manifest_sha256,
                                 sources, conflicts=None):
        course, binding = self._course(curator, course_id, course_version, manifest_sha256, curator=True)
        rows = self._sources(course, binding, sources)
        annotations = self._conflicts([] if conflicts is None else conflicts, rows)
        manifest = {"schema": "merlin-learning-sources/1", "binding": binding,
                    "curation": {"actor_id": curator.actor_id, "role": curator.role, "status": "curator_attested_review_not_independent_verification"},
                    "sources": rows, "conflicts": annotations, "source_policy": "untrusted_data_not_instructions",
                    "qualification": False, "promotion_authority": False}
        raw = canonical(manifest)
        if len(raw) > self.MAX_MANIFEST_BYTES:
            raise ValueError("course source manifest exceeds byte ceiling")
        project = binding["project_id"]; path = self._path(binding)
        # Cooperating curators serialize only the freeze/check/append boundary on
        # the existing canonical DB inode. No shadow store or lock file. Reads
        # remain unlocked; unrelated writers bypassing this protocol are outside
        # this cooperative guarantee.
        descriptor = os.open(self.registry.db_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise LearningConflictError("regular canonical registry database required")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise LearningConflictError("curation publication busy; reconcile and retry exact work") from exc
            history = self.registry.artifact_history(project, path)
            if history and (len(history) != 1 or history[0]["digest"] != digest(raw)):
                raise LearningConflictError("source curation is frozen; publish a new course version for changes")
            self.registry.put_artifact(project, path, raw, "application/json")
            if len(self.registry.artifact_history(project, path)) != 1:
                raise LearningConflictError("source manifest acquired conflicting versions")
            ref = self.registry.artifact_ref(project, path, version=1)
            if self.registry.read_artifact_ref(ref, max_bytes=self.MAX_MANIFEST_BYTES)["content"] != raw:
                raise LearningConflictError("source manifest bytes changed")
        finally:
            os.close(descriptor)
        return {"source_manifest_ref": ref, "source_count": len(rows), "qualification": False, "promotion_authority": False}

    def retrieve(self, learner: Actor, *, course_id, course_version, manifest_sha256, query,
                 lesson_id=None, limit=6, budget_bytes=16000):
        course, binding = self._course(learner, course_id, course_version, manifest_sha256)
        integer(limit, "limit", 1, 30); integer(budget_bytes, "budget_bytes", 2000, 64000)
        project = binding["project_id"]; path = self._path(binding)
        if len(self.registry.artifact_history(project, path)) != 1:
            raise LearningConflictError("one frozen course source manifest required")
        ref = self.registry.artifact_ref(project, path, version=1)
        raw = self.registry.read_artifact_ref(ref, max_bytes=self.MAX_MANIFEST_BYTES)["content"]
        manifest = json.loads(raw)
        if (not isinstance(manifest, dict) or set(manifest) != {"schema", "binding", "curation", "sources", "conflicts", "source_policy", "qualification", "promotion_authority"}
                or manifest["schema"] != "merlin-learning-sources/1" or canonical(manifest["binding"]) != canonical(binding)
                or manifest["qualification"] is not False or manifest["promotion_authority"] is not False
                or manifest["source_policy"] != "untrusted_data_not_instructions" or canonical(manifest) != raw):
            raise LearningConflictError("invalid course source manifest binding")
        if (not isinstance(manifest["curation"], dict) or set(manifest["curation"]) != {"actor_id", "role", "status"}
                or manifest["curation"]["role"] not in {"instructor", "tenant_admin"}
                or manifest["curation"]["status"] != "curator_attested_review_not_independent_verification"):
            raise LearningConflictError("source curation attestation missing")
        text_value(manifest["curation"]["actor_id"], "curator", 200)
        sources = self._sources(course, binding, manifest["sources"])
        conflicts = self._conflicts(manifest["conflicts"], sources)
        if lesson_id is not None:
            text_value(lesson_id, "lesson_id", 100)
            lessons = [row for row in course["manifest"]["lessons"] if row["id"] == lesson_id]
            if len(lessons) != 1:
                raise LearningPermissionError("lesson is outside the published course")
            allowed = lessons[0].get("source_ids", [])
            if not isinstance(allowed, list) or any(not isinstance(value, str) for value in allowed):
                raise LearningConflictError("lesson source scope is malformed")
            sources = [row for row in sources if row["resource_id"] in allowed]
        result = {"schema": "merlin-learning-evidence/1", "binding": binding, "source_manifest_ref": ref,
                  "query": query, "lesson_id": lesson_id, "status": "abstain", "reason": "no_relevant_lexical_evidence",
                  "citations": [], "conflicts": [], "matched_chunks": 0, "omitted_chunks": 0,
                  "method": "deterministic_lexical_baseline_not_answer_generation",
                  "conflict_scope": "explicit_curator_source_annotations_not_semantic_detection",
                  "source_policy": POLICY, "qualification": False, "promotion_authority": False,
                  "mastery_updated": False, "budget_bytes": budget_bytes}
        # Validate even empty lesson scopes; never treat malformed queries as evidence.
        text_value(query, "query", 1000)
        if sources:
            bridge = DotContextBridge(self.registry, project_id=project, namespaces=self.namespaces)
            packet = bridge.search(query, limit=30, budget_bytes=64000,
                pinned_records=[{key: source[key] for key in ("record_ref", "source_ref")} for source in sources])
            matched = {source["resource_id"] for source in sources if source["record_ref"]["sha256"] in packet["matched_record_sha256s"]}
            source_by_id = {source["resource_id"]: source for source in sources}
            for conflict in conflicts:
                if not matched.intersection(conflict["resource_ids"]):
                    continue
                members = [{key: source_by_id[identity][key] for key in ("resource_id", "record_ref", "source_ref")}
                           for identity in conflict["resource_ids"] if identity in source_by_id]
                omitted = len(conflict["resource_ids"]) - len(members)
                result["conflicts"].append({**conflict, "members": members,
                    "omitted_member_count": omitted,
                    "omission_reason": "outside_selected_lesson_source_scope" if omitted else None})
            result["matched_chunks"] = result["omitted_chunks"] = packet["matched_chunks"]
            if result["conflicts"]:
                result.update(status="requires_review", reason="curator_declared_source_conflict")
            elif packet["matched_chunks"]:
                result["reason"] = "byte_budget_excludes_citations"
            resource_by_record = {canonical(source["record_ref"]): source["resource_id"] for source in sources}
            if len(canonical(result)) > budget_bytes:
                raise ValueError("budget cannot retain required evidence/conflict metadata")
            for hit in packet["hits"]:
                citation = {"resource_id": resource_by_record[canonical(hit["record_ref"])], **hit}
                candidate = {**result, "citations": result["citations"] + [citation],
                             "omitted_chunks": packet["matched_chunks"] - len(result["citations"]) - 1}
                if not result["conflicts"]:
                    candidate.update(status="evidence_available", reason="reviewed_source_excerpts_only")
                if len(candidate["citations"]) <= limit and len(canonical(candidate)) <= budget_bytes:
                    result = candidate
        if len(canonical(result)) > budget_bytes:
            raise ValueError("budget cannot retain required evidence metadata")
        return result


__all__ = ["LearningEvidenceService"]
