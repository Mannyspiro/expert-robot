"""Small durable project/artifact/claim registry for Merlin foundation.

SQLite stores metadata and typed relationships; immutable SHA-256 blobs store
artifact bytes. Hashes establish identity/integrity, not truth or approval.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any


class MerlinRegistry:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.blobs = self.root / "blobs" / "sha256"
        self.blobs.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "merlin.sqlite3"
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _initialize(self):
        with self._connect() as db:
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
              PRIMARY KEY(project_id, logical_path));
            CREATE TABLE IF NOT EXISTS claims(
              claim_id TEXT PRIMARY KEY, statement TEXT NOT NULL,
              evidence_class TEXT NOT NULL, assumptions_json TEXT NOT NULL,
              status TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS relations(
              source_id TEXT NOT NULL, relation TEXT NOT NULL, target_id TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              PRIMARY KEY(source_id, relation, target_id));
            """)
    
    def register_project(self, project_id: str, name: str, version: str = "0.1.0",
                         metadata: dict[str, Any] | None = None) -> None:
        if not project_id.strip() or not name.strip():
            raise ValueError("project ID and name are required")
        payload = json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"))
        with self._connect() as db:
            db.execute(
                "INSERT INTO projects VALUES(?,?,?,?,?) "
                "ON CONFLICT(project_id) DO UPDATE SET name=excluded.name, "
                "version=excluded.version, metadata_json=excluded.metadata_json",
                (project_id, name, version, payload, time.time()),
            )

    def put_artifact(self, project_id: str, logical_path: str, content: bytes,
                     media_type: str = "application/octet-stream") -> str:
        if not logical_path or logical_path.startswith("/") or ".." in Path(logical_path).parts:
            raise ValueError("artifact logical path must be relative and traversal-free")
        digest = hashlib.sha256(content).hexdigest()
        target = self.blobs / digest[:2] / digest[2:]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise RuntimeError("content-addressed blob integrity mismatch")
        else:
            temp = target.with_suffix(".tmp")
            temp.write_bytes(content)
            os.replace(temp, target)
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone():
                raise KeyError(f"unknown project: {project_id}")
            db.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?)",
                       (digest, media_type, len(content), str(target.relative_to(self.root)), time.time()))
            db.execute("INSERT INTO project_artifacts VALUES(?,?,?) "
                       "ON CONFLICT(project_id,logical_path) DO UPDATE SET digest=excluded.digest",
                       (project_id, digest, logical_path))
        return digest

    def verify_artifact(self, digest: str) -> bool:
        with self._connect() as db:
            row = db.execute("SELECT relative_path FROM artifacts WHERE digest=?", (digest,)).fetchone()
        if row is None:
            return False
        path = self.root / row["relative_path"]
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest

    def add_claim(self, claim_id: str, statement: str, evidence_class: str,
                  assumptions: tuple[str, ...] = (), status: str = "unreviewed") -> None:
        if not claim_id.strip() or not statement.strip() or not evidence_class.strip():
            raise ValueError("claim identity, statement and evidence class are required")
        with self._connect() as db:
            db.execute("INSERT INTO claims VALUES(?,?,?,?,?,?)",
                       (claim_id, statement, evidence_class,
                        json.dumps(list(assumptions), sort_keys=True), status, time.time()))

    def relate(self, source_id: str, relation: str, target_id: str,
               metadata: dict[str, Any] | None = None) -> None:
        if not source_id.strip() or not relation.strip() or not target_id.strip():
            raise ValueError("relation endpoints and type are required")
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO relations VALUES(?,?,?,?)",
                       (source_id, relation, target_id,
                        json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"))))

    def inventory(self, project_id: str) -> dict[str, Any]:
        with self._connect() as db:
            project = db.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
            if project is None:
                raise KeyError(project_id)
            artifacts = db.execute(
                "SELECT pa.logical_path,a.digest,a.media_type,a.size_bytes "
                "FROM project_artifacts pa JOIN artifacts a USING(digest) "
                "WHERE pa.project_id=? ORDER BY pa.logical_path", (project_id,)
            ).fetchall()
        return {
            "project_id": project["project_id"], "name": project["name"],
            "version": project["version"], "metadata": json.loads(project["metadata_json"]),
            "artifacts": [dict(row) for row in artifacts],
        }
