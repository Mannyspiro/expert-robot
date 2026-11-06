"""Privacy-bounded interaction learning and improvement proposals for Merlin.

This module learns from operational measurements and explicit outcome signals.
It deliberately stores no prompt, response, attachment, credential, or raw
conversation text. Aggregates are recommendations; this module cannot change
code, policies, permissions, or execution authority.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import math
import re
import sqlite3
import statistics
import time
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

DOMAINS = frozenset({
    "general", "software", "research", "mathematics", "engineering", "cad",
    "video", "image", "audio", "education", "business", "finance", "data",
    "agent_orchestration",
})
OUTCOMES = frozenset({"success", "partial", "failure", "abandoned"})
FRICTION_CODES = frozenset({
    "incorrect_answer", "incomplete_answer", "repeated_clarification",
    "tool_failure", "slow_response", "confusing_ui", "missing_capability",
    "poor_recommendation", "continuity_loss", "other",
})
CORRECTION_TYPES = frozenset({
    "factual", "reasoning", "format", "scope", "preference", "safety",
    "tool_selection", "other",
})
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class InteractionLearningStore:
    """Append-only, metadata-only feedback store sharing Merlin's SQLite DB."""

    def __init__(self, database: str | Path):
        self.path = str(database)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS interaction_feedback(
              event_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
              domain TEXT NOT NULL, task_type TEXT NOT NULL,
              outcome TEXT NOT NULL, friction_code TEXT,
              correction_type TEXT, satisfaction INTEGER,
              created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS interaction_feedback_time
              ON interaction_feedback(created_at);
            CREATE TABLE IF NOT EXISTS interaction_preferences(
              preference_key TEXT PRIMARY KEY, preference_value TEXT NOT NULL,
              updated_at REAL NOT NULL
            );
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def preferences(self) -> dict[str, Any]:
        defaults = {
            "aggregate_telemetry": True,
            "explicit_feedback_learning": True,
            "personalization": False,
            "raw_conversation_retention": False,
            "automatic_self_modification": False,
        }
        with self._connect() as db:
            rows = db.execute("SELECT preference_key,preference_value FROM interaction_preferences").fetchall()
        for row in rows:
            defaults[row["preference_key"]] = json.loads(row["preference_value"])
        return defaults

    def set_preferences(self, changes: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"aggregate_telemetry", "explicit_feedback_learning", "personalization"}
        if not isinstance(changes, Mapping) or not changes or set(changes) - allowed:
            raise ValueError("only telemetry, explicit feedback and personalization preferences can be changed")
        if any(not isinstance(v, bool) for v in changes.values()):
            raise ValueError("interaction preferences must be booleans")
        if changes.get("personalization") is True:
            raise ValueError("cross-session personalization is not implemented or qualified yet")
        with self._connect() as db:
            for key, value in changes.items():
                db.execute(
                    "INSERT INTO interaction_preferences VALUES(?,?,?) "
                    "ON CONFLICT(preference_key) DO UPDATE SET preference_value=excluded.preference_value, updated_at=excluded.updated_at",
                    (key, json.dumps(value), time.time()),
                )
        return self.preferences()

    def record_feedback(self, event: Mapping[str, Any]) -> dict[str, Any]:
        if not self.preferences()["explicit_feedback_learning"]:
            raise PermissionError("explicit feedback learning is disabled")
        if not isinstance(event, Mapping):
            raise ValueError("feedback must be an object")
        session_id = event.get("session_id")
        task_type = event.get("task_type")
        domain = event.get("domain", "general")
        outcome = event.get("outcome")
        if not isinstance(session_id, str) or not _ID.fullmatch(session_id):
            raise ValueError("session_id must be an opaque identifier")
        if not isinstance(task_type, str) or not _ID.fullmatch(task_type):
            raise ValueError("task_type must be a short category identifier")
        if domain not in DOMAINS or outcome not in OUTCOMES:
            raise ValueError("unsupported domain or outcome")
        friction = event.get("friction_code")
        correction = event.get("correction_type")
        satisfaction = event.get("satisfaction")
        if friction is not None and friction not in FRICTION_CODES:
            raise ValueError("unsupported friction_code")
        if correction is not None and correction not in CORRECTION_TYPES:
            raise ValueError("unsupported correction_type")
        if satisfaction is not None and (
            isinstance(satisfaction, bool) or not isinstance(satisfaction, int)
            or not 1 <= satisfaction <= 5
        ):
            raise ValueError("satisfaction must be an integer from 1 to 5")
        event_id = event.get("event_id") or str(uuid4())
        if not isinstance(event_id, str) or not _ID.fullmatch(event_id):
            raise ValueError("event_id must be an opaque identifier")
        created_at = event.get("created_at", time.time())
        if isinstance(created_at, bool) or not isinstance(created_at, (int, float)) or not math.isfinite(created_at):
            raise ValueError("created_at must be a finite timestamp")
        row = (event_id, session_id, domain, task_type, outcome, friction,
               correction, satisfaction, float(created_at))
        with self._connect() as db:
            old = db.execute("SELECT * FROM interaction_feedback WHERE event_id=?", (event_id,)).fetchone()
            if old is not None:
                previous = tuple(old[k] for k in (
                    "event_id", "session_id", "domain", "task_type", "outcome",
                    "friction_code", "correction_type", "satisfaction", "created_at"))
                same = previous == row
                # Server-generated receipt time must not make a network retry conflict.
                if "created_at" not in event:
                    same = previous[:-1] == row[:-1]
                if not same:
                    raise ValueError("event_id reused with different feedback")
                return {"accepted": True, "duplicate": True, "event_id": event_id}
            db.execute("INSERT INTO interaction_feedback VALUES(?,?,?,?,?,?,?,?,?)", row)
        return {"accepted": True, "duplicate": False, "event_id": event_id}

    def feedback_summary(self, limit: int = 10000) -> dict[str, Any]:
        if not 1 <= limit <= 100000:
            raise ValueError("limit out of range")
        with self._connect() as db:
            rows = db.execute(
                "SELECT domain,task_type,outcome,friction_code,correction_type,satisfaction,created_at "
                "FROM interaction_feedback ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return {"count": len(rows), "events": [dict(row) for row in rows]}

    def delete_session_feedback(self, session_id: str) -> int:
        if not isinstance(session_id, str) or not _ID.fullmatch(session_id):
            raise ValueError("session_id must be an opaque identifier")
        with self._connect() as db:
            cursor = db.execute("DELETE FROM interaction_feedback WHERE session_id=?", (session_id,))
            return cursor.rowcount

    def purge_feedback_before(self, timestamp: float) -> int:
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
            raise ValueError("timestamp must be finite")
        with self._connect() as db:
            cursor = db.execute("DELETE FROM interaction_feedback WHERE created_at < ?", (timestamp,))
            return cursor.rowcount


def analyze_interactions(
    telemetry_events: list[dict[str, Any]],
    feedback_events: list[dict[str, Any]],
    *,
    min_samples: int = 5,
) -> dict[str, Any]:
    """Build transparent, aggregate-only improvement proposals."""
    if not 2 <= min_samples <= 1000:
        raise ValueError("min_samples must be between 2 and 1000")
    routes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in telemetry_events:
        payload = event.get("payload", {})
        if event.get("source") != "runtime" or payload.get("component") != "http_api":
            continue
        route = event.get("task_id")
        if isinstance(route, str) and route.startswith("/"):
            routes[route].append(event)

    route_metrics = []
    proposals = []
    for route, rows in sorted(routes.items()):
        durations = sorted(float(e.get("duration_ms") or 0) for e in rows)
        errors = sum(int(e.get("payload", {}).get("status_code", 0)) >= 500 for e in rows)
        count = len(rows)
        p95 = durations[min(len(durations) - 1, math.ceil(0.95 * len(durations)) - 1)]
        metric = {"route": route, "samples": count, "server_error_rate": round(errors / count, 4),
                  "p95_duration_ms": round(p95, 2)}
        route_metrics.append(metric)
        if count >= min_samples and errors / count >= 0.10:
            proposals.append({
                "id": "improve-api-reliability:" + route,
                "type": "reliability", "target": route, "priority": "high",
                "reason": f"{errors}/{count} observed requests returned server errors",
                "sample_count": count, "recommended_measurement": "re-run route contract and fault-injection tests",
            })
        if count >= min_samples and p95 >= 1500:
            proposals.append({
                "id": "improve-api-latency:" + route,
                "type": "performance", "target": route, "priority": "medium",
                "reason": f"observed p95 latency is {round(p95, 2)} ms",
                "sample_count": count, "recommended_measurement": "profile route and compare p95 before/after",
            })

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in feedback_events:
        grouped[(event["domain"], event["task_type"])].append(event)
    feedback_metrics = []
    for (domain, task_type), rows in sorted(grouped.items()):
        count = len(rows)
        failures = sum(r["outcome"] in {"failure", "abandoned"} for r in rows)
        ratings = [r["satisfaction"] for r in rows if r.get("satisfaction") is not None]
        frictions: dict[str, int] = defaultdict(int)
        corrections: dict[str, int] = defaultdict(int)
        for row in rows:
            if row.get("friction_code"):
                frictions[row["friction_code"]] += 1
            if row.get("correction_type"):
                corrections[row["correction_type"]] += 1
        metric = {
            "domain": domain, "task_type": task_type, "samples": count,
            "failure_or_abandon_rate": round(failures / count, 4),
            "mean_satisfaction": round(statistics.mean(ratings), 2) if ratings else None,
            "friction_counts": dict(sorted(frictions.items())),
            "correction_counts": dict(sorted(corrections.items())),
        }
        feedback_metrics.append(metric)
        if count >= min_samples and (failures / count >= 0.25 or (ratings and statistics.mean(ratings) < 3.0)):
            proposals.append({
                "id": f"improve-task:{domain}:{task_type}",
                "type": "task_quality", "target": f"{domain}/{task_type}",
                "priority": "high" if failures / count >= 0.4 else "medium",
                "reason": "observed task outcomes or satisfaction fall below the configured threshold",
                "sample_count": count,
                "friction_counts": metric["friction_counts"],
                "correction_counts": metric["correction_counts"],
                "recommended_measurement": "create a held-out task set and compare success, correction and satisfaction rates",
            })
    return {
        "schema": "merlin-interaction-improvement/1",
        "telemetry": {"route_metrics": route_metrics, "sample_count": sum(len(x) for x in routes.values())},
        "feedback": {"task_metrics": feedback_metrics, "sample_count": len(feedback_events)},
        "proposals": proposals,
        "minimum_samples": min_samples,
        "raw_conversation_content_stored": False,
        "automatic_code_or_policy_changes": False,
        "promotion_authorized": False,
        "notice": "Aggregate observations identify candidates; human review and held-out evaluation are required before any change.",
    }
