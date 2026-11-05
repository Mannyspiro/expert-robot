"""Event-derived HUD state for Merlin.

The HUD visualizes observable system activity, not private model reasoning.
Animations are presentation; event records and evidence references are the source.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Iterable, Mapping

from merlin.telemetry import normalize_event

PHASES = (
    "intake", "hypothesis", "representation", "experiment",
    "counterexample", "formalization", "verification", "artifact",
)
PHASE_BY_KIND = {
    "task.started": "intake",
    "hypothesis.updated": "hypothesis",
    "research.stage": None,
    "experiment.completed": "experiment",
    "proof.checked": "formalization",
    "verification.completed": "verification",
    "artifact.registered": "artifact",
    "task.completed": "artifact",
}
EVENT_LABELS = {
    "task.started": "Task accepted",
    "task.progress": "Progress update",
    "task.completed": "Task completed",
    "agent.status": "Agent status",
    "model.inference": "Model inference",
    "verification.completed": "Verification result",
    "resource.sample": "Resource measurement",
    "decision.trace": "Plan decision",
    "operator.action": "Operator action",
    "system.error": "System error",
    "research.stage": "Research stage",
    "agent.tool.started": "Tool started",
    "agent.tool.completed": "Tool completed",
    "artifact.registered": "Artifact registered",
    "experiment.completed": "Experiment completed",
    "proof.checked": "Proof check",
    "hypothesis.updated": "Hypothesis updated",
    "outbox.acknowledged": "Event acknowledged",
}


class HudActivityProjector:
    """Build a bounded, read-only HUD projection from normalized event records."""

    def __init__(self, max_events: int = 250):
        if isinstance(max_events, bool) or not isinstance(max_events, int) or not 1 <= max_events <= 5000:
            raise ValueError("max_events must be between 1 and 5000")
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._seen: set[str] = set()
        self.max_events = max_events

    def ingest(self, event: Mapping[str, Any]) -> bool:
        normalized = normalize_event(event)
        if normalized["event_id"] in self._seen:
            return False
        if len(self._events) == self.max_events:
            evicted = self._events.popleft()
            self._seen.discard(evicted["event_id"])
        self._events.append(normalized)
        self._seen.add(normalized["event_id"])
        return True

    def ingest_many(self, events: Iterable[Mapping[str, Any]]) -> int:
        return sum(1 for event in events if self.ingest(event))

    def snapshot(self, *, run_id: str | None = None) -> dict[str, Any]:
        events = [event for event in self._events
                  if run_id is None or event["run_id"] == run_id]
        latest = events[-1] if events else None
        active_run = run_id or (latest["run_id"] if latest else None)
        current_phase = "intake"
        agents: dict[str, dict[str, Any]] = {}
        resources: dict[str, Any] = {}
        timeline = []
        evidence_refs: list[str] = []
        for event in events:
            kind, payload = event["kind"], event["payload"]
            stage = payload.get("stage") if kind == "research.stage" else None
            if stage in PHASES:
                current_phase = stage
            elif kind in PHASE_BY_KIND and PHASE_BY_KIND[kind]:
                current_phase = PHASE_BY_KIND[kind]
            agent_id = payload.get("agent_id") or payload.get("worker_id")
            if kind == "agent.status" and isinstance(agent_id, str):
                agents[agent_id] = {
                    "agent_id": agent_id,
                    "status": str(payload.get("status", "unknown")),
                    "role": str(payload.get("role", "agent")),
                    "activity": str(payload.get("activity", "working")),
                    "event_id": event["event_id"],
                }
            if kind == "resource.sample":
                resources = {
                    key: payload[key] for key in (
                        "cpu_percent", "memory_bytes", "gpu_percent",
                        "cpu_cores_reserved", "memory_bytes_reserved",
                        "gpu_count_reserved", "compute_budget_units_reserved",
                    ) if key in payload
                }
            evidence_refs.extend(event["evidence_refs"])
            timeline.append({
                "event_id": event["event_id"],
                "kind": kind,
                "label": EVENT_LABELS[kind],
                "timestamp": event["timestamp"],
                "source": event["source"],
                "task_id": event["task_id"],
                "duration_ms": event["duration_ms"],
                "evidence_refs": list(event["evidence_refs"]),
                "summary": str(payload.get("summary") or payload.get("activity") or
                               payload.get("stage") or EVENT_LABELS[kind])[:180],
                "status": payload.get("status"),
            })
        return {
            "schema": "merlin-hud-activity/1",
            "active_run_id": active_run,
            "phase": current_phase,
            "phase_index": PHASES.index(current_phase),
            "phases": list(PHASES),
            "agents": list(agents.values()),
            "resources": resources,
            "timeline": timeline[-60:],
            "evidence_refs": list(dict.fromkeys(evidence_refs))[-100:],
            "event_count": len(events),
            "latest_event_id": latest["event_id"] if latest else None,
            "visualization_policy": {
                "activity_is_event_derived": True,
                "animation_is_presentation_only": True,
                "private_reasoning_is_not_exposed": True,
                "simulation_is_not_runtime": True,
            },
        }


class HudOutboxConsumer:
    """Project telemetry events from the durable outbox into a read-only HUD view."""

    def __init__(self, outbox: Any, projector: HudActivityProjector):
        self.outbox = outbox
        self.projector = projector
        from merlin.telemetry import KINDS
        self.topics = tuple("merlin.telemetry." + kind for kind in sorted(KINDS))

    def drain_one(self, worker_id: str = "merlin-hud", *, now: float | None = None) -> dict[str, Any] | None:
        lease = self.outbox.claim_next(worker_id, topics=self.topics, now=now)
        if lease is None:
            return None
        try:
            accepted = self.projector.ingest(lease["payload"])
            result = {"projected": accepted, "event_id": lease["payload"]["event_id"]}
            self.outbox.acknowledge(lease["event_id"], worker_id, lease["lease_token"],
                                    result=result, now=now)
            return result
        except Exception as exc:
            self.outbox.retry(lease["event_id"], worker_id, lease["lease_token"],
                              type(exc).__name__ + ": " + str(exc),
                              delay_seconds=1, now=now)
            raise


__all__ = ["HudActivityProjector", "HudOutboxConsumer", "PHASES", "EVENT_LABELS"]
