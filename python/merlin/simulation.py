"""Deterministic, bounded Merlin world simulator for HUD development.

All values produced here are explicitly simulated. This module does not launch
processes, call models, access the network, or grant tool/repository authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from threading import RLock
from typing import Any


@dataclass
class SimState:
    tick: int = 0
    mode: str = "running"
    phase: str = "observe"
    task: str = "Map current system state"
    progress: float = 0.0
    confidence: float = 0.62
    uncertainty: float = 0.38
    cpu_percent: float = 8.0
    memory_mb: float = 420.0
    queue_depth: int = 2
    active_agents: int = 1
    verified_claims: int = 0
    candidate_hypotheses: int = 2
    strategy: str = "baseline"
    last_action: str = "initialize"
    decision: str = "Observe the environment before choosing work."
    decision_basis: list[str] = field(default_factory=lambda: ["No simulation steps have run yet."])
    events: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)


class MerlinSimulation:
    """A deterministic miniature research environment with bounded controls."""

    ACTIONS = {"advance", "pause", "resume", "inject_uncertainty", "verify",
               "decompose", "explore", "compress", "reset"}

    def __init__(self) -> None:
        self._lock = RLock()
        self.state = SimState()
        self._record("world.initialized", "Simulation world initialized", {"mode": "running"})

    def _event(self, kind: str, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "id": len(self.state.events) + 1,
            "tick": self.state.tick,
            "at": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "message": message,
            "data": data or {},
            "source": "simulation",
        }

    def _record(self, kind: str, message: str, data: dict[str, Any] | None = None) -> None:
        self.state.events.append(self._event(kind, message, data))
        self.state.events = self.state.events[-120:]

    def _metric(self) -> None:
        s = self.state
        self.state.metrics.append({
            "tick": s.tick, "progress": round(s.progress, 3),
            "confidence": round(s.confidence, 3), "uncertainty": round(s.uncertainty, 3),
            "cpu_percent": round(s.cpu_percent, 2), "memory_mb": round(s.memory_mb, 2),
            "queue_depth": s.queue_depth, "verified_claims": s.verified_claims,
        })
        self.state.metrics = self.state.metrics[-80:]

    def _decide(self) -> tuple[str, list[str]]:
        s = self.state
        if s.mode == "paused":
            return "Hold execution; preserve current state.", ["Operator paused the simulation."]
        if s.uncertainty >= 0.65:
            return "Decompose the problem and isolate uncertain assumptions.", [
                f"Uncertainty is {s.uncertainty:.2f}, above the 0.65 threshold.",
                "A smaller subproblem is easier to test independently.",
            ]
        if s.queue_depth > 3:
            return "Compress the queue and prioritize the smallest verifiable task.", [
                f"Queue depth is {s.queue_depth}.", "Resource steward prioritizes bounded work.",
            ]
        if s.progress > 0.0 and s.tick % 4 == 0:
            return "Run a verification pass before expanding the search.", [
                "Progress has accumulated.", "Verification is preferred over unmeasured expansion.",
            ]
        return "Advance the current bounded research task.", [
            "Uncertainty is below the decomposition threshold.",
            "Queue and resource levels are within the simulated budget.",
        ]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            s = self.state
            decision, basis = self._decide()
            return {
                "schema": "merlin-sim-state/1",
                "environment": "deterministic_simulation",
                "simulation_only": True,
                "state": {**asdict(s), "events": s.events[-30:], "metrics": s.metrics[-40:]},
                "decision_preview": {"action": self._recommended_action(), "summary": decision, "basis": basis},
                "world": {
                    "nodes": [
                        {"id": "observe", "label": "Observe", "status": "active" if s.phase == "observe" else "complete"},
                        {"id": "hypothesize", "label": "Hypothesize", "status": "active" if s.phase == "hypothesize" else ("complete" if s.tick > 1 else "pending")},
                        {"id": "experiment", "label": "Experiment", "status": "active" if s.phase == "experiment" else ("complete" if s.tick > 3 else "pending")},
                        {"id": "verify", "label": "Verify", "status": "active" if s.phase == "verify" else ("complete" if s.verified_claims else "pending")},
                        {"id": "consolidate", "label": "Consolidate", "status": "active" if s.phase == "consolidate" else "pending"},
                    ],
                    "edges": [["observe", "hypothesize"], ["hypothesize", "experiment"],
                              ["experiment", "verify"], ["verify", "consolidate"]],
                },
            }

    def _recommended_action(self) -> str:
        s = self.state
        if s.mode == "paused":
            return "resume"
        if s.uncertainty >= 0.65:
            return "decompose"
        if s.queue_depth > 3:
            return "compress"
        if s.tick > 0 and s.tick % 4 == 0:
            return "verify"
        return "advance"

    def step(self, action: str) -> dict[str, Any]:
        if action not in self.ACTIONS:
            raise ValueError("unsupported simulation action")
        with self._lock:
            s = self.state
            if action == "reset":
                self.state = SimState()
                self._record("world.reset", "Simulation reset to initial conditions", {})
                self._metric()
                return self.snapshot()
            if action == "pause":
                s.mode = "paused"
                s.last_action = action
                s.decision = "Execution paused by operator."
                s.decision_basis = ["Manual control takes precedence over simulated policy."]
                self._record("control.pause", "Simulation paused", {})
                self._metric()
                return self.snapshot()
            if action == "resume":
                s.mode = "running"
                s.last_action = action
                self._record("control.resume", "Simulation resumed", {})
            elif s.mode == "paused":
                raise ValueError("simulation is paused; resume before advancing")
            else:
                s.tick += 1
                s.last_action = action
                if action == "inject_uncertainty":
                    s.uncertainty = min(0.95, s.uncertainty + 0.28)
                    s.confidence = max(0.1, 1.0 - s.uncertainty)
                    s.queue_depth += 1
                    s.phase = "observe"
                    self._record("world.uncertainty_injected", "A new uncertain assumption entered the world", {"uncertainty": s.uncertainty})
                elif action == "decompose":
                    s.phase = "hypothesize"
                    s.queue_depth = max(1, s.queue_depth - 1)
                    s.active_agents = 2
                    s.uncertainty = max(0.28, s.uncertainty - 0.12)
                    s.candidate_hypotheses += 1
                    self._record("cognition.decompose", "Merlin split the task into smaller hypotheses", {"hypotheses": s.candidate_hypotheses})
                elif action == "explore":
                    s.phase = "experiment"
                    s.candidate_hypotheses += 2
                    s.uncertainty = min(0.9, s.uncertainty + 0.06)
                    s.cpu_percent = min(92.0, s.cpu_percent + 12.0)
                    s.memory_mb = min(2800.0, s.memory_mb + 95.0)
                    s.strategy = "divergent_search"
                    self._record("research.explore", "Exploration generated competing hypotheses", {"hypotheses": s.candidate_hypotheses})
                elif action == "compress":
                    s.queue_depth = max(1, s.queue_depth - 2)
                    s.cpu_percent = max(4.0, s.cpu_percent - 4.0)
                    s.memory_mb = max(300.0, s.memory_mb - 60.0)
                    s.strategy = "resource_aware"
                    self._record("cognition.compress", "Merlin consolidated low-priority work", {"queue_depth": s.queue_depth})
                elif action == "verify":
                    s.phase = "verify"
                    s.verified_claims += 1
                    s.confidence = min(0.98, s.confidence + 0.09)
                    s.uncertainty = max(0.05, s.uncertainty - 0.1)
                    s.progress = min(1.0, s.progress + 0.08)
                    self._record("verification.passed", "A simulated claim passed its configured verifier", {"verified_claims": s.verified_claims})
                elif action == "advance":
                    s.progress = min(1.0, s.progress + 0.07)
                    s.queue_depth = max(0, s.queue_depth - 1)
                    s.cpu_percent = min(88.0, max(5.0, s.cpu_percent + (3.0 if s.queue_depth else -1.5)))
                    s.memory_mb = min(2400.0, max(360.0, s.memory_mb + 18.0))
                    s.phase = ("hypothesize", "experiment", "verify", "consolidate")[min(3, s.tick // 3)]
                    s.uncertainty = max(0.08, s.uncertainty - 0.025)
                    self._record("task.progress", "Research task advanced one bounded simulation step", {"progress": s.progress})
            s.decision, s.decision_basis = self._decide()
            self._metric()
            return self.snapshot()

    def get_events(self, limit: int = 30) -> dict[str, Any]:
        with self._lock:
            return {"schema": "merlin-sim-events/1", "events": self.state.events[-max(1, min(120, limit)):]}

