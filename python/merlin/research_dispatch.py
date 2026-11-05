"""Approval- and MCFC-lease-gated research task dispatch.

Ranking is advisory. This module requires the canonical hypothesis ledger plus
independent approval and lease validators before it can enqueue a Hermes task.
It never launches a process or grants authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any, Callable

from merlin.event_outbox import MerlinEventOutbox
from merlin.telemetry import agent_event_sink
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.research_optimizer import (
    ResearchCandidate, ResearchMetrics, ResearchWeights, rank_research_candidates,
)


@dataclass(frozen=True)
class ResearchTask:
    task_id: str
    hypothesis_id: str
    objective: str
    stage: str
    metrics: ResearchMetrics
    constraints: dict[str, bool]
    resource_budget: dict[str, int]
    approval_ref: str
    lease_ref: str
    evidence_refs: tuple[str, ...] = ()
    experiment_spec: dict[str, Any] | None = None

    def validate(self) -> None:
        for name, value in (("task_id", self.task_id), ("hypothesis_id", self.hypothesis_id),
                            ("objective", self.objective), ("stage", self.stage),
                            ("approval_ref", self.approval_ref), ("lease_ref", self.lease_ref)):
            if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                raise ValueError(name + " must be a non-empty bounded string")
        if not isinstance(self.metrics, ResearchMetrics):
            raise ValueError("metrics must be ResearchMetrics")
        if not isinstance(self.constraints, dict) or any(
            not isinstance(key, str) or not isinstance(value, bool)
            for key, value in self.constraints.items()
        ):
            raise ValueError("constraints must map string names to booleans")
        required = {"cpu_cores", "memory_bytes", "max_wall_seconds", "compute_budget_units"}
        if not isinstance(self.resource_budget, dict) or not required.issubset(self.resource_budget):
            raise ValueError("resource_budget is missing required limits")
        for key, value in self.resource_budget.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("resource budget values must be positive integers")
        if any(not isinstance(ref, str) or not ref.strip() for ref in self.evidence_refs):
            raise ValueError("evidence_refs must be non-empty strings")
        if self.experiment_spec is not None and not isinstance(self.experiment_spec, dict):
            raise ValueError("experiment_spec must be an object")


class ResearchDispatchCoordinator:
    def __init__(self, outbox: MerlinEventOutbox, hypotheses: HypothesisLedger, *,
                 approval_validator: Callable[[str, ResearchTask], bool],
                 lease_validator: Callable[[str, dict[str, int]], bool],
                 weights: ResearchWeights | None = None):
        if not isinstance(outbox, MerlinEventOutbox):
            raise ValueError("outbox must be a MerlinEventOutbox")
        if not isinstance(hypotheses, HypothesisLedger):
            raise ValueError("hypotheses must be the canonical HypothesisLedger")
        if not callable(approval_validator) or not callable(lease_validator):
            raise ValueError("approval and MCFC lease validators are required")
        self.outbox = outbox
        self.hypotheses = hypotheses
        self.approval_validator = approval_validator
        self.lease_validator = lease_validator
        self.weights = weights
        self.emit_event = agent_event_sink(outbox, "hermes")
        self.emit_mcfc_event = agent_event_sink(outbox, "mcfc")

    def rank(self, tasks: list[ResearchTask]):
        for task in tasks:
            task.validate()
            self.hypotheses.get(task.hypothesis_id)
        candidates = [
            ResearchCandidate(task.task_id, task.metrics, task.constraints, task.evidence_refs)
            for task in tasks
        ]
        return rank_research_candidates(candidates, self.weights)

    def dispatch(self, task: ResearchTask) -> dict[str, Any]:
        task.validate()
        self.hypotheses.get(task.hypothesis_id)
        if not task.constraints or not all(task.constraints.values()):
            raise PermissionError("research task failed hard admission constraints")
        if not self.approval_validator(task.approval_ref, task):
            raise PermissionError("explicit operator approval was not validated")
        if not self.lease_validator(task.lease_ref, task.resource_budget):
            raise PermissionError("active MCFC resource lease was not validated")
        payload = {
            "schema": "merlin-research-task/1",
            "task_id": task.task_id,
            "hypothesis_id": task.hypothesis_id,
            "objective": task.objective,
            "stage": task.stage,
            "metrics": asdict(task.metrics),
            "resource_budget": dict(task.resource_budget),
            "approval_ref": task.approval_ref,
            "lease_ref": task.lease_ref,
            "evidence_refs": list(task.evidence_refs),
            "experiment_spec": dict(task.experiment_spec or {}),
            "authority": "bounded_execution_only",
            "promotion_authority": False,
        }
        idempotency_key = "research-task:" + task.task_id
        outbox_id = "evt_" + hashlib.sha256(idempotency_key.encode()).hexdigest()
        already_queued = self.outbox.get(outbox_id) is not None
        queued = self.outbox.enqueue(
            idempotency_key=idempotency_key,
            topic="merlin.hermes.task",
            payload=payload,
        )
        if already_queued:
            return queued
        self.emit_mcfc_event(
            kind="agent.status", run_id=task.task_id, task_id=task.task_id,
            payload={"agent_id": "mcfc", "role": "resource governor",
                     "status": "leased", "activity": "resource lease validated",
                     "lease_ref": task.lease_ref},
        )
        self.emit_mcfc_event(
            kind="resource.sample", run_id=task.task_id, task_id=task.task_id,
            payload={"measurement_kind": "reserved",
                     "cpu_cores_reserved": task.resource_budget["cpu_cores"],
                     "memory_bytes_reserved": task.resource_budget["memory_bytes"],
                     "max_wall_seconds_reserved": task.resource_budget["max_wall_seconds"],
                     "compute_budget_units_reserved": task.resource_budget["compute_budget_units"],
                     "lease_ref": task.lease_ref},
        )
        self.emit_event(
            kind="task.started", run_id=task.task_id, task_id=task.task_id,
            payload={"agent_id": "hermes", "role": "orchestrator",
                     "status": "queued", "activity": "bounded task queued",
                     "hypothesis_id": task.hypothesis_id},
        )
        self.emit_event(
            kind="agent.status", run_id=task.task_id, task_id=task.task_id,
            payload={"agent_id": "hermes", "role": "orchestrator",
                     "status": "queued", "activity": "awaiting worker acknowledgement"},
        )
        return queued


__all__ = ["ResearchTask", "ResearchDispatchCoordinator"]
