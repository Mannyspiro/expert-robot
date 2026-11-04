"""Proof Strategy Observatory: immutable Lean attempt telemetry and cross-domain links.

This module records observations; it does not run Lean, authenticate CI, or
promote theorem status. A receipt is qualified only when its provenance and
kernel/audit fields are supplied by a trusted external qualification workflow.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import sqlite3
import statistics
import time
from pathlib import Path
from typing import Iterable


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GoalKey:
    theorem_id: str
    statement_sha256: str
    assumptions_sha256: str
    domain: str
    representation_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.theorem_id.strip() or not self.domain.strip():
            raise ValueError("theorem_id and domain are required")
        for label, digest in (("statement", self.statement_sha256),
                              ("assumptions", self.assumptions_sha256)):
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError(f"{label}_sha256 must be lowercase SHA-256")


@dataclass(frozen=True)
class ProofAttempt:
    attempt_id: str
    goal: GoalKey
    tactic_sequence: tuple[str, ...]
    outcome: str
    failure_stage: str | None
    elapsed_ms: float
    heartbeats: int
    peak_memory_bytes: int | None
    source_commit: str
    source_sha256: str
    lean_version: str
    mathlib_revision: str
    import_closure_sha256: str
    kernel_checked: bool = False
    contains_sorry: bool = False
    axiom_dependencies: tuple[str, ...] = ()
    exact_target_declaration: bool = False
    workflow_run_url: str | None = None

    def validate(self) -> None:
        self.goal.validate()
        if not self.attempt_id.strip() or not self.tactic_sequence:
            raise ValueError("attempt_id and tactic_sequence are required")
        if self.outcome not in {"success", "failure", "timeout", "cancelled"}:
            raise ValueError("unsupported attempt outcome")
        if self.elapsed_ms < 0 or self.heartbeats < 0:
            raise ValueError("elapsed_ms and heartbeats must be non-negative")
        if len(self.source_commit) != 40 or any(c not in "0123456789abcdef" for c in self.source_commit):
            raise ValueError("source_commit must be a lowercase Git SHA")
        for label, digest in (("source_sha256", self.source_sha256),
                              ("import_closure_sha256", self.import_closure_sha256)):
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError(f"{label} must be lowercase SHA-256")
        if not self.lean_version.strip() or not self.mathlib_revision.strip():
            raise ValueError("Lean version and Mathlib revision are required")
        if self.outcome == "success" and self.failure_stage is not None:
            raise ValueError("successful attempts cannot have a failure_stage")

    @property
    def qualified(self) -> bool:
        return (self.outcome == "success" and self.kernel_checked and
                not self.contains_sorry and self.exact_target_declaration and
                bool(self.workflow_run_url))


@dataclass(frozen=True)
class CrossDomainLink:
    theorem_id: str
    object_view_id: str
    engineering_project_id: str
    engineering_revision_sha256: str
    relation: str
    evidence_receipt_sha256: str

    def validate(self) -> None:
        required = (self.theorem_id, self.object_view_id, self.engineering_project_id, self.relation)
        if any(not value.strip() for value in required):
            raise ValueError("cross-domain link identifiers and relation are required")
        for label, digest in (("engineering_revision_sha256", self.engineering_revision_sha256),
                              ("evidence_receipt_sha256", self.evidence_receipt_sha256)):
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError(f"{label} must be lowercase SHA-256")


class ProofObservatory:
    """Append-only SQLite store with a tamper-evident receipt hash chain."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS observations (
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              attempt_id TEXT NOT NULL UNIQUE,
              payload TEXT NOT NULL,
              payload_sha256 TEXT NOT NULL,
              previous_sha256 TEXT NOT NULL,
              chain_sha256 TEXT NOT NULL,
              created_ns INTEGER NOT NULL
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS cross_domain_links (
              link_id TEXT PRIMARY KEY,
              payload TEXT NOT NULL,
              payload_sha256 TEXT NOT NULL,
              created_ns INTEGER NOT NULL
            )
        """)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def record_attempt(self, attempt: ProofAttempt) -> str:
        attempt.validate()
        payload = canonical_json(asdict(attempt))
        payload_hash = sha256_text(payload)
        previous = self.db.execute(
            "SELECT chain_sha256 FROM observations ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous[0] if previous else "0" * 64
        chain_hash = sha256_text(previous_hash + payload_hash)
        self.db.execute(
            "INSERT INTO observations(attempt_id,payload,payload_sha256,previous_sha256,chain_sha256,created_ns) VALUES(?,?,?,?,?,?)",
            (attempt.attempt_id, payload, payload_hash, previous_hash, chain_hash, time.time_ns()),
        )
        self.db.commit()
        return chain_hash

    def verify_chain(self) -> bool:
        previous = "0" * 64
        rows = self.db.execute(
            "SELECT payload,payload_sha256,previous_sha256,chain_sha256 FROM observations ORDER BY seq"
        ).fetchall()
        for payload, payload_hash, stored_previous, stored_chain in rows:
            actual_payload = sha256_text(payload)
            actual_chain = sha256_text(previous + actual_payload)
            if actual_payload != payload_hash or stored_previous != previous or actual_chain != stored_chain:
                return False
            previous = stored_chain
        return True

    def attempts(self, theorem_id: str | None = None) -> list[dict]:
        rows = self.db.execute("SELECT payload FROM observations ORDER BY seq").fetchall()
        values = [json.loads(row[0]) for row in rows]
        return [item for item in values
                if theorem_id is None or item["goal"]["theorem_id"] == theorem_id]

    def record_link(self, link: CrossDomainLink) -> str:
        link.validate()
        payload = canonical_json(asdict(link))
        digest = sha256_text(payload)
        self.db.execute(
            "INSERT INTO cross_domain_links(link_id,payload,payload_sha256,created_ns) VALUES(?,?,?,?)",
            (digest, payload, digest, time.time_ns()),
        )
        self.db.commit()
        return digest

    def links_for_theorem(self, theorem_id: str) -> list[dict]:
        rows = self.db.execute("SELECT payload FROM cross_domain_links ORDER BY created_ns").fetchall()
        return [value for (payload,) in rows
                if (value := json.loads(payload))["theorem_id"] == theorem_id]


def rank_strategies(attempts: Iterable[ProofAttempt], minimum_qualified: int = 3) -> list[dict]:
    """Rank tactic sequences only after repeated exact-target kernel-checked observations."""
    groups: dict[tuple[tuple[str, ...], str, str, str, str, str], list[ProofAttempt]] = {}
    for attempt in attempts:
        attempt.validate()
        if attempt.qualified:
            group_key = (
                attempt.tactic_sequence,
                attempt.goal.domain,
                attempt.goal.statement_sha256,
                attempt.goal.assumptions_sha256,
                attempt.lean_version,
                attempt.mathlib_revision,
            )
            groups.setdefault(group_key, []).append(attempt)
    ranked = []
    for group_key, rows in groups.items():
        tactics = group_key[0]
        if len(rows) < minimum_qualified:
            continue
        ranked.append({
            "tactics": list(tactics),
            "qualified_observations": len(rows),
            "success_rate": 1.0,
            "median_heartbeats": statistics.median(row.heartbeats for row in rows),
            "median_elapsed_ms": statistics.median(row.elapsed_ms for row in rows),
            "domain": group_key[1],
            "statement_sha256": group_key[2],
            "assumptions_sha256": group_key[3],
            "lean_version": group_key[4],
            "mathlib_revision": group_key[5],
        })
    return sorted(ranked, key=lambda row: (
        -row["success_rate"], row["median_heartbeats"], row["median_elapsed_ms"]
    ))
def object_view_engineering_links(
    theorem_id: str,
    object_view_ids: Iterable[str],
    engineering_project_id: str,
    engineering_revision_sha256: str,
    relation: str,
    evidence_receipt_sha256: str,
) -> tuple[CrossDomainLink, ...]:
    """Create explicit links; callers must supply real IDs and revision/evidence hashes."""
    links = tuple(CrossDomainLink(
        theorem_id=theorem_id,
        object_view_id=object_id,
        engineering_project_id=engineering_project_id,
        engineering_revision_sha256=engineering_revision_sha256,
        relation=relation,
        evidence_receipt_sha256=evidence_receipt_sha256,
    ) for object_id in object_view_ids)
    for link in links:
        link.validate()
    return links
