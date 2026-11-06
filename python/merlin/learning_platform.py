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
            CREATE TABLE IF NOT EXISTS learning_enrollments(
              tenant_id TEXT NOT NULL, course_id TEXT NOT NULL, version INTEGER NOT NULL,
              learner_id TEXT NOT NULL, enrolled_at REAL NOT NULL, status TEXT NOT NULL,
              PRIMARY KEY(tenant_id,course_id,version,learner_id),
              FOREIGN KEY(tenant_id,course_id,version)
                REFERENCES learning_course_versions(tenant_id,course_id,version));
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
        objective_ids = set()
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
            if not isinstance(prereqs, list) or any(not isinstance(x, str) for x in prereqs):
                raise ValueError("objective prerequisites must be a list of IDs")
        for objective in manifest["objectives"]:
            if any(p not in objective_ids for p in objective.get("prerequisites", [])):
                raise ValueError("objective prerequisite references an unknown objective")
        for lesson in manifest["lessons"]:
            if not isinstance(lesson, dict):
                raise ValueError("lesson entries must be objects")
            _required(lesson.get("id"), "lesson.id", 100)
            _required(lesson.get("title"), "lesson.title", 240)
            if lesson.get("objective_id") not in objective_ids:
                raise ValueError("lesson must reference a known objective")
            if not isinstance(lesson.get("body", ""), str):
                raise ValueError("lesson body must be text")
        for resource in manifest["resources"]:
            if not isinstance(resource, dict):
                raise ValueError("resource entries must be objects")
            _required(resource.get("id"), "resource.id", 100)
            _required(resource.get("title"), "resource.title", 240)
            _required(resource.get("source_uri"), "resource.source_uri", 2048)
            _required(resource.get("license"), "resource.license", 120)
            _required(resource.get("creator"), "resource.creator", 240)
        for assessment in manifest["assessments"]:
            if not isinstance(assessment, dict):
                raise ValueError("assessment entries must be objects")
            _required(assessment.get("id"), "assessment.id", 100)
            _required(assessment.get("title"), "assessment.title", 240)
            if assessment.get("objective_id") not in objective_ids:
                raise ValueError("assessment must reference a known objective")
            if assessment.get("high_stakes") is True and assessment.get("human_review_required") is not True:
                raise ValueError("high-stakes assessments require human review")

    def publish_course(self, actor: Actor, course_id: str) -> dict[str, Any]:
        self._authorize(actor, {"tenant_admin", "instructor", "reviewer"})
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

    def audit_events(self, actor: Actor, limit: int = 100) -> list[dict[str, Any]]:
        self._authorize(actor, {"tenant_admin", "reviewer"})
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as db:
            rows = db.execute("""SELECT event_id,actor_id,action,target_id,payload_sha256,created_at
              FROM learning_audit WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?""",
              (actor.tenant_id, limit)).fetchall()
        return [dict(row) for row in rows]
