"""Explicit, user-approved long-term memory for Merlin.

Only preferences and project summaries deliberately saved by the local user are
stored here. Raw conversations, credentials and model-generated guesses are not
automatically retained or promoted into memory.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Any

_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_. -]{0,79}$")
_FORBIDDEN_KEY_PARTS = ("password", "passwd", "secret", "token", "credential",
                        "api_key", "private_key", "recovery_code")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MerlinMemoryVault:
    """Small transactional SQLite vault; independent from telemetry and artifacts."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS memory_preferences(
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              value_sha256 TEXT NOT NULL,
              version INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memory_projects(
              name TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              status_sha256 TEXT NOT NULL,
              version INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def _transaction(self):
        db = self._connect()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _preference(key: Any, value: Any) -> tuple[str, str, str]:
        if not isinstance(key, str) or not _KEY.fullmatch(key.strip()):
            raise ValueError("preference key must be 1–80 safe characters")
        normalized = key.strip()
        lowered = normalized.lower().replace("-", "_").replace(" ", "_")
        if any(part in lowered for part in _FORBIDDEN_KEY_PARTS):
            raise ValueError("credentials and secrets must never be saved in memory")
        if not isinstance(value, str) or not value.strip() or len(value) > 2000:
            raise ValueError("preference value must be nonblank and at most 2000 characters")
        value = value.strip()
        return normalized, value, hashlib.sha256(value.encode("utf-8")).hexdigest()

    def set_preference(self, key: str, value: str) -> dict[str, Any]:
        key, value, digest = self._preference(key, value)
        now = _now()
        with self._transaction() as db:
            db.execute("""
              INSERT INTO memory_preferences(key,value,value_sha256,version,created_at,updated_at)
              VALUES(?,?,?,1,?,?)
              ON CONFLICT(key) DO UPDATE SET
                value=excluded.value, value_sha256=excluded.value_sha256,
                version=memory_preferences.version+1, updated_at=excluded.updated_at
            """, (key, value, digest, now, now))
            row = db.execute(
                "SELECT key,value_sha256,version,created_at,updated_at "
                "FROM memory_preferences WHERE key=?", (key,)
            ).fetchone()
        return dict(row)

    def set_project(self, name: Any, status: Any) -> dict[str, Any]:
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
            raise ValueError("project name must be nonblank and at most 200 characters")
        if not isinstance(status, str) or not status.strip() or len(status) > 1000:
            raise ValueError("project status must be nonblank and at most 1000 characters")
        name, status = name.strip(), status.strip()
        digest = hashlib.sha256(status.encode("utf-8")).hexdigest()
        now = _now()
        with self._transaction() as db:
            db.execute("""
              INSERT INTO memory_projects(name,status,status_sha256,version,created_at,updated_at)
              VALUES(?,?,?,1,?,?)
              ON CONFLICT(name) DO UPDATE SET
                status=excluded.status, status_sha256=excluded.status_sha256,
                version=memory_projects.version+1, updated_at=excluded.updated_at
            """, (name, status, digest, now, now))
            row = db.execute(
                "SELECT name,status_sha256,version,created_at,updated_at "
                "FROM memory_projects WHERE name=?", (name,)
            ).fetchone()
        return dict(row)

    def snapshot(self) -> dict[str, Any]:
        with self._transaction() as db:
            preferences = db.execute(
                "SELECT key,value,value_sha256,version,created_at,updated_at "
                "FROM memory_preferences ORDER BY key"
            ).fetchall()
            projects = db.execute(
                "SELECT name,status,status_sha256,version,created_at,updated_at "
                "FROM memory_projects ORDER BY updated_at DESC,name"
            ).fetchall()
        return {
            "schema": "merlin-memory-vault/1",
            "policy": {
                "user_approved_only": True,
                "raw_conversation_retention": False,
                "credentials_allowed": False,
                "memory_context_opt_in_required": True,
            },
            "preferences": [dict(row) for row in preferences],
            "projects": [dict(row) for row in projects],
        }

    def delete_preference(self, key: str) -> bool:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("preference key is required")
        with self._transaction() as db:
            cursor = db.execute("DELETE FROM memory_preferences WHERE key=?", (key.strip(),))
        return cursor.rowcount > 0

    def delete_project(self, name: str) -> bool:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("project name is required")
        with self._transaction() as db:
            cursor = db.execute("DELETE FROM memory_projects WHERE name=?", (name.strip(),))
        return cursor.rowcount > 0
