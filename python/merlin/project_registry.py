"""Small durable project/artifact/claim registry for Merlin foundation.

SQLite stores metadata and typed relationships; immutable SHA-256 blobs store
artifact bytes. Hashes establish identity/integrity, not truth or approval.
"""
from __future__ import annotations

from contextlib import closing

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Mapping


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
        with closing(self._connect()) as db, db:
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
            CREATE TABLE IF NOT EXISTS capability_qualification_receipts(
              receipt_id TEXT PRIMARY KEY,
              capability_id TEXT NOT NULL,
              artifact_digest TEXT NOT NULL REFERENCES artifacts(digest),
              receipt_json TEXT NOT NULL,
              receipt_sha256 TEXT NOT NULL UNIQUE,
              created_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS capability_receipts_by_capability
              ON capability_qualification_receipts(capability_id, created_at);
            CREATE TRIGGER IF NOT EXISTS capability_receipts_no_update
              BEFORE UPDATE ON capability_qualification_receipts
              BEGIN SELECT RAISE(ABORT, 'capability qualification receipts are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS capability_receipts_no_delete
              BEFORE DELETE ON capability_qualification_receipts
              BEGIN SELECT RAISE(ABORT, 'capability qualification receipts are append-only'); END;
            """)
    
    def register_project(self, project_id: str, name: str, version: str = "0.1.0",
                         metadata: dict[str, Any] | None = None) -> None:
        if not project_id.strip() or not name.strip():
            raise ValueError("project ID and name are required")
        payload = json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"))
        with closing(self._connect()) as db, db:
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
        with closing(self._connect()) as db, db:
            if not db.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone():
                raise KeyError(f"unknown project: {project_id}")
            db.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?)",
                       (digest, media_type, len(content), str(target.relative_to(self.root)), time.time()))
            db.execute("INSERT INTO project_artifacts VALUES(?,?,?) "
                       "ON CONFLICT(project_id,logical_path) DO UPDATE SET digest=excluded.digest",
                       (project_id, digest, logical_path))
        return digest

    def verify_artifact(self, digest: str) -> bool:
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT relative_path FROM artifacts WHERE digest=?", (digest,)).fetchone()
        if row is None:
            return False
        path = self.root / row["relative_path"]
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest

    def add_claim(self, claim_id: str, statement: str, evidence_class: str,
                  assumptions: tuple[str, ...] = (), status: str = "unreviewed") -> None:
        if not claim_id.strip() or not statement.strip() or not evidence_class.strip():
            raise ValueError("claim identity, statement and evidence class are required")
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO claims VALUES(?,?,?,?,?,?)",
                       (claim_id, statement, evidence_class,
                        json.dumps(list(assumptions), sort_keys=True), status, time.time()))

    def relate(self, source_id: str, relation: str, target_id: str,
               metadata: dict[str, Any] | None = None) -> None:
        if not source_id.strip() or not relation.strip() or not target_id.strip():
            raise ValueError("relation endpoints and type are required")
        encoded = json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"))
        with closing(self._connect()) as db, db:
            existing = db.execute(
                "SELECT metadata_json FROM relations WHERE source_id=? AND relation=? AND target_id=?",
                (source_id, relation, target_id),
            ).fetchone()
            if existing is not None:
                if existing["metadata_json"] != encoded:
                    raise ValueError("registry relation already exists with different metadata")
                return
            db.execute("INSERT INTO relations VALUES(?,?,?,?)",
                       (source_id, relation, target_id, encoded))

    @staticmethod
    def _canonical_json(value: Mapping[str, Any]) -> str:
        return json.dumps(dict(value), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)

    @staticmethod
    def _valid_sha256(value: Any) -> bool:
        return (isinstance(value, str) and len(value) == 64
                and all(char in "0123456789abcdef" for char in value))

    def record_capability_qualification(self, receipt: Mapping[str, Any]) -> dict[str, Any]:
        """Append an untrusted qualification claim pending independent CACE review.

        This stores evidence; it does not grant a capability or assert that a
        provider is qualified. Only an independent verifier may promote it.
        """
        if not isinstance(receipt, Mapping):
            raise ValueError("qualification receipt must be an object")
        required = (
            "receipt_id", "capability_id", "capability_version", "provider",
            "model_revision", "heldout_suite", "environment_sha256",
            "artifact_digest", "result", "signer_id", "signed_at",
        )
        normalized: dict[str, Any] = {}
        for key in required:
            value = receipt.get(key)
            if key in {"environment_sha256", "artifact_digest"}:
                if not self._valid_sha256(value):
                    raise ValueError(f"{key} must be a lowercase SHA-256 digest")
                normalized[key] = value
            elif key == "signed_at":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError("signed_at must be a finite positive timestamp")
                if not (0 < float(value) < float("inf")):
                    raise ValueError("signed_at must be a finite positive timestamp")
                normalized[key] = float(value)
            else:
                if not isinstance(value, str) or not value.strip() or len(value) > 512:
                    raise ValueError(f"{key} must be a non-empty string of at most 512 characters")
                normalized[key] = value.strip()
        if normalized["result"] not in {"passed", "failed"}:
            raise ValueError("result must be passed or failed")
        # Preserve additional structured evidence fields in the digest, but do
        # not let them override the validated contract fields.
        for key, value in receipt.items():
            if key not in normalized:
                normalized[key] = value
        encoded = self._canonical_json(normalized)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        artifact_digest = normalized["artifact_digest"]
        if not self.verify_artifact(artifact_digest):
            raise ValueError("qualification evidence artifact is missing or fails digest verification")
        with closing(self._connect()) as db, db:
            existing = db.execute(
                "SELECT receipt_sha256 FROM capability_qualification_receipts WHERE receipt_id=?",
                (normalized["receipt_id"],),
            ).fetchone()
            if existing is not None:
                if existing["receipt_sha256"] != digest:
                    raise ValueError("receipt_id was reused with different qualification content")
                return {
                    "receipt_id": normalized["receipt_id"],
                    "receipt_sha256": digest,
                    "status": "pending_independent_verification",
                    "qualified": False,
                    "idempotent_replay": True,
                }
            db.execute(
                "INSERT INTO capability_qualification_receipts"
                "(receipt_id,capability_id,artifact_digest,receipt_json,receipt_sha256,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (normalized["receipt_id"], normalized["capability_id"],
                 artifact_digest, encoded, digest, time.time()),
            )
        return {
            "receipt_id": normalized["receipt_id"],
            "receipt_sha256": digest,
            "status": "pending_independent_verification",
            "qualified": False,
            "idempotent_replay": False,
        }

    def capability_qualification_receipts(self, capability_id: str) -> list[dict[str, Any]]:
        if not isinstance(capability_id, str) or not capability_id.strip():
            raise ValueError("capability_id is required")
        with closing(self._connect()) as db, db:
            rows = db.execute(
                "SELECT receipt_id,receipt_json,receipt_sha256,created_at "
                "FROM capability_qualification_receipts WHERE capability_id=? "
                "ORDER BY created_at,receipt_id",
                (capability_id.strip(),),
            ).fetchall()
        return [{
            "receipt_id": row["receipt_id"],
            "receipt": json.loads(row["receipt_json"]),
            "receipt_sha256": row["receipt_sha256"],
            "created_at": row["created_at"],
            "status": "pending_independent_verification",
            "qualified": False,
        } for row in rows]

    def inventory(self, project_id: str) -> dict[str, Any]:
        with closing(self._connect()) as db, db:
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
