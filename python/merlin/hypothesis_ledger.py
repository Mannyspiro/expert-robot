"""Evidence-gated hypothesis ledger for Merlin.

Hypotheses are stored separately from scholarly facts. Status transitions require
appropriate evidence records; no automatic promotion occurs from topic similarity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

STATUSES = {
    "proposed", "literature_checked", "computationally_tested",
    "refuted", "conditional", "formally_verified",
}
EVIDENCE_KINDS = {"source", "counterexample", "experiment", "proof", "assumption"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(value: str, label: str, limit: int = 4000) -> str:
    result = " ".join((value or "").split()).strip()
    if not result or len(result) > limit:
        raise ValueError(f"{label} must be non-empty and at most {limit} characters")
    return result


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    claim: str
    mathematical_objects: tuple[str, ...]
    relation: str
    assumptions: tuple[str, ...]
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Evidence:
    evidence_id: int
    hypothesis_id: str
    kind: str
    description: str
    source_url: str
    artifact_hash: str
    created_at: str


class HypothesisLedger:
    """Local SQLite hypothesis registry with evidence-gated status transitions."""

    def __init__(self, database: str | Path):
        self.database = str(database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS hypotheses (
                    hypothesis_id TEXT PRIMARY KEY,
                    claim TEXT NOT NULL,
                    mathematical_objects_json TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    assumptions_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hypothesis_evidence (
                    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hypothesis_id TEXT NOT NULL REFERENCES hypotheses(hypothesis_id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    description TEXT NOT NULL,
                    source_url TEXT NOT NULL DEFAULT '',
                    artifact_hash TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_hypothesis_evidence
                    ON hypothesis_evidence(hypothesis_id, kind);
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def create(self, hypothesis_id: str, claim: str, *,
               mathematical_objects: tuple[str, ...] = (),
               relation: str = "unspecified",
               assumptions: tuple[str, ...] = ()) -> Hypothesis:
        hid = _clean(hypothesis_id, "hypothesis ID", 120)
        statement = _clean(claim, "claim")
        rel = _clean(relation, "relation", 300)
        objects = tuple(_clean(x, "mathematical object", 300) for x in mathematical_objects)
        assumptions_clean = tuple(_clean(x, "assumption", 1000) for x in assumptions)
        now = _now()
        with self._connect() as db:
            db.execute("""
                INSERT INTO hypotheses VALUES (?, ?, ?, ?, ?, 'proposed', ?, ?)
            """, (hid, statement, json.dumps(objects), rel,
                  json.dumps(assumptions_clean), now, now))
        return self.get(hid)

    def get(self, hypothesis_id: str) -> Hypothesis:
        with self._connect() as db:
            row = db.execute("SELECT * FROM hypotheses WHERE hypothesis_id=?",
                             (hypothesis_id,)).fetchone()
        if row is None:
            raise KeyError(hypothesis_id)
        return Hypothesis(
            row["hypothesis_id"], row["claim"],
            tuple(json.loads(row["mathematical_objects_json"])),
            row["relation"], tuple(json.loads(row["assumptions_json"])),
            row["status"], row["created_at"], row["updated_at"],
        )

    def add_evidence(self, hypothesis_id: str, kind: str, description: str, *,
                     source_url: str = "", artifact_hash: str = "") -> Evidence:
        if kind not in EVIDENCE_KINDS:
            raise ValueError(f"kind must be one of {sorted(EVIDENCE_KINDS)}")
        desc = _clean(description, "evidence description")
        url = (source_url or "").strip()
        if url and not url.startswith("https://"):
            raise ValueError("source_url must use HTTPS")
        digest = (artifact_hash or "").strip()
        if digest and (len(digest) < 16 or len(digest) > 128):
            raise ValueError("artifact_hash must be 16 to 128 characters")
        with self._connect() as db:
            if db.execute("SELECT 1 FROM hypotheses WHERE hypothesis_id=?",
                          (hypothesis_id,)).fetchone() is None:
                raise KeyError(hypothesis_id)
            cursor = db.execute("""
                INSERT INTO hypothesis_evidence
                    (hypothesis_id, kind, description, source_url, artifact_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (hypothesis_id, kind, desc, url, digest, _now()))
            row = db.execute("SELECT * FROM hypothesis_evidence WHERE evidence_id=?",
                             (cursor.lastrowid,)).fetchone()
        return Evidence(row["evidence_id"], row["hypothesis_id"], row["kind"],
                        row["description"], row["source_url"], row["artifact_hash"],
                        row["created_at"])

    def evidence(self, hypothesis_id: str) -> list[Evidence]:
        with self._connect() as db:
            rows = db.execute("""
                SELECT * FROM hypothesis_evidence WHERE hypothesis_id=?
                ORDER BY evidence_id
            """, (hypothesis_id,)).fetchall()
        return [Evidence(row["evidence_id"], row["hypothesis_id"], row["kind"],
                         row["description"], row["source_url"], row["artifact_hash"],
                         row["created_at"]) for row in rows]

    def set_status(self, hypothesis_id: str, status: str) -> Hypothesis:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}")
        current = self.get(hypothesis_id)
        kinds = {item.kind for item in self.evidence(hypothesis_id)}
        requirements = {
            "literature_checked": {"source"},
            "computationally_tested": {"experiment"},
            "refuted": {"counterexample"},
            "conditional": {"assumption"},
            "formally_verified": {"proof"},
        }
        missing = requirements.get(status, set()) - kinds
        if missing:
            raise ValueError(f"status {status} requires evidence kinds: {sorted(missing)}")
        if status == "formally_verified":
            proofs = [e for e in self.evidence(hypothesis_id)
                      if e.kind == "proof" and e.artifact_hash]
            if not proofs:
                raise ValueError("formal verification requires a proof record with an artifact hash")
        if status == "conditional" and not current.assumptions:
            assumptions = [e for e in self.evidence(hypothesis_id) if e.kind == "assumption"]
            if not assumptions:
                raise ValueError("conditional status requires explicit assumptions")
        with self._connect() as db:
            db.execute("UPDATE hypotheses SET status=?, updated_at=? WHERE hypothesis_id=?",
                       (status, _now(), hypothesis_id))
        return self.get(hypothesis_id)

    def list_hypotheses(self, status: str | None = None) -> list[Hypothesis]:
        if status is not None and status not in STATUSES:
            raise ValueError("unknown hypothesis status")
        with self._connect() as db:
            if status:
                rows = db.execute("SELECT hypothesis_id FROM hypotheses WHERE status=? ORDER BY created_at",
                                  (status,)).fetchall()
            else:
                rows = db.execute("SELECT hypothesis_id FROM hypotheses ORDER BY created_at").fetchall()
        return [self.get(row["hypothesis_id"]) for row in rows]
