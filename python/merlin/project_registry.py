"""Durable project/artifact registry with immutable blobs and versioned heads.

Artifact bytes are content-addressed and write-once. Logical paths are versioned
pointers; replacing a pointer requires an explicit compare-and-swap precondition.
Hashes establish identity/integrity, not truth or approval.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import time
from typing import Any
from uuid import uuid4


class ArtifactConflict(RuntimeError):
    """A logical artifact head changed or replacement lacked a valid precondition."""


class MerlinRegistry:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.blobs = self.root / "blobs" / "sha256"
        self.blobs.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "merlin.sqlite3"
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def _initialize(self):
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS projects(
              project_id TEXT PRIMARY KEY, name TEXT NOT NULL,
              version TEXT NOT NULL, metadata_json TEXT NOT NULL,
              created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS artifacts(
              digest TEXT PRIMARY KEY, media_type TEXT NOT NULL,
              size_bytes INTEGER NOT NULL, relative_path TEXT NOT NULL,
              created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS project_artifacts(
              project_id TEXT NOT NULL REFERENCES projects(project_id),
              digest TEXT NOT NULL REFERENCES artifacts(digest),
              logical_path TEXT NOT NULL,
              generation INTEGER NOT NULL DEFAULT 1,
              PRIMARY KEY(project_id, logical_path));
            CREATE TABLE IF NOT EXISTS artifact_versions(
              version_id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL REFERENCES projects(project_id),
              logical_path TEXT NOT NULL,
              digest TEXT NOT NULL REFERENCES artifacts(digest),
              parent_version_id TEXT,
              generation INTEGER NOT NULL,
              actor TEXT NOT NULL,
              operation_id TEXT NOT NULL,
              created_at REAL NOT NULL,
              pre_change_recovery_id TEXT);
            CREATE INDEX IF NOT EXISTS artifact_versions_path
              ON artifact_versions(project_id, logical_path, generation);
            CREATE TABLE IF NOT EXISTS recovery_points(
              recovery_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
              manifest_digest TEXT NOT NULL, manifest_json TEXT NOT NULL,
              created_at REAL NOT NULL, actor TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS claims(
              claim_id TEXT PRIMARY KEY, statement TEXT NOT NULL,
              evidence_class TEXT NOT NULL, assumptions_json TEXT NOT NULL,
              status TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS relations(
              source_id TEXT NOT NULL, relation TEXT NOT NULL, target_id TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              PRIMARY KEY(source_id, relation, target_id));
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(project_artifacts)")}
            if "generation" not in columns:
                db.execute("ALTER TABLE project_artifacts ADD COLUMN generation INTEGER NOT NULL DEFAULT 1")
            version_columns = {row["name"] for row in db.execute("PRAGMA table_info(artifact_versions)")}
            if "pre_change_recovery_id" not in version_columns:
                db.execute("ALTER TABLE artifact_versions ADD COLUMN pre_change_recovery_id TEXT")
            # Migrate pre-versioning heads once. Existing blob bytes are not modified.
            db.execute("""
              INSERT INTO artifact_versions(
                version_id, project_id, logical_path, digest, parent_version_id,
                generation, actor, operation_id, created_at)
              SELECT 'legacy:' || pa.project_id || ':' || pa.logical_path,
                     pa.project_id, pa.logical_path, pa.digest, NULL,
                     COALESCE(pa.generation, 1), 'migration', 'legacy-import', ?
              FROM project_artifacts pa
              WHERE NOT EXISTS (
                SELECT 1 FROM artifact_versions av
                WHERE av.project_id=pa.project_id AND av.logical_path=pa.logical_path)
            """, (time.time(),))
            db.executescript("""
            CREATE TRIGGER IF NOT EXISTS artifact_blobs_no_update
              BEFORE UPDATE ON artifacts
              BEGIN SELECT RAISE(ABORT, 'artifact blob metadata is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS artifact_blobs_no_delete
              BEFORE DELETE ON artifacts
              BEGIN SELECT RAISE(ABORT, 'artifact blobs cannot be deleted'); END;
            CREATE TRIGGER IF NOT EXISTS artifact_versions_no_update
              BEFORE UPDATE ON artifact_versions
              BEGIN SELECT RAISE(ABORT, 'artifact versions are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS artifact_versions_no_delete
              BEFORE DELETE ON artifact_versions
              BEGIN SELECT RAISE(ABORT, 'artifact versions cannot be deleted'); END;
            CREATE TRIGGER IF NOT EXISTS recovery_points_no_update
              BEFORE UPDATE ON recovery_points
              BEGIN SELECT RAISE(ABORT, 'recovery points are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS recovery_points_no_delete
              BEFORE DELETE ON recovery_points
              BEGIN SELECT RAISE(ABORT, 'recovery points cannot be deleted'); END;
            CREATE TRIGGER IF NOT EXISTS project_artifacts_no_delete
              BEFORE DELETE ON project_artifacts
              BEGIN SELECT RAISE(ABORT, 'artifact heads cannot be deleted; tombstone instead'); END;
            CREATE TRIGGER IF NOT EXISTS project_artifacts_guard_update
              BEFORE UPDATE ON project_artifacts
              WHEN NEW.project_id != OLD.project_id
                OR NEW.logical_path != OLD.logical_path
                OR NEW.generation != OLD.generation + 1
                OR NEW.digest = OLD.digest
              BEGIN SELECT RAISE(ABORT, 'artifact head update requires a one-step version advance'); END;
            """)

    @staticmethod
    def _validate_path(logical_path: str) -> str:
        if not isinstance(logical_path, str) or not logical_path:
            raise ValueError("artifact logical path is required")
        path = PurePosixPath(logical_path.replace("\\", "/"))
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("artifact logical path must be relative and traversal-free")
        if ":" in path.parts[0]:
            raise ValueError("artifact logical path cannot be drive-qualified")
        return str(path)

    def register_project(self, project_id: str, name: str, version: str = "0.1.0",
                         metadata: dict[str, Any] | None = None) -> None:
        if not isinstance(project_id, str) or not project_id.strip() or not isinstance(name, str) or not name.strip():
            raise ValueError("project ID and name are required")
        payload = json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO projects VALUES(?,?,?,?,?) "
                "ON CONFLICT(project_id) DO UPDATE SET name=excluded.name, "
                "version=excluded.version, metadata_json=excluded.metadata_json",
                (project_id, name, version, payload, time.time()),
            )
            db.commit()

    def _store_blob(self, content: bytes, media_type: str) -> str:
        if not isinstance(content, bytes):
            raise TypeError("artifact content must be bytes")
        digest = hashlib.sha256(content).hexdigest()
        target = self.blobs / digest[:2] / digest[2:]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise RuntimeError("content-addressed blob integrity mismatch")
        else:
            temp = target.with_name(target.name + "." + uuid4().hex + ".tmp")
            try:
                with temp.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                # Atomic create; if another writer won, verify its immutable bytes.
                try:
                    os.link(temp, target)
                except FileExistsError:
                    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                        raise RuntimeError("content-addressed blob integrity mismatch")
            finally:
                temp.unlink(missing_ok=True)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?)",
                       (digest, media_type, len(content), str(target.relative_to(self.root)), time.time()))
            row = db.execute("SELECT size_bytes, relative_path FROM artifacts WHERE digest=?", (digest,)).fetchone()
            if row is None or row["size_bytes"] != len(content):
                raise RuntimeError("artifact metadata integrity mismatch")
            db.commit()
        return digest

    def put_artifact(self, project_id: str, logical_path: str, content: bytes,
                     media_type: str = "application/octet-stream", *,
                     actor: str = "unknown", operation_id: str | None = None) -> str:
        """Create a new path. Existing paths are immutable unless bytes are identical.

        Use replace_artifact() with expected_digest and expected_generation to
        deliberately advance an existing logical path.
        """
        logical_path = self._validate_path(logical_path)
        digest = self._store_blob(content, media_type)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone():
                db.rollback()
                raise KeyError(f"unknown project: {project_id}")
            old = db.execute(
                "SELECT digest, generation FROM project_artifacts WHERE project_id=? AND logical_path=?",
                (project_id, logical_path),
            ).fetchone()
            if old:
                if old["digest"] == digest:
                    db.commit()
                    return digest
                db.rollback()
                raise ArtifactConflict(
                    "logical path already exists; use replace_artifact with the observed digest and generation"
                )
            version_id = "av_" + uuid4().hex
            timestamp = time.time()
            db.execute("INSERT INTO project_artifacts(project_id,digest,logical_path,generation) VALUES(?,?,?,1)",
                       (project_id, digest, logical_path))
            db.execute("""INSERT INTO artifact_versions(
                version_id,project_id,logical_path,digest,parent_version_id,generation,actor,operation_id,created_at
                ) VALUES(?,?,?,?,NULL,1,?,?,?)""",
                (version_id, project_id, logical_path, digest, actor, operation_id or version_id, timestamp))
            db.commit()
        return digest

    def get_artifact_head(self, project_id: str, logical_path: str) -> dict[str, Any] | None:
        logical_path = self._validate_path(logical_path)
        with self._connect() as db:
            row = db.execute("""
              SELECT pa.digest, pa.generation, av.version_id, av.actor, av.operation_id, av.created_at
              FROM project_artifacts pa
              JOIN artifact_versions av ON av.project_id=pa.project_id
                AND av.logical_path=pa.logical_path AND av.generation=pa.generation
              WHERE pa.project_id=? AND pa.logical_path=?
            """, (project_id, logical_path)).fetchone()
        return dict(row) if row else None

    def replace_artifact(self, project_id: str, logical_path: str, content: bytes,
                         *, expected_digest: str, expected_generation: int,
                         media_type: str = "application/octet-stream",
                         actor: str, operation_id: str) -> str:
        """Advance a logical path only if its exact observed head still matches."""
        logical_path = self._validate_path(logical_path)
        if not expected_digest or not isinstance(expected_generation, int) or expected_generation < 1:
            raise ValueError("expected digest and positive expected generation are required")
        if not actor.strip() or not operation_id.strip():
            raise ValueError("actor and operation_id are required")
        digest = self._store_blob(content, media_type)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("""
              SELECT pa.digest,pa.generation,a.size_bytes,a.media_type
              FROM project_artifacts pa JOIN artifacts a USING(digest)
              WHERE pa.project_id=? AND pa.logical_path=?
            """, (project_id, logical_path)).fetchone()
            if old is None:
                db.rollback()
                raise ArtifactConflict("cannot replace a missing artifact head")
            if old["digest"] != expected_digest or old["generation"] != expected_generation:
                db.rollback()
                raise ArtifactConflict("artifact head changed since it was observed; re-read and re-plan")
            if old["digest"] == digest:
                db.commit()
                return digest
            parent = db.execute("""
              SELECT version_id FROM artifact_versions
              WHERE project_id=? AND logical_path=? AND generation=?
            """, (project_id, logical_path, expected_generation)).fetchone()
            if parent is None:
                db.rollback()
                raise RuntimeError("artifact version history is incomplete; refusing replacement")
            next_generation = expected_generation + 1
            version_id = "av_" + uuid4().hex
            timestamp = time.time()
            updated = db.execute("""
              UPDATE project_artifacts SET digest=?, generation=?
              WHERE project_id=? AND logical_path=? AND digest=? AND generation=?
            """, (digest, next_generation, project_id, logical_path, expected_digest, expected_generation))
            if updated.rowcount != 1:
                db.rollback()
                raise ArtifactConflict("compare-and-swap failed")
            recovery_id = "rp_" + uuid4().hex
            recovery_manifest = {
                "schema": "merlin-recovery-manifest/1",
                "project_id": project_id,
                "reason": "pre-change snapshot",
                "operation_id": operation_id,
                "artifacts": [{
                    "path": logical_path, "sha256": old["digest"],
                    "size_bytes": old["size_bytes"], "media_type": old["media_type"],
                    "generation": expected_generation, "disposition": "retained",
                }],
            }
            encoded_manifest = json.dumps(
                recovery_manifest, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False)
            manifest_digest = hashlib.sha256(encoded_manifest.encode("utf-8")).hexdigest()
            db.execute("INSERT INTO recovery_points VALUES(?,?,?,?,?,?)",
                       (recovery_id, project_id, manifest_digest, encoded_manifest, timestamp, actor))
            db.execute("""INSERT INTO artifact_versions(
              version_id,project_id,logical_path,digest,parent_version_id,generation,actor,operation_id,created_at,pre_change_recovery_id
              ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
              (version_id, project_id, logical_path, digest, parent["version_id"],
               next_generation, actor, operation_id, timestamp, recovery_id))
            db.commit()
        return digest

    def artifact_history(self, project_id: str, logical_path: str) -> list[dict[str, Any]]:
        logical_path = self._validate_path(logical_path)
        with self._connect() as db:
            rows = db.execute("""
              SELECT version_id,digest,parent_version_id,generation,actor,operation_id,created_at,pre_change_recovery_id
              FROM artifact_versions WHERE project_id=? AND logical_path=? ORDER BY generation
            """, (project_id, logical_path)).fetchall()
        return [dict(row) for row in rows]

    def get_artifact_bytes(self, digest: str) -> bytes:
        with self._connect() as db:
            row = db.execute("SELECT relative_path,size_bytes FROM artifacts WHERE digest=?", (digest,)).fetchone()
        if row is None:
            raise KeyError(f"unknown artifact digest: {digest}")
        path = self.root / row["relative_path"]
        content = path.read_bytes()
        if len(content) != row["size_bytes"] or hashlib.sha256(content).hexdigest() != digest:
            raise RuntimeError("artifact blob failed exact-byte integrity verification")
        return content

    def verify_artifact(self, digest: str) -> bool:
        try:
            self.get_artifact_bytes(digest)
            return True
        except (KeyError, OSError, RuntimeError):
            return False

    def add_recovery_point(self, recovery_id: str, project_id: str, manifest: dict[str, Any],
                           *, actor: str = "system") -> str:
        encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone():
                db.rollback()
                raise KeyError(project_id)
            db.execute("INSERT INTO recovery_points VALUES(?,?,?,?,?,?)",
                       (recovery_id, project_id, digest, encoded, time.time(), actor))
            db.commit()
        return digest

    def get_recovery_point(self, recovery_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM recovery_points WHERE recovery_id=?", (recovery_id,)).fetchone()
        if row is None:
            raise KeyError(recovery_id)
        manifest = json.loads(row["manifest_json"])
        encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != row["manifest_digest"]:
            raise RuntimeError("recovery manifest integrity mismatch")
        return {**dict(row), "manifest": manifest}

    def verify_artifact_version(self, project_id: str, logical_path: str, generation: int) -> bool:
        with self._connect() as db:
            row = db.execute("""
              SELECT av.digest FROM artifact_versions av
              WHERE av.project_id=? AND av.logical_path=? AND av.generation=?
            """, (project_id, self._validate_path(logical_path), generation)).fetchone()
        return bool(row and self.verify_artifact(row["digest"]))

    def add_claim(self, claim_id: str, statement: str, evidence_class: str,
                  assumptions: tuple[str, ...] = (), status: str = "unreviewed") -> None:
        if not claim_id.strip() or not statement.strip() or not evidence_class.strip():
            raise ValueError("claim identity, statement and evidence class are required")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO claims VALUES(?,?,?,?,?,?)",
                       (claim_id, statement, evidence_class,
                        json.dumps(list(assumptions), sort_keys=True), status, time.time()))
            db.commit()

    def relate(self, source_id: str, relation: str, target_id: str,
               metadata: dict[str, Any] | None = None) -> None:
        if not source_id.strip() or not relation.strip() or not target_id.strip():
            raise ValueError("relation endpoints and type are required")
        encoded = json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT metadata_json FROM relations WHERE source_id=? AND relation=? AND target_id=?",
                (source_id, relation, target_id),
            ).fetchone()
            if existing is not None:
                if existing["metadata_json"] != encoded:
                    db.rollback()
                    raise ValueError("registry relation already exists with different metadata")
                db.commit()
                return
            db.execute("INSERT INTO relations VALUES(?,?,?,?)",
                       (source_id, relation, target_id, encoded))
            db.commit()

    def inventory(self, project_id: str) -> dict[str, Any]:
        with self._connect() as db:
            project = db.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
            if project is None:
                raise KeyError(project_id)
            artifacts = db.execute("""
              SELECT pa.logical_path,a.digest,a.media_type,a.size_bytes,pa.generation
              FROM project_artifacts pa JOIN artifacts a USING(digest)
              WHERE pa.project_id=? ORDER BY pa.logical_path
            """, (project_id,)).fetchall()
        return {
            "project_id": project["project_id"], "name": project["name"],
            "version": project["version"], "metadata": json.loads(project["metadata_json"]),
            "artifacts": [dict(row) for row in artifacts],
        }
