"""Hermes worker lifecycle for approval-gated Merlin research tasks.

The worker consumes only the Hermes task topic. It never dispatches Avrea,
installs tools, or grants hypothesis-promotion authority. Actual execution is
possible only through explicitly injected, stage-scoped handlers.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable, Mapping

from merlin.event_outbox import MerlinEventOutbox
from merlin.telemetry import agent_event_sink

HERMES_TASK_TOPIC = "merlin.hermes.task"


@dataclass(frozen=True)
class TaskExecutionContext:
    task_id: str
    hypothesis_id: str
    resource_budget: Mapping[str, int]
    approval_ref: str
    lease_ref: str
    idempotency_key: str
    deadline_epoch: float
    emit_progress: Callable[[str, Mapping[str, Any] | None], None]
    emit_tool_event: Callable[[str, str, Mapping[str, Any]], None]


class HermesWorker:
    """Lease, validate, execute and acknowledge one bounded research task."""

    def __init__(
        self,
        outbox: MerlinEventOutbox,
        *,
        handlers: Mapping[str, Callable[[Mapping[str, Any], TaskExecutionContext], Mapping[str, Any]]],
        approval_validator: Callable[[str, Mapping[str, Any]], bool],
        lease_validator: Callable[[str, Mapping[str, int]], bool],
        worker_id: str = "hermes-worker",
        lease_seconds: float = 120,
        max_attempts: int = 4,
        retry_delay_seconds: float = 2,
    ):
        if not isinstance(outbox, MerlinEventOutbox):
            raise ValueError("outbox must be a MerlinEventOutbox")
        if not isinstance(handlers, Mapping) or not handlers:
            raise ValueError("at least one explicitly injected stage handler is required")
        if any(not isinstance(stage, str) or not stage.strip() or not callable(handler)
               for stage, handler in handlers.items()):
            raise ValueError("handlers must map stage names to callables")
        if not callable(approval_validator) or not callable(lease_validator):
            raise ValueError("approval and lease validators are required")
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, (int, float)) or lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if isinstance(retry_delay_seconds, bool) or not isinstance(retry_delay_seconds, (int, float)) or retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be non-negative")
        self.outbox = outbox
        self.handlers = dict(handlers)
        self.approval_validator = approval_validator
        self.lease_validator = lease_validator
        self.worker_id = worker_id.strip()
        self.lease_seconds = float(lease_seconds)
        self.max_attempts = max_attempts
        self.retry_delay_seconds = float(retry_delay_seconds)
        self.emit_event = agent_event_sink(outbox, "hermes")

    @staticmethod
    def _validate_payload(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict) or payload.get("schema") != "merlin-research-task/1":
            raise ValueError("unsupported Hermes task schema")
        for key in ("task_id", "hypothesis_id", "objective", "stage", "approval_ref", "lease_ref"):
            value = payload.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                raise ValueError("task " + key + " is missing or invalid")
        budget = payload.get("resource_budget")
        required = {"cpu_cores", "memory_bytes", "max_wall_seconds", "compute_budget_units"}
        if not isinstance(budget, dict) or not required.issubset(budget):
            raise ValueError("task resource budget is incomplete")
        for key, value in budget.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("task resource budget values must be positive integers")
        if payload.get("promotion_authority") is not False:
            raise PermissionError("Hermes tasks cannot carry hypothesis-promotion authority")
        if payload.get("authority") != "bounded_execution_only":
            raise PermissionError("Hermes task authority is not bounded execution")
        return payload

    def _progress(self, task_id: str, hypothesis_id: str, stage: str,
                  summary: str, details: Mapping[str, Any] | None = None) -> None:
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 500:
            raise ValueError("progress summary must be a short non-empty string")
        body = {"agent_id": "hermes", "role": "research orchestrator",
                "status": "running", "stage": stage, "summary": summary,
                "hypothesis_id": hypothesis_id}
        if details is not None:
            if not isinstance(details, Mapping):
                raise ValueError("progress details must be an object")
            body["details"] = dict(details)
        self.emit_event(kind="task.progress", run_id=task_id, task_id=task_id, payload=body)

    def run_once(self, *, now: float | None = None) -> dict[str, Any] | None:
        lease = self.outbox.claim_next(
            self.worker_id, lease_seconds=self.lease_seconds,
            topics=[HERMES_TASK_TOPIC], now=now,
        )
        if lease is None:
            return None
        event_id, token = lease["event_id"], lease["lease_token"]
        payload = lease["payload"]
        task_id = str(payload.get("task_id") or event_id) if isinstance(payload, dict) else event_id
        try:
            task = self._validate_payload(payload)
            stage = task["stage"]
            handler = self.handlers.get(stage)
            if handler is None:
                raise ValueError("no Hermes handler is registered for stage " + stage)
            if not self.approval_validator(task["approval_ref"], task):
                raise PermissionError("operator approval is not valid at execution time")
            if not self.lease_validator(task["lease_ref"], task["resource_budget"]):
                raise PermissionError("MCFC lease is not valid at execution time")
            if task["resource_budget"]["max_wall_seconds"] > self.lease_seconds:
                raise PermissionError("task wall-time budget exceeds the worker lease duration")
            deadline_epoch = time.time() + task["resource_budget"]["max_wall_seconds"]
            idempotency_key = "hermes-task-handler:" + task["task_id"]
            self.emit_event(
                kind="agent.status", run_id=task_id, task_id=task_id,
                payload={"agent_id": "hermes", "role": "research orchestrator",
                         "status": "running", "activity": "worker claimed and revalidated task",
                         "worker_id": self.worker_id},
            )
            self._progress(task_id, task["hypothesis_id"], stage, "Execution handler started")

            def progress(summary: str, details: Mapping[str, Any] | None = None) -> None:
                if time.time() > deadline_epoch:
                    raise TimeoutError("task execution exceeded its declared wall-time budget")
                self._progress(task_id, task["hypothesis_id"], stage, summary, details)

            def tool_event(kind: str, tool_name: str, details: Mapping[str, Any]) -> None:
                if kind not in {"agent.tool.started", "agent.tool.completed"}:
                    raise ValueError("unsupported tool lifecycle event")
                if not isinstance(tool_name, str) or not tool_name.strip() or len(tool_name) > 120:
                    raise ValueError("tool name is invalid")
                body = {**dict(details), "agent_id": "hermes", "tool": tool_name}
                self.emit_event(kind=kind, run_id=task_id, task_id=task_id, payload=body)

            context = TaskExecutionContext(
                task_id=task_id, hypothesis_id=task["hypothesis_id"],
                resource_budget=dict(task["resource_budget"]),
                approval_ref=task["approval_ref"], lease_ref=task["lease_ref"],
                idempotency_key=idempotency_key, deadline_epoch=deadline_epoch,
                emit_progress=progress, emit_tool_event=tool_event,
            )
            result = handler(task, context)
            if not isinstance(result, Mapping):
                raise ValueError("Hermes handler must return a result object")
            result = dict(result)
            evidence_refs = result.pop("evidence_refs", [])
            if not isinstance(evidence_refs, (list, tuple)) or any(
                not isinstance(ref, str) or not ref.strip() for ref in evidence_refs
            ):
                raise ValueError("handler evidence_refs must be non-empty strings")
            receipt = {
                "schema": "merlin-hermes-task-result/1",
                "task_id": task_id, "hypothesis_id": task["hypothesis_id"],
                "stage": stage, "status": "completed", "result": result,
                "evidence_refs": list(evidence_refs),
                "promotion_authority": False,
            }
            self.emit_event(
                kind="task.completed", run_id=task_id, task_id=task_id,
                evidence_refs=list(evidence_refs),
                payload={"agent_id": "hermes", "role": "research orchestrator",
                         "status": "completed", "activity": "bounded handler completed",
                         "hypothesis_id": task["hypothesis_id"]},
            )
            self.emit_event(
                kind="agent.status", run_id=task_id, task_id=task_id,
                payload={"agent_id": "hermes", "role": "research orchestrator",
                         "status": "completed", "activity": "result receipt stored"},
            )
            ack = self.outbox.acknowledge(event_id, self.worker_id, token,
                                          result=receipt, now=now)
            return {"status": "completed", "event_id": event_id,
                    "receipt": receipt, "outbox_state": ack["state"]}
        except PermissionError as exc:
            rejection = {"schema": "merlin-hermes-task-result/1",
                         "task_id": task_id, "status": "rejected",
                         "reason": str(exc), "promotion_authority": False}
            self.emit_event(
                kind="system.error", run_id=task_id, task_id=task_id,
                payload={"agent_id": "hermes", "component": "worker_admission",
                         "status": "rejected", "error_type": type(exc).__name__,
                         "summary": str(exc)[:300]},
            )
            ack = self.outbox.acknowledge(event_id, self.worker_id, token,
                                          result=rejection, now=now)
            return {"status": "rejected", "event_id": event_id,
                    "outbox_state": ack["state"]}
        except Exception as exc:
            self.emit_event(
                kind="system.error", run_id=task_id, task_id=task_id,
                payload={"agent_id": "hermes", "component": "worker_execution",
                         "status": "retrying", "error_type": type(exc).__name__,
                         "summary": str(exc)[:300]},
            )
            retried = self.outbox.retry(
                event_id, self.worker_id, token,
                type(exc).__name__ + ": " + str(exc),
                delay_seconds=self.retry_delay_seconds,
                max_attempts=self.max_attempts, now=now,
            )
            self.emit_event(
                kind="agent.status", run_id=task_id, task_id=task_id,
                payload={"agent_id": "hermes", "role": "research orchestrator",
                         "status": retried["state"],
                         "activity": "handler failed; outbox retry policy applied"},
            )
            return {"status": retried["state"], "event_id": event_id,
                    "error": type(exc).__name__}

    def run_forever(self, stop_event: Any, *, idle_seconds: float = 0.5) -> None:
        if not hasattr(stop_event, "is_set") or not hasattr(stop_event, "wait"):
            raise ValueError("stop_event must provide is_set and wait")
        if isinstance(idle_seconds, bool) or not isinstance(idle_seconds, (int, float)) or idle_seconds <= 0:
            raise ValueError("idle_seconds must be positive")
        while not stop_event.is_set():
            result = self.run_once()
            if result is None:
                stop_event.wait(idle_seconds)


__all__ = ["HermesWorker", "TaskExecutionContext", "HERMES_TASK_TOPIC"]
