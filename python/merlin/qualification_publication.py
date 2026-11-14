"""Atomic publication of qualification snapshots and Hermes-facing outbox events.

The snapshot and its notification share MerlinRegistry's SQLite database and one
BEGIN IMMEDIATE transaction. The event is a pointer to immutable snapshot history;
it does not itself qualify the evidence or grant execution authority.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any, Mapping

from .event_outbox import MerlinEventOutbox
from .qualification_evidence_dag import SnapshotHistory, validate_snapshot


SNAPSHOT_EVENT_TOPIC = "merlin.qualification.snapshot"
SNAPSHOT_EVENT_SCHEMA = "merlin-qualification-snapshot-event/1"


class QualificationSnapshotPublisher:
    """Commit an immutable DAG snapshot and its notification atomically."""

    def __init__(self, registry_db_path: str | Path,
                 outbox: MerlinEventOutbox | None = None):
        self.db_path = Path(registry_db_path).resolve()
        self.history = SnapshotHistory(self.db_path)
        self.outbox = outbox or MerlinEventOutbox(self.db_path)
        if self.outbox.path.resolve() != self.db_path:
            raise ValueError("qualification snapshot and outbox must share the registry database")

    def publish(self, snapshot: Mapping[str, Any], *,
                now: float | None = None) -> dict[str, Any]:
        """Persist the snapshot and an idempotent event in one SQLite transaction."""
        validated = validate_snapshot(snapshot)
        digest = validated["snapshot_sha256"]
        idempotency_key = f"qualification-snapshot:{digest}"
        payload_base = {
            "schema": SNAPSHOT_EVENT_SCHEMA,
            "snapshot_sha256": digest,
            "node_count": len(validated["nodes"]),
            "edge_count": len(validated["edges"]),
        }

        db = sqlite3.connect(str(self.db_path), timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        try:
            db.execute("BEGIN IMMEDIATE")
            sequence = self.history.append_in_transaction(db, validated)
            payload = {**payload_base, "sequence": sequence}
            event = self.outbox.enqueue_in_transaction(
                db, idempotency_key, SNAPSHOT_EVENT_TOPIC, payload, now=now,
            )
            db.commit()
            return {
                "sequence": sequence,
                "snapshot_sha256": digest,
                "event_id": event["event_id"],
                "event_state": event["state"],
                "event_payload": event["payload"],
            }
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
