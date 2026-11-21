"""Durable, idempotent checkpoints for retryable Hermes stage handlers.

The journal checkpoints generated stage output before registry/graph projection.
It does not make external provider calls exactly-once; callers pass the stable
idempotency key through to adapters so providers can deduplicate when supported.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Mapping


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


class StageJournalConflict(ValueError):
    """A task idempotency key was reused for different immutable inputs."""


class HermesStageJournal:
    def __init__(self, database: str | Path):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""
                CREATE TABLE IF NOT EXISTS hermes_stage_runs (
                    idempotency_key TEXT PRIMARY KEY,
                    stage TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    hypothesis_id TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('started','generated','completed')),
                    candidate_set_json TEXT,
                    result_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def begin(self, *, idempotency_key: str, stage: str, task_id: str,
              hypothesis_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        for value, label, limit in (
            (idempotency_key, "idempotency_key", 256),
            (stage, "stage", 120),
            (task_id, "task_id", 200),
            (hypothesis_id, "hypothesis_id", 200),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(label + " is invalid")
        if not isinstance(request, Mapping):
            raise ValueError("journal request must be an object")
        request_digest = hashlib.sha256(_canonical(dict(request)).encode("utf-8")).hexdigest()
        now = time.time()
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM hermes_stage_runs WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                db.execute("""
                    INSERT INTO hermes_stage_runs(
                        idempotency_key,stage,task_id,hypothesis_id,request_sha256,
                        state,created_at,updated_at
                    ) VALUES(?,?,?,?,?,'started',?,?)
                """, (idempotency_key, stage, task_id, hypothesis_id,
                      request_digest, now, now))
                row = db.execute(
                    "SELECT * FROM hermes_stage_runs WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
            elif (
                row["stage"] != stage or row["task_id"] != task_id
                or row["hypothesis_id"] != hypothesis_id
                or row["request_sha256"] != request_digest
            ):
                raise StageJournalConflict(
                    "task idempotency key is already bound to different stage inputs"
                )
            result = dict(row)
            db.commit()
        if result["candidate_set_json"]:
            result["candidate_set"] = json.loads(result.pop("candidate_set_json"))
        else:
            result.pop("candidate_set_json", None)
            result["candidate_set"] = None
        if result["result_json"]:
            result["result"] = json.loads(result.pop("result_json"))
        else:
            result.pop("result_json", None)
            result["result"] = None
        return result

    def save_generated(self, idempotency_key: str,
                       candidate_set: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(candidate_set, Mapping):
            raise ValueError("candidate_set must be an object")
        encoded = _canonical(dict(candidate_set))
        now = time.time()
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state,candidate_set_json FROM hermes_stage_runs WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                raise KeyError(idempotency_key)
            if row["candidate_set_json"] is not None and row["candidate_set_json"] != encoded:
                raise StageJournalConflict("replayed generator output differs from the durable checkpoint")
            if row["state"] == "completed":
                db.rollback()
                raise StageJournalConflict("completed stage cannot replace its generated checkpoint")
            db.execute("""
                UPDATE hermes_stage_runs
                SET state='generated',candidate_set_json=?,updated_at=?
                WHERE idempotency_key=?
            """, (encoded, now, idempotency_key))
            db.commit()
        return dict(candidate_set)

    def complete(self, idempotency_key: str, result: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(result, Mapping):
            raise ValueError("stage result must be an object")
        encoded = _canonical(dict(result))
        now = time.time()
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state,result_json FROM hermes_stage_runs WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row is None or row["state"] not in {"generated", "completed"}:
                raise RuntimeError("stage result cannot complete before its generated checkpoint")
            if row["result_json"] is not None and row["result_json"] != encoded:
                raise StageJournalConflict("completed stage result changed on replay")
            db.execute("""
                UPDATE hermes_stage_runs
                SET state='completed',result_json=?,updated_at=?
                WHERE idempotency_key=?
            """, (encoded, now, idempotency_key))
            db.commit()
        return dict(result)


__all__ = ["HermesStageJournal", "StageJournalConflict"]
