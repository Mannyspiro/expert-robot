"""Hermes worker lifecycle for approval-gated Merlin research tasks.

The worker consumes only the Hermes task topic. It never dispatches Avrea,
installs tools, or grants hypothesis-promotion authority. Actual execution is
possible only through explicitly injected, stage-scoped handlers.
"""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
import hashlib
import json
import math
import threading
import time
from typing import Any, Callable, Mapping

from .event_outbox import MerlinEventOutbox, LeaseConflict
from .artifact_ref import ArtifactRef
from .failure_prevention import failure_plan, encode_failure_plan
from .telemetry import agent_event_sink, normalize_event

HERMES_TASK_TOPIC = "merlin.hermes.task"


@dataclass(frozen=True)
class TaskExecutionContext:
    task_id: str
    hypothesis_id: str
    resource_budget: Mapping[str, int]
    approval_ref: str
    lease_ref: str
    artifact_refs: tuple[Mapping[str, Any], ...]
    idempotency_key: str
    deadline_epoch: float
    emit_progress: Callable[[str, Mapping[str, Any] | None], None]
    emit_tool_event: Callable[[str, str, Mapping[str, Any]], None]
    heartbeat: Callable[[], None]
    check_cancelled: Callable[[], None]


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
        artifact_ref_validator: Callable[[Mapping[str, Any]], bool] | None = None,
        max_same_failures: int = 2,
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
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, (int, float)) or not 0.05 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 0.05 and 3600 seconds")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 1_000_000:
            raise ValueError("max_attempts must be a positive bounded integer")
        if isinstance(retry_delay_seconds, bool) or not isinstance(retry_delay_seconds, (int, float)) or not math.isfinite(retry_delay_seconds) or retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be finite and non-negative")
        if type(max_same_failures) is not int or not 1 <= max_same_failures <= 100:
            raise ValueError("max_same_failures must be between 1 and 100")
        self.max_same_failures = max_same_failures
        self.outbox = outbox
        self.handlers = dict(handlers)
        self.approval_validator = approval_validator
        self.lease_validator = lease_validator
        self.artifact_ref_validator = artifact_ref_validator
        self.worker_id = worker_id.strip()
        self.lease_seconds = float(lease_seconds)
        self.max_attempts = max_attempts
        self.retry_delay_seconds = float(retry_delay_seconds)
        self.emit_event = agent_event_sink(outbox, "hermes")

    @staticmethod
    def _validate_payload(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict) or payload.get("schema") != "merlin-research-task/2":
            raise ValueError("unsupported Hermes task schema")
        for key in ("task_id", "hypothesis_id", "objective", "stage", "approval_ref", "lease_ref"):
            value = payload.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                raise ValueError("task " + key + " is missing or invalid")
        if len(payload["task_id"]) > 128:
            raise ValueError("task_id exceeds the telemetry identity boundary")
        budget = payload.get("resource_budget")
        required = {"cpu_cores", "memory_bytes", "max_wall_seconds", "compute_budget_units"}
        if not isinstance(budget, dict) or not required.issubset(budget):
            raise ValueError("task resource budget is incomplete")
        if set(budget) != required:
            raise ValueError("task resource budget must contain only the four declared fields")
        limits = {"cpu_cores": 256, "memory_bytes": 1 << 50,
                  "max_wall_seconds": 86400, "compute_budget_units": 1_000_000_000}
        for key, value in budget.items():
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= limits[key]:
                raise ValueError("task resource budget value is outside its bounded range: " + key)
        refs = payload.get("artifact_refs")
        if not isinstance(refs, list):
            raise ValueError("Hermes task artifact_refs must be a list")
        for ref in refs:
            ArtifactRef.from_mapping(ref)
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

    def _diagnostic_event(self, **event: Any) -> bool:
        """Best-effort observation must not undo a persisted failure decision."""
        try:
            self.emit_event(**event)
            return True
        except Exception:
            return False

    def _record_failure(self, lease: Mapping[str, Any], task_id: str, phase: str,
                        error: Exception, now: float | None) -> dict[str, Any]:
        event_id, token = lease["event_id"], lease["lease_token"]
        plan = failure_plan(error=error, event_id=event_id, phase=phase,
            attempt=lease["attempts"], max_attempts=self.max_attempts,
            max_same_failures=self.max_same_failures, previous_error=lease.get("last_error"))
        limit = self.max_attempts if plan["action"] == "retry_same_approved_task" else lease["attempts"]
        try:
            retried = self.outbox.retry(event_id, self.worker_id, token, encode_failure_plan(plan),
                delay_seconds=self.retry_delay_seconds, max_attempts=limit, now=now)
        except LeaseConflict:
            current = self.outbox.get(event_id)
            return {"status": "cancelled" if current and current.get("state") == "cancelled"
                    else "lease_lost", "event_id": event_id}
        # The durable decision is stored first. No exception message or traceback
        # is sent to shared telemetry, even when the diagnostic sink itself fails.
        observed = self._diagnostic_event(
            kind="system.error", run_id=task_id, task_id=task_id,
            payload={"agent_id": "hermes", "component": "worker_execution",
                     "status": retried["state"], "failure_plan": plan},
        )
        status_observed = self._diagnostic_event(
            kind="agent.status", run_id=task_id, task_id=task_id,
            payload={"agent_id": "hermes", "role": "research orchestrator",
                     "status": retried["state"],
                     "activity": "failure contained; bounded retry or reframing required"},
        )
        telemetry = ("recorded" if observed and status_observed else
                     "partial" if observed or status_observed else "unavailable")
        return {"status": retried["state"], "event_id": event_id,
                "error": plan["category"], "failure_plan": plan,
                "telemetry_status": telemetry}

    def run_once(self, *, now: float | None = None) -> dict[str, Any] | None:
        lease = self.outbox.claim_next(
            self.worker_id, lease_seconds=self.lease_seconds,
            topics=[HERMES_TASK_TOPIC], now=now,
        )
        if lease is None:
            return None
        event_id, token = lease["event_id"], lease["lease_token"]
        payload = lease["payload"]
        raw_task_id = payload.get("task_id") if isinstance(payload, dict) else None
        task_id = (raw_task_id if isinstance(raw_task_id, str) and raw_task_id.strip()
                   and len(raw_task_id) <= 128 else event_id)
        phase = "admission"
        heartbeat_stop = threading.Event()
        lease_lost = threading.Event()
        heartbeat_thread = None
        receipt = None

        def stop_heartbeat() -> None:
            heartbeat_stop.set()
            if heartbeat_thread is not None and heartbeat_thread.is_alive():
                heartbeat_thread.join(timeout=2)

        def heartbeat_once() -> None:
            row = self.outbox.get(event_id)
            if row is None or row.get("state") != "leased" or row.get("lease_token") != token:
                lease_lost.set()
                raise LeaseConflict("Hermes worker no longer owns the task lease")
            self.outbox.heartbeat(
                event_id, self.worker_id, token, lease_seconds=self.lease_seconds,
            )

        # Explicit clocks are used by deterministic tests. Production calls
        # use real time and keep the lease alive in a supervisor thread.
        if now is None:
            def heartbeat_loop() -> None:
                interval = max(0.05, min(30.0, self.lease_seconds / 3.0))
                while not heartbeat_stop.wait(interval):
                    try:
                        heartbeat_once()
                    except Exception:
                        lease_lost.set()
                        return
            heartbeat_thread = threading.Thread(
                target=heartbeat_loop, name="merlin-hermes-lease-heartbeat", daemon=True,
            )
            heartbeat_thread.start()

        try:
            task = self._validate_payload(payload)
            stage = task["stage"]
            handler = self.handlers.get(stage)
            if handler is None:
                raise ValueError("no Hermes handler is registered for stage " + stage)
            if self.approval_validator(task["approval_ref"], deepcopy(task)) is not True:
                raise PermissionError("operator approval is not valid at execution time")
            if self.lease_validator(task["lease_ref"], dict(task["resource_budget"])) is not True:
                raise PermissionError("MCFC lease is not valid at execution time")
            if task["artifact_refs"] and self.artifact_ref_validator is None:
                raise RuntimeError("task artifact references require a canonical registry validator")
            for artifact_ref in task["artifact_refs"]:
                if self.artifact_ref_validator(deepcopy(artifact_ref)) is not True:
                    raise ValueError("Hermes task contains an unresolved or unverified artifact reference")
            deadline_epoch = time.time() + task["resource_budget"]["max_wall_seconds"]

            def check_cancelled() -> None:
                if time.time() > deadline_epoch:
                    raise TimeoutError("task execution exceeded its declared wall-time budget")
                if lease_lost.is_set():
                    raise LeaseConflict("Hermes worker lost its task lease")
                current = self.outbox.get(event_id)
                if current is None or current.get("state") == "cancelled":
                    raise InterruptedError("task was cancelled")
                if current.get("state") != "leased" or current.get("lease_token") != token:
                    lease_lost.set()
                    raise LeaseConflict("Hermes worker no longer owns the task lease")
                expiry = current.get("lease_expires_at")
                lease_clock = time.time() if now is None else float(now)
                if expiry is None or expiry <= lease_clock:
                    lease_lost.set()
                    raise LeaseConflict("Hermes worker task lease expired")
                if self.approval_validator(task["approval_ref"], deepcopy(task)) is not True:
                    raise PermissionError("operator approval was revoked during execution")
                if self.lease_validator(task["lease_ref"], dict(task["resource_budget"])) is not True:
                    raise PermissionError("MCFC lease was revoked during execution")

            def renew_lease() -> None:
                check_cancelled()
                heartbeat_once()

            phase = "telemetry"
            self.emit_event(
                kind="agent.status", run_id=task_id, task_id=task_id,
                payload={"agent_id": "hermes", "role": "research orchestrator",
                         "status": "running", "activity": "worker claimed and revalidated task",
                         "worker_id": self.worker_id},
            )
            self._progress(task_id, task["hypothesis_id"], stage, "Execution handler started")

            def progress(summary: str, details: Mapping[str, Any] | None = None) -> None:
                check_cancelled()
                self._progress(task_id, task["hypothesis_id"], stage, summary, details)

            def tool_event(kind: str, tool_name: str, details: Mapping[str, Any]) -> None:
                check_cancelled()
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
                artifact_refs=tuple(deepcopy(task["artifact_refs"])),
                idempotency_key="hermes-task-handler:" + task["task_id"],
                deadline_epoch=deadline_epoch,
                emit_progress=progress, emit_tool_event=tool_event,
                heartbeat=renew_lease, check_cancelled=check_cancelled,
            )
            handler_task = deepcopy(task)
            phase = "admission"
            check_cancelled()
            phase = "execution"
            result = handler(handler_task, context)
            phase = "result_validation"
            if handler_task != task:
                raise ValueError("Hermes handler mutated its admitted task")
            check_cancelled()
            if not isinstance(result, Mapping):
                raise ValueError("Hermes handler must return a result object")
            result = dict(result)
            evidence_refs = result.pop("evidence_refs", [])
            output_artifact_refs = result.pop("artifact_refs", [])
            if not isinstance(evidence_refs, (list, tuple)) or any(
                not isinstance(ref, str) or not ref.strip() for ref in evidence_refs
            ):
                raise ValueError("handler evidence_refs must be non-empty strings")
            if not isinstance(output_artifact_refs, (list, tuple)):
                raise ValueError("handler artifact_refs must be a list of exact references")
            output_artifact_refs = [ArtifactRef.from_mapping(ref).to_dict()
                                    for ref in output_artifact_refs]
            if output_artifact_refs and self.artifact_ref_validator is None:
                raise RuntimeError("output artifact references require a canonical registry validator")
            for artifact_ref in output_artifact_refs:
                if self.artifact_ref_validator(deepcopy(artifact_ref)) is not True:
                    raise ValueError("handler returned an unresolved or unverified artifact reference")
            receipt = {
                "schema": "merlin-hermes-task-result/2",
                "task_id": task_id, "hypothesis_id": task["hypothesis_id"],
                "stage": stage, "status": "completed", "result": result,
                "evidence_refs": list(evidence_refs),
                "input_artifact_refs": list(task["artifact_refs"]),
                "output_artifact_refs": output_artifact_refs,
                "promotion_authority": False,
            }
            # Normalize once to the exact JSON representation that will be stored.
            # This also makes lost-reply reconciliation insensitive to tuple/list
            # differences in otherwise valid handler return values.
            receipt = json.loads(json.dumps(receipt, sort_keys=True, separators=(",", ":"),
                                             ensure_ascii=False, allow_nan=False))
            # Construct announcements without publishing them. The receipt and
            # both announcements commit together or not at all in the same outbox.
            receipt_digest = hashlib.sha256(json.dumps(
                receipt, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()
            completion_events = []
            for kind, activity in (("task.completed", "bounded handler completed"),
                                   ("agent.status", "result receipt stored")):
                telemetry_id = hashlib.sha256(
                    (event_id + ":" + kind + ":" + receipt_digest).encode("utf-8")
                ).hexdigest()
                event = normalize_event({
                    "event_id": telemetry_id, "source": "hermes", "kind": kind,
                    "run_id": task_id, "task_id": task_id,
                    "evidence_refs": list(evidence_refs),
                    "payload": {"agent_id": "hermes", "role": "research orchestrator",
                                "status": "completed", "activity": activity,
                                "hypothesis_id": task["hypothesis_id"],
                                "task_event_id": event_id, "receipt_sha256": receipt_digest},
                })
                completion_events.append({"idempotency_key": "telemetry:" + telemetry_id,
                                          "topic": "merlin.telemetry." + kind, "payload": event})
            stop_heartbeat()
            check_cancelled()
            phase = "acknowledgement"
            ack = self.outbox.acknowledge_with_events(
                event_id, self.worker_id, token, result=receipt,
                events=completion_events, now=now,
            )
            return {"status": "completed", "event_id": event_id,
                    "receipt": receipt, "outbox_state": ack["state"]}
        except InterruptedError as exc:
            stop_heartbeat()
            current = self.outbox.get(event_id)
            if current is not None and current.get("state") == "cancelled":
                self._diagnostic_event(
                    kind="agent.status", run_id=task_id, task_id=task_id,
                    payload={"agent_id": "hermes", "status": "cancelled",
                             "activity": "worker observed cooperative cancellation"},
                )
                return {"status": "cancelled", "event_id": event_id}
            return self._record_failure(lease, task_id, phase, exc, now)
        except PermissionError as exc:
            stop_heartbeat()
            plan = failure_plan(error=exc, event_id=event_id, phase=phase,
                attempt=lease["attempts"], max_attempts=self.max_attempts,
                max_same_failures=self.max_same_failures, previous_error=lease.get("last_error"))
            rejection = {"schema": "merlin-hermes-task-result/2",
                         "task_id": task_id, "status": "rejected",
                         "reason": "approval_or_lease_denied", "input_artifact_refs": [],
                         "output_artifact_refs": [], "promotion_authority": False,
                         "failure_plan": plan}
            try:
                ack = self.outbox.acknowledge(event_id, self.worker_id, token,
                                              result=rejection, now=now)
            except LeaseConflict:
                current = self.outbox.get(event_id)
                return {"status": "cancelled" if current and current.get("state") == "cancelled"
                        else "lease_lost", "event_id": event_id}
            except Exception:
                current = self.outbox.get(event_id)
                if not current or current.get("state") != "acknowledged" or current.get("result") != rejection:
                    raise
                ack = current
            observed = self._diagnostic_event(
                kind="system.error", run_id=task_id, task_id=task_id,
                payload={"agent_id": "hermes", "component": "worker_admission",
                         "status": "rejected", "failure_plan": plan},
            )
            return {"status": "rejected", "event_id": event_id, "outbox_state": ack["state"],
                    "telemetry_status": "recorded" if observed else "unavailable"}
        except LeaseConflict:
            stop_heartbeat()
            current = self.outbox.get(event_id)
            return {"status": "cancelled" if current and current.get("state") == "cancelled"
                    else "lease_lost", "event_id": event_id}
        except Exception as exc:
            stop_heartbeat()
            current = self.outbox.get(event_id)
            if (receipt is not None and current is not None
                    and current.get("state") == "acknowledged" and current.get("result") == receipt):
                return {"status": "completed", "event_id": event_id,
                        "receipt": receipt, "outbox_state": "acknowledged"}
            if current is not None and current.get("state") == "cancelled":
                return {"status": "cancelled", "event_id": event_id}
            if current is None or current.get("state") != "leased" or current.get("lease_token") != token:
                return {"status": "lease_lost", "event_id": event_id}
            return self._record_failure(lease, task_id, phase, exc, now)
        finally:
            stop_heartbeat()

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
