"""Tenant-scoped Merlin Learning course catalog and immutable publication service.

Identity is deliberately injected by the trusted application layer. Never build an
Actor from request-body fields: production callers must derive it from verified SSO
or an authenticated session. Published course versions are immutable snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping

from .learner_model import LearnerStore, select_next_lesson, learner_subject_id

SCHEMA = "merlin-learning-platform/1"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
ROLES = {"tenant_admin", "instructor", "learner", "reviewer"}


class LearningPermissionError(PermissionError):
    pass


class LearningConflictError(ValueError):
    pass


@dataclass(frozen=True)
class Actor:
    tenant_id: str
    actor_id: str
    role: str


def _required(value: Any, field: str, limit: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} must be a non-empty string of at most {limit} characters")
    return value.strip()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return sha256(_json(value).encode("utf-8")).hexdigest()


class LearningPlatform:
    """SQLite-backed course catalog with tenant isolation and audited state changes."""

    def __init__(self, database: str | Path):
        self.path = str(database)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS learning_courses(
              tenant_id TEXT NOT NULL, course_id TEXT NOT NULL, slug TEXT NOT NULL,
              title TEXT NOT NULL, description TEXT NOT NULL, owner_id TEXT NOT NULL,
              current_version INTEGER NOT NULL, created_at REAL NOT NULL,
              PRIMARY KEY(tenant_id,course_id), UNIQUE(tenant_id,slug));
            CREATE TABLE IF NOT EXISTS learning_course_versions(
              tenant_id TEXT NOT NULL, course_id TEXT NOT NULL, version INTEGER NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('draft','published','retired')),
              manifest_json TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
              created_by TEXT NOT NULL, created_at REAL NOT NULL, published_at REAL,
              PRIMARY KEY(tenant_id,course_id,version),
              FOREIGN KEY(tenant_id,course_id) REFERENCES learning_courses(tenant_id,course_id));
            CREATE TABLE IF NOT EXISTS learning_course_reviews(
              tenant_id TEXT NOT NULL, course_id TEXT NOT NULL, version INTEGER NOT NULL,
              reviewer_id TEXT NOT NULL, decision TEXT NOT NULL
                CHECK(decision IN ('approved','changes_requested')),
              notes_sha256 TEXT NOT NULL, reviewed_at REAL NOT NULL,
              PRIMARY KEY(tenant_id,course_id,version,reviewer_id),
              FOREIGN KEY(tenant_id,course_id,version)
                REFERENCES learning_course_versions(tenant_id,course_id,version));
            CREATE TABLE IF NOT EXISTS learning_enrollments(
              tenant_id TEXT NOT NULL, course_id TEXT NOT NULL, version INTEGER NOT NULL,
              learner_id TEXT NOT NULL, enrolled_at REAL NOT NULL, status TEXT NOT NULL,
              PRIMARY KEY(tenant_id,course_id,version,learner_id),
              FOREIGN KEY(tenant_id,course_id,version)
                REFERENCES learning_course_versions(tenant_id,course_id,version));
            CREATE TABLE IF NOT EXISTS learning_submissions(
              tenant_id TEXT NOT NULL, submission_id TEXT NOT NULL, course_id TEXT NOT NULL,
              version INTEGER NOT NULL, lesson_id TEXT NOT NULL, assessment_id TEXT NOT NULL,
              learner_id TEXT NOT NULL, response_json TEXT NOT NULL, response_sha256 TEXT NOT NULL,
              submitted_at REAL NOT NULL, status TEXT NOT NULL
                CHECK(status IN ('pending_review','accepted','needs_revision')),
              PRIMARY KEY(tenant_id,submission_id),
              FOREIGN KEY(tenant_id,course_id,version)
                REFERENCES learning_course_versions(tenant_id,course_id,version));
            CREATE INDEX IF NOT EXISTS learning_submissions_queue
              ON learning_submissions(tenant_id,course_id,version,status,submitted_at);
            CREATE TABLE IF NOT EXISTS learning_submission_reviews(
              review_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, submission_id TEXT NOT NULL,
              reviewer_id TEXT NOT NULL, decision TEXT NOT NULL
                CHECK(decision IN ('accepted','needs_revision')),
              feedback TEXT NOT NULL, rubric_json TEXT NOT NULL, created_at REAL NOT NULL,
              FOREIGN KEY(tenant_id,submission_id)
                REFERENCES learning_submissions(tenant_id,submission_id));
            CREATE TABLE IF NOT EXISTS learning_audit(
              event_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, actor_id TEXT NOT NULL,
              action TEXT NOT NULL, target_id TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
              created_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS learning_audit_tenant_time
              ON learning_audit(tenant_id,created_at);
            """)
    
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _authorize(actor: Actor, roles: set[str]) -> None:
        if not isinstance(actor, Actor):
            raise LearningPermissionError("trusted actor context is required")
        _required(actor.tenant_id, "tenant_id")
        _required(actor.actor_id, "actor_id")
        if actor.role not in ROLES or actor.role not in roles:
            raise LearningPermissionError("actor role is not authorized for this operation")

    def _audit(self, db: sqlite3.Connection, actor: Actor, action: str,
               target_id: str, payload: Mapping[str, Any]) -> None:
        event_id = sha256(f"{actor.tenant_id}:{actor.actor_id}:{action}:{target_id}:{time.time_ns()}".encode()).hexdigest()
        db.execute("INSERT INTO learning_audit VALUES(?,?,?,?,?,?,?)",
                   (event_id, actor.tenant_id, actor.actor_id, action, target_id,
                    _digest(payload), time.time()))

    @staticmethod
    def _empty_manifest(title: str, description: str) -> dict[str, Any]:
        return {"schema": SCHEMA, "title": title, "description": description,
                "modules": [], "objectives": [], "lessons": [], "assessments": [],
                "resources": [], "grading_policy": {"automated_high_stakes": False}}

    def create_course(self, actor: Actor, slug: str, title: str,
                      description: str = "") -> dict[str, Any]:
        self._authorize(actor, {"tenant_admin", "instructor"})
        slug = _required(slug, "slug", 64)
        if not SLUG_RE.fullmatch(slug):
            raise ValueError("slug must be lowercase alphanumeric words separated by hyphens")
        title = _required(title, "title", 240)
        if not isinstance(description, str) or len(description) > 4000:
            raise ValueError("description must be text of at most 4000 characters")
        course_id = sha256(f"{actor.tenant_id}:{slug}".encode()).hexdigest()[:24]
        manifest = self._empty_manifest(title, description)
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM learning_courses WHERE tenant_id=? AND slug=?",
                          (actor.tenant_id, slug)).fetchone():
                raise LearningConflictError("course slug already exists in this tenant")
            db.execute("INSERT INTO learning_courses VALUES(?,?,?,?,?,?,?,?)",
                       (actor.tenant_id, course_id, slug, title, description,
                        actor.actor_id, 1, now))
            db.execute("INSERT INTO learning_course_versions VALUES(?,?,?,?,?,?,?,?,?)",
                       (actor.tenant_id, course_id, 1, "draft", _json(manifest),
                        _digest(manifest), actor.actor_id, now, None))
            self._audit(db, actor, "course.created", course_id, {"slug": slug, "version": 1})
        return self.get_course(actor, course_id)

    def _load_draft(self, db: sqlite3.Connection, actor: Actor, course_id: str):
        row = db.execute("""SELECT c.owner_id,c.current_version,v.status,v.manifest_json
          FROM learning_courses c JOIN learning_course_versions v
          ON v.tenant_id=c.tenant_id AND v.course_id=c.course_id AND v.version=c.current_version
          WHERE c.tenant_id=? AND c.course_id=?""", (actor.tenant_id, course_id)).fetchone()
        if row is None:
            raise KeyError("course not found")
        if actor.role != "tenant_admin" and row["owner_id"] != actor.actor_id:
            raise LearningPermissionError("only the course owner or tenant admin may edit this course")
        if row["status"] != "draft":
            raise LearningConflictError("published course versions are immutable; create a new draft revision")
        return row, json.loads(row["manifest_json"])

    def update_manifest(self, actor: Actor, course_id: str,
                        manifest: Mapping[str, Any]) -> dict[str, Any]:
        self._authorize(actor, {"tenant_admin", "instructor"})
        if not isinstance(manifest, Mapping) or manifest.get("schema") != SCHEMA:
            raise ValueError("manifest must use the supported schema")
        clean = dict(manifest)
        for key in ("modules", "objectives", "lessons", "assessments", "resources"):
            if not isinstance(clean.get(key), list):
                raise ValueError(f"{key} must be a list")
        self._validate_manifest(clean)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row, _ = self._load_draft(db, actor, course_id)
            version = int(row["current_version"])
            db.execute("""UPDATE learning_course_versions SET manifest_json=?,manifest_sha256=?
              WHERE tenant_id=? AND course_id=? AND version=? AND status='draft'""",
              (_json(clean), _digest(clean), actor.tenant_id, course_id, version))
            self._audit(db, actor, "course.manifest.updated", course_id,
                        {"version": version, "manifest_sha256": _digest(clean)})
        return self.get_course(actor, course_id)

    @staticmethod
    def _validate_manifest(manifest: Mapping[str, Any]) -> None:
        objective_ids: set[str] = set()
        prerequisites_by_id: dict[str, list[str]] = {}
        for objective in manifest["objectives"]:
            if not isinstance(objective, dict):
                raise ValueError("objective entries must be objects")
            oid = _required(objective.get("id"), "objective.id", 100)
            if oid in objective_ids:
                raise ValueError("objective IDs must be unique")
            objective_ids.add(oid)
            _required(objective.get("title"), "objective.title", 240)
            if not isinstance(objective.get("description", ""), str):
                raise ValueError("objective description must be text")
            prereqs = objective.get("prerequisites", [])
            if not isinstance(prereqs, list) or any(
                not isinstance(item, str) or not item.strip() for item in prereqs
            ):
                raise ValueError("objective prerequisites must be a list of non-empty IDs")
            if len(set(prereqs)) != len(prereqs):
                raise ValueError("objective prerequisites must be unique")
            if oid in prereqs:
                raise ValueError("objective cannot depend on itself")
            external = objective.get("external_prerequisites", [])
            if not isinstance(external, list) or any(
                not isinstance(item, str) or not item.strip() for item in external
            ) or len(set(external)) != len(external):
                raise ValueError("external_prerequisites must be unique non-empty objective IDs")
            if any(item in objective_ids or item not in prereqs for item in external):
                raise ValueError("external_prerequisites must be declared prerequisites outside this course")
            local_prerequisites = [item for item in prereqs if item not in external]
            if any(item not in objective_ids for item in local_prerequisites):
                raise ValueError("objective prerequisite references an unknown objective")
            prerequisites_by_id[oid] = local_prerequisites

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(oid: str) -> None:
            if oid in visiting:
                raise ValueError("objective prerequisite graph contains a cycle")
            if oid in visited:
                return
            visiting.add(oid)
            for prerequisite in prerequisites_by_id[oid]:
                visit(prerequisite)
            visiting.remove(oid)
            visited.add(oid)

        for oid in sorted(objective_ids):
            visit(oid)

        def unique_ids(items: list[Any], kind: str) -> set[str]:
            ids: set[str] = set()
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError(f"{kind} entries must be objects")
                identifier = _required(item.get("id"), f"{kind}.id", 100)
                if identifier in ids:
                    raise ValueError(f"{kind} IDs must be unique")
                ids.add(identifier)
            return ids

        lesson_ids = unique_ids(manifest["lessons"], "lesson")
        for lesson in manifest["lessons"]:
            _required(lesson.get("title"), "lesson.title", 240)
            if lesson.get("objective_id") not in objective_ids:
                raise ValueError("lesson must reference a known objective")
            if not isinstance(lesson.get("body", ""), str):
                raise ValueError("lesson body must be text")
            for field in ("pathways", "interest_tags"):
                if field in lesson and (
                    not isinstance(lesson[field], list)
                    or any(not isinstance(value, str) or not value.strip() for value in lesson[field])
                ):
                    raise ValueError(f"lesson {field} must be a list of non-empty strings")

        unique_ids(manifest["resources"], "resource")
        for resource in manifest["resources"]:
            _required(resource.get("title"), "resource.title", 240)
            uri = _required(resource.get("source_uri"), "resource.source_uri", 2048)
            if not uri.startswith("https://"):
                raise ValueError("learning resources must use HTTPS source URIs")
            _required(resource.get("license"), "resource.license", 120)
            _required(resource.get("creator"), "resource.creator", 240)

        unique_ids(manifest["assessments"], "assessment")
        for assessment in manifest["assessments"]:
            _required(assessment.get("title"), "assessment.title", 240)
            if assessment.get("objective_id") not in objective_ids:
                raise ValueError("assessment must reference a known objective")
            high_stakes = assessment.get("high_stakes", False)
            human_review = assessment.get("human_review_required", False)
            if not isinstance(high_stakes, bool) or not isinstance(human_review, bool):
                raise ValueError("assessment review flags must be boolean")
            if high_stakes and not human_review:
                raise ValueError("high-stakes assessments require human review")

    def review_course(self, actor: Actor, course_id: str, version: int,
                      decision: str, notes: str = "") -> dict[str, Any]:
        self._authorize(actor, {"reviewer"})
        if decision not in {"approved", "changes_requested"}:
            raise ValueError("decision must be approved or changes_requested")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError("version must be a positive integer")
        if not isinstance(notes, str) or len(notes) > 4000:
            raise ValueError("review notes must be text of at most 4000 characters")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT c.owner_id,v.status FROM learning_courses c
              JOIN learning_course_versions v ON v.tenant_id=c.tenant_id
              AND v.course_id=c.course_id WHERE c.tenant_id=? AND c.course_id=? AND v.version=?""",
              (actor.tenant_id, course_id, version)).fetchone()
            if row is None:
                raise KeyError("course version not found")
            if row["owner_id"] == actor.actor_id:
                raise LearningPermissionError("course authors cannot independently review their own course")
            if row["status"] != "draft":
                raise LearningConflictError("only draft versions can be reviewed")
            notes_hash = sha256(notes.encode("utf-8")).hexdigest()
            db.execute("""INSERT INTO learning_course_reviews VALUES(?,?,?,?,?,?,?)
              ON CONFLICT(tenant_id,course_id,version,reviewer_id) DO UPDATE SET
              decision=excluded.decision,notes_sha256=excluded.notes_sha256,
              reviewed_at=excluded.reviewed_at""",
              (actor.tenant_id, course_id, version, actor.actor_id, decision,
               notes_hash, time.time()))
            self._audit(db, actor, "course.reviewed", course_id,
                        {"version": version, "decision": decision, "notes_sha256": notes_hash})
        return {"course_id": course_id, "version": version, "decision": decision,
                "reviewer_id": actor.actor_id, "notes_sha256": notes_hash}

    def publish_course(self, actor: Actor, course_id: str) -> dict[str, Any]:
        self._authorize(actor, {"tenant_admin", "instructor"})
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT c.owner_id,c.current_version,v.status,v.manifest_json
              FROM learning_courses c JOIN learning_course_versions v
              ON v.tenant_id=c.tenant_id AND v.course_id=c.course_id AND v.version=c.current_version
              WHERE c.tenant_id=? AND c.course_id=?""",
              (actor.tenant_id, course_id)).fetchone()
            if row is None:
                raise KeyError("course not found")
            if actor.role == "instructor" and row["owner_id"] != actor.actor_id:
                raise LearningPermissionError("instructor may publish only their own course")
            if row["status"] != "draft":
                raise LearningConflictError("only a draft course version can be published")
            manifest = json.loads(row["manifest_json"])
            self._validate_manifest(manifest)
            approved = db.execute("""SELECT 1 FROM learning_course_reviews
              WHERE tenant_id=? AND course_id=? AND version=? AND decision='approved'
              AND reviewer_id<>? LIMIT 1""",
              (actor.tenant_id, course_id, row["current_version"], row["owner_id"])).fetchone()
            if approved is None:
                raise LearningConflictError("independent reviewer approval is required before publication")
            now = time.time()
            db.execute("""UPDATE learning_course_versions SET status='published',published_at=?
              WHERE tenant_id=? AND course_id=? AND version=?""",
              (now, actor.tenant_id, course_id, row["current_version"]))
            self._audit(db, actor, "course.published", course_id,
                        {"version": row["current_version"], "manifest_sha256": _digest(manifest)})
        return self.get_course(actor, course_id)

    def create_revision(self, actor: Actor, course_id: str) -> dict[str, Any]:
        self._authorize(actor, {"tenant_admin", "instructor"})
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            course = db.execute("SELECT * FROM learning_courses WHERE tenant_id=? AND course_id=?",
                                (actor.tenant_id, course_id)).fetchone()
            if course is None:
                raise KeyError("course not found")
            if actor.role != "tenant_admin" and course["owner_id"] != actor.actor_id:
                raise LearningPermissionError("only the course owner or tenant admin may revise")
            old = db.execute("""SELECT * FROM learning_course_versions WHERE tenant_id=?
              AND course_id=? AND version=?""",
              (actor.tenant_id, course_id, course["current_version"])).fetchone()
            if old["status"] != "published":
                raise LearningConflictError("a revision can be created only from a published version")
            version = int(course["current_version"]) + 1
            now = time.time()
            db.execute("INSERT INTO learning_course_versions VALUES(?,?,?,?,?,?,?,?,?)",
                       (actor.tenant_id, course_id, version, "draft", old["manifest_json"],
                        old["manifest_sha256"], actor.actor_id, now, None))
            db.execute("UPDATE learning_courses SET current_version=? WHERE tenant_id=? AND course_id=?",
                       (version, actor.tenant_id, course_id))
            self._audit(db, actor, "course.revision.created", course_id,
                        {"from_version": old["version"], "to_version": version})
        return self.get_course(actor, course_id)

    def submit_assessment(self, actor: Actor, course_id: str, submission_id: str,
                          lesson_id: str, task_id: str, response: Any) -> dict[str, Any]:
        """Append learner work for independent human review; never award mastery."""
        self._authorize(actor, {"learner"})
        submission_id = _required(submission_id, "submission_id", 120)
        lesson_id = _required(lesson_id, "lesson_id", 100)
        task_id = _required(task_id, "task_id", 120)
        if not isinstance(response, (str, dict, list)):
            raise ValueError("response must be text, an object, or a list")
        response_json = _json(response)
        if len(response_json.encode("utf-8")) > 65536:
            raise ValueError("response exceeds the 64 KiB submission limit")
        response_sha = sha256(response_json.encode("utf-8")).hexdigest()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM learning_submissions WHERE tenant_id=? AND submission_id=?",
                (actor.tenant_id, submission_id)).fetchone()
            if existing is not None:
                if existing["learner_id"] != actor.actor_id:
                    raise LearningPermissionError("submission belongs to another learner")
                same = (existing["course_id"] == course_id
                        and existing["lesson_id"] == lesson_id
                        and existing["response_sha256"] == response_sha)
                if not same:
                    raise LearningConflictError("submission_id was already used for different work")
                return {"submission_id": submission_id, "course_id": course_id,
                        "version": existing["version"], "status": existing["status"],
                        "duplicate": True, "mastery_updated": False,
                        "proof_qualified": False}
            course = db.execute("""SELECT c.current_version,v.status,v.manifest_json
              FROM learning_courses c JOIN learning_course_versions v
              ON v.tenant_id=c.tenant_id AND v.course_id=c.course_id AND v.version=c.current_version
              WHERE c.tenant_id=? AND c.course_id=?""",
              (actor.tenant_id, course_id)).fetchone()
            if course is None:
                raise KeyError("course not found")
            if course["status"] != "published":
                raise LearningConflictError("submissions require a published course version")
            version = int(course["current_version"])
            enrolled = db.execute("""SELECT 1 FROM learning_enrollments
              WHERE tenant_id=? AND course_id=? AND version=? AND learner_id=? AND status='active'""",
              (actor.tenant_id, course_id, version, actor.actor_id)).fetchone()
            if enrolled is None:
                raise LearningPermissionError("learner is not enrolled in this course version")
            manifest = json.loads(course["manifest_json"])
            lesson = next((item for item in manifest["lessons"] if item["id"] == lesson_id), None)
            if lesson is None or not isinstance(lesson.get("exercise"), dict):
                raise ValueError("lesson does not contain a configured exercise")
            if lesson["exercise"].get("task_id") != task_id:
                raise ValueError("task_id does not match the selected lesson exercise")
            assessment = next((item for item in manifest["assessments"]
                               if item.get("objective_id") == lesson.get("objective_id")), None)
            if assessment is None:
                raise ValueError("lesson objective has no configured assessment")
            if assessment.get("human_review_required") is not True:
                raise LearningConflictError("this submission route requires a human-reviewed assessment")
            rubric_sha256 = _digest(assessment.get("rubric", []))
            now = time.time()
            db.execute("""INSERT INTO learning_submissions
              VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
              (actor.tenant_id, submission_id, course_id, version, lesson_id,
               assessment["id"], actor.actor_id, response_json, response_sha,
               now, "pending_review"))
            self._audit(db, actor, "assessment.submitted", submission_id,
                        {"course_id": course_id, "version": version,
                         "lesson_id": lesson_id, "assessment_id": assessment["id"],
                         "response_sha256": response_sha,
                         "rubric_sha256": rubric_sha256})
        return {"submission_id": submission_id, "course_id": course_id,
                "version": version, "lesson_id": lesson_id,
                "assessment_id": assessment["id"], "status": "pending_review",
                "response_sha256": response_sha, "rubric_sha256": rubric_sha256,
                "duplicate": False, "mastery_updated": False, "proof_qualified": False}

    def list_submissions(self, actor: Actor, course_id: str) -> dict[str, Any]:
        self._authorize(actor, {"reviewer", "tenant_admin", "instructor"})
        with self._connect() as db:
            course = db.execute("""SELECT owner_id,current_version FROM learning_courses
              WHERE tenant_id=? AND course_id=?""",
              (actor.tenant_id, course_id)).fetchone()
            if course is None:
                raise KeyError("course not found")
            if actor.role == "instructor" and course["owner_id"] != actor.actor_id:
                raise LearningPermissionError("instructor may view submissions only for their own course")
            if actor.role == "reviewer" and course["owner_id"] == actor.actor_id:
                raise LearningPermissionError("course authors cannot independently review their own learner work")
            rows = db.execute("""SELECT submission_id,course_id,version,lesson_id,assessment_id,
              learner_id,response_json,response_sha256,submitted_at,status
              FROM learning_submissions WHERE tenant_id=? AND course_id=?
              ORDER BY submitted_at,submission_id""",
              (actor.tenant_id, course_id)).fetchall()
        return {"schema": "merlin-learning-submission-queue/1",
                "submissions": [{**dict(row), "response": json.loads(row["response_json"])}
                                for row in rows],
                "count": len(rows)}

    def list_my_submissions(self, actor: Actor, course_id: str) -> dict[str, Any]:
        """Return a learner's own submissions and append-only reviewer feedback."""
        self._authorize(actor, {"learner"})
        with self._connect() as db:
            course = db.execute("""SELECT current_version FROM learning_courses
              WHERE tenant_id=? AND course_id=?""",
              (actor.tenant_id, course_id)).fetchone()
            if course is None:
                raise KeyError("course not found")
            enrolled = db.execute("""SELECT 1 FROM learning_enrollments
              WHERE tenant_id=? AND course_id=? AND learner_id=? AND status='active'""",
              (actor.tenant_id, course_id, actor.actor_id)).fetchone()
            if enrolled is None:
                raise LearningPermissionError("learner is not enrolled in this course")
            rows = db.execute("""SELECT submission_id,version,lesson_id,assessment_id,
              response_sha256,submitted_at,status FROM learning_submissions
              WHERE tenant_id=? AND course_id=? AND learner_id=?
              ORDER BY submitted_at DESC,submission_id""",
              (actor.tenant_id, course_id, actor.actor_id)).fetchall()
            result = []
            for row in rows:
                reviews = db.execute("""SELECT decision,feedback,rubric_json,created_at
                  FROM learning_submission_reviews
                  WHERE tenant_id=? AND submission_id=? ORDER BY created_at,review_id""",
                  (actor.tenant_id, row["submission_id"])).fetchall()
                result.append({
                    **dict(row),
                    "reviews": [
                        {
                            **dict(review),
                            "rubric_scores": (
                                json.loads(review["rubric_json"]).get("scores", {})
                                if isinstance(json.loads(review["rubric_json"]), dict)
                                and "scores" in json.loads(review["rubric_json"])
                                else json.loads(review["rubric_json"])
                            ),
                            "rubric_sha256": (
                                json.loads(review["rubric_json"]).get("rubric_sha256")
                                if isinstance(json.loads(review["rubric_json"]), dict)
                                and "scores" in json.loads(review["rubric_json"])
                                else None
                            ),
                        }
                        for review in reviews
                    ],
                })
        return {"schema": "merlin-learning-my-submissions/1",
                "submissions": result, "count": len(result),
                "mastery_updated": False, "proof_qualified": False}

    def review_submission(self, actor: Actor, course_id: str, submission_id: str,
                          decision: str, feedback: str = "",
                          rubric_scores: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Append an independent human review; scores remain review metadata only."""
        self._authorize(actor, {"reviewer"})
        submission_id = _required(submission_id, "submission_id", 120)
        if decision not in {"accepted", "needs_revision"}:
            raise ValueError("decision must be accepted or needs_revision")
        if not isinstance(feedback, str) or len(feedback) > 8000:
            raise ValueError("feedback must be text of at most 8000 characters")
        if rubric_scores is None:
            rubric_scores = {}
        if not isinstance(rubric_scores, Mapping):
            raise ValueError("rubric_scores must be an object")
        clean_scores: dict[str, float] = {}
        for key, value in rubric_scores.items():
            dimension = _required(key, "rubric dimension", 120)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("rubric scores must be finite numbers from 0 to 1")
            score = float(value)
            if not (0.0 <= score <= 1.0) or score != score or score in (float("inf"), float("-inf")):
                raise ValueError("rubric scores must be finite numbers from 0 to 1")
            clean_scores[dimension] = score
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT s.*,c.owner_id,v.manifest_json
              FROM learning_submissions s JOIN learning_courses c
                ON c.tenant_id=s.tenant_id AND c.course_id=s.course_id
              JOIN learning_course_versions v
                ON v.tenant_id=s.tenant_id AND v.course_id=s.course_id AND v.version=s.version
              WHERE s.tenant_id=? AND s.course_id=? AND s.submission_id=?""",
              (actor.tenant_id, course_id, submission_id)).fetchone()
            if row is None:
                raise KeyError("submission not found")
            if row["owner_id"] == actor.actor_id:
                raise LearningPermissionError("course authors cannot independently review learner work")
            manifest = json.loads(row["manifest_json"])
            assessment = next((item for item in manifest["assessments"]
                               if item.get("id") == row["assessment_id"]), None)
            if assessment is None:
                raise ValueError("submission assessment is missing from its immutable course version")
            rubric_sha256 = _digest(assessment.get("rubric", []))
            allowed_dimensions = {item.get("dimension") for item in assessment.get("rubric", [])
                                  if isinstance(item, dict) and isinstance(item.get("dimension"), str)}
            if set(clean_scores) - allowed_dimensions:
                raise ValueError("rubric score references an unknown assessment dimension")
            review_id = sha256(f"{actor.tenant_id}:{submission_id}:{actor.actor_id}:{time.time_ns()}".encode()).hexdigest()
            now = time.time()
            db.execute("INSERT INTO learning_submission_reviews VALUES(?,?,?,?,?,?,?,?)",
              (review_id, actor.tenant_id, submission_id, actor.actor_id, decision,
               feedback, _json({"rubric_sha256": rubric_sha256, "scores": clean_scores}), now))
            db.execute("""UPDATE learning_submissions SET status=?
              WHERE tenant_id=? AND submission_id=?""",
              (decision, actor.tenant_id, submission_id))
            self._audit(db, actor, "assessment.reviewed", submission_id,
                        {"review_id": review_id, "decision": decision,
                         "feedback_sha256": sha256(feedback.encode("utf-8")).hexdigest(),
                         "rubric_scores": clean_scores,
                         "rubric_sha256": rubric_sha256})
        return {"review_id": review_id, "submission_id": submission_id,
                "decision": decision, "reviewer_id": actor.actor_id,
                "rubric_scores": clean_scores, "rubric_sha256": rubric_sha256,
                "mastery_updated": False, "proof_qualified": False}

    def enroll(self, actor: Actor, course_id: str, learner_id: str | None = None) -> dict[str, Any]:
        self._authorize(actor, {"tenant_admin", "instructor", "learner"})
        target = actor.actor_id if actor.role == "learner" else _required(learner_id, "learner_id")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            course = db.execute("""SELECT c.current_version,v.status FROM learning_courses c
              JOIN learning_course_versions v ON v.tenant_id=c.tenant_id AND v.course_id=c.course_id
              AND v.version=c.current_version WHERE c.tenant_id=? AND c.course_id=?""",
              (actor.tenant_id, course_id)).fetchone()
            if course is None:
                raise KeyError("course not found")
            if course["status"] != "published":
                raise LearningConflictError("course must be published before enrollment")
            now = time.time()
            db.execute("""INSERT OR IGNORE INTO learning_enrollments
              VALUES(?,?,?,?,?,?)""",
              (actor.tenant_id, course_id, course["current_version"], target, now, "active"))
            self._audit(db, actor, "learner.enrolled", course_id,
                        {"learner_id": target, "version": course["current_version"]})
        return {"course_id": course_id, "version": course["current_version"],
                "learner_id": target, "status": "active"}

    def list_courses(self, actor: Actor) -> dict[str, Any]:
        """Return tenant-scoped course summaries appropriate to the actor's role."""
        self._authorize(actor, ROLES)
        clauses = ["c.tenant_id=?"]
        params: list[Any] = [actor.tenant_id]
        if actor.role == "instructor":
            clauses.append("c.owner_id=?")
            params.append(actor.actor_id)
        elif actor.role == "learner":
            clauses.append("v.status='published'")
        elif actor.role == "reviewer":
            clauses.append("""((v.status='draft' AND c.owner_id<>?)
              OR (v.status='published' AND c.owner_id<>? AND EXISTS(
                SELECT 1 FROM learning_submissions s
                WHERE s.tenant_id=c.tenant_id AND s.course_id=c.course_id
                  AND s.status='pending_review')) )""")
            params.extend([actor.actor_id, actor.actor_id])
        where = " AND ".join(clauses)
        with self._connect() as db:
            rows = db.execute(f"""SELECT c.course_id,c.slug,c.title,c.description,
                c.owner_id,c.current_version,v.status,v.manifest_sha256,v.manifest_json,
                e.status AS enrollment_status
              FROM learning_courses c JOIN learning_course_versions v
                ON v.tenant_id=c.tenant_id AND v.course_id=c.course_id
                AND v.version=c.current_version
              LEFT JOIN learning_enrollments e
                ON e.tenant_id=c.tenant_id AND e.course_id=c.course_id
                AND e.version=c.current_version AND e.learner_id=?
              WHERE {where}
              ORDER BY c.title COLLATE NOCASE,c.course_id""",
              (actor.actor_id, *params)).fetchall()
        courses = []
        for row in rows:
            manifest = json.loads(row["manifest_json"])
            courses.append({
                "course_id": row["course_id"], "slug": row["slug"],
                "title": row["title"], "description": row["description"],
                "owner_id": row["owner_id"], "version": row["current_version"],
                "status": row["status"], "manifest_sha256": row["manifest_sha256"],
                "objective_count": len(manifest.get("objectives", [])),
                "lesson_count": len(manifest.get("lessons", [])),
                "enrollment_status": row["enrollment_status"],
            })
        return {"schema": "merlin-learning-course-list/1",
                "tenant_id": actor.tenant_id, "role": actor.role,
                "courses": courses, "count": len(courses)}

    def get_course(self, actor: Actor, course_id: str, version: int | None = None) -> dict[str, Any]:
        self._authorize(actor, ROLES)
        with self._connect() as db:
            if version is None:
                row = db.execute("""SELECT c.slug,c.title,c.description,c.current_version,v.*
                  FROM learning_courses c JOIN learning_course_versions v
                  ON v.tenant_id=c.tenant_id AND v.course_id=c.course_id AND v.version=c.current_version
                  WHERE c.tenant_id=? AND c.course_id=?""",
                  (actor.tenant_id, course_id)).fetchone()
            else:
                row = db.execute("""SELECT c.slug,c.title,c.description,c.current_version,v.*
                  FROM learning_courses c JOIN learning_course_versions v
                  ON v.tenant_id=c.tenant_id AND v.course_id=c.course_id
                  WHERE c.tenant_id=? AND c.course_id=? AND v.version=?""",
                  (actor.tenant_id, course_id, version)).fetchone()
        if row is None:
            raise KeyError("course not found")
        if actor.role == "learner":
            with self._connect() as db:
                enrolled = db.execute("""SELECT 1 FROM learning_enrollments WHERE tenant_id=?
                  AND course_id=? AND version=? AND learner_id=? AND status='active'""",
                  (actor.tenant_id, course_id, row["version"], actor.actor_id)).fetchone()
            if not enrolled:
                raise LearningPermissionError("learner is not enrolled in this course version")
        manifest = json.loads(row["manifest_json"])
        return {"schema": SCHEMA, "course_id": course_id, "slug": row["slug"],
                "title": row["title"], "description": row["description"],
                "version": row["version"], "current_version": row["current_version"],
                "status": row["status"], "manifest_sha256": row["manifest_sha256"],
                "manifest": manifest}

    def recommend_next_lesson(self, actor: Actor, course_id: str,
                              learner_store: LearnerStore) -> dict[str, Any]:
        """Use the shared evidence model to recommend a course lesson; never grade or advance."""
        self._authorize(actor, {"learner"})
        course = self.get_course(actor, course_id)
        manifest = course["manifest"]
        graph = {}
        for objective in manifest["objectives"]:
            dimensions = objective.get("dimensions", ["conceptual_explanation", "procedure"])
            if not isinstance(dimensions, list) or not dimensions:
                raise ValueError("objective dimensions must be a non-empty list")
            graph[objective["id"]] = {
                "prerequisites": objective.get("prerequisites", []),
                "dimensions": dimensions,
            }
        lessons = [{
            "lesson_id": lesson["id"],
            "idea_id": lesson["objective_id"],
            "curriculum_id": course_id,
            "pathways": lesson.get("pathways", []),
            "interest_tags": lesson.get("interest_tags", []),
            "estimated_minutes": lesson.get("estimated_minutes", 20),
            "learning_value": lesson.get("learning_value", 0.5),
            "transfer_value": lesson.get("transfer_value", 0.5),
        } for lesson in manifest["lessons"]]
        learner_id = learner_subject_id(actor.tenant_id, actor.actor_id)
        profile = learner_store.get_profile(learner_id)
        recommendation = select_next_lesson(
            learner_id,
            learner_store,
            graph,
            lessons,
            curriculum_id=course_id,
            path_weights=profile["pathway_weights"],
            interests=profile["interests"],
            max_minutes=profile["max_minutes"],
        )
        return {
            "schema": "merlin-learning-course-recommendation/1",
            "course_id": course_id, "course_version": course["version"],
            **recommendation,
        }

    def audit_events(self, actor: Actor, limit: int = 100) -> list[dict[str, Any]]:
        self._authorize(actor, {"tenant_admin", "reviewer"})
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as db:
            rows = db.execute("""SELECT event_id,actor_id,action,target_id,payload_sha256,created_at
              FROM learning_audit WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?""",
              (actor.tenant_id, limit)).fetchall()
        return [dict(row) for row in rows]
