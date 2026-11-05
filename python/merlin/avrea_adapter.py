"""Injected Avrea runner transport with approval, MCFC and result provenance gates.

No provider-specific API is assumed. A real Avrea client must be injected by the
deployment and return the documented neutral receipt shape.
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Mapping

from merlin.event_outbox import MerlinEventOutbox
from merlin.project_registry import MerlinRegistry
from merlin.telemetry import agent_event_sink


class AvreaAdapter:
    def __init__(self, *, dispatch_transport: Callable[[dict[str, Any]], Mapping[str, Any]] | None,
                 collect_transport: Callable[[str], Mapping[str, Any]] | None,
                 approval_validator: Callable[[str, dict[str, Any]], bool],
                 lease_validator: Callable[[str, dict[str, Any]], bool],
                 registry: MerlinRegistry, outbox: MerlinEventOutbox):
        self.dispatch_transport = dispatch_transport
        self.collect_transport = collect_transport
        self.approval_validator = approval_validator
        self.lease_validator = lease_validator
        self.registry = registry
        self.outbox = outbox
        self.emit_event = agent_event_sink(outbox, "avrea")

    def dispatch(self, job: Mapping[str, Any]) -> dict[str, Any]:
        if self.dispatch_transport is None:
            raise RuntimeError("Avrea transport is not configured")
        payload = dict(job)
        if payload.get("schema") != "merlin-research-task/1":
            raise ValueError("unsupported Merlin job schema")
        if payload.get("promotion_authority") is not False:
            raise PermissionError("Avrea jobs cannot carry promotion authority")
        approval_ref, lease_ref = payload.get("approval_ref"), payload.get("lease_ref")
        budget = payload.get("resource_budget")
        if not isinstance(approval_ref, str) or not isinstance(lease_ref, str) or not isinstance(budget, dict):
            raise ValueError("job is missing approval, lease or resource budget")
        if not self.approval_validator(approval_ref, payload):
            raise PermissionError("operator approval was not validated")
        if not self.lease_validator(lease_ref, budget):
            raise PermissionError("active MCFC lease was not validated")
        dispatch_request = dict(payload)
        dispatch_request["idempotency_key"] = "merlin-avrea:" + str(payload.get("task_id", ""))
        response = self.dispatch_transport(dispatch_request)
        if not isinstance(response, Mapping):
            raise TypeError("Avrea dispatch transport must return a mapping")
        runner_id, job_id, status = response.get("runner_id"), response.get("job_id"), response.get("status")
        if not all(isinstance(value, str) and value.strip()
                   for value in (runner_id, job_id, status)):
            raise ValueError("Avrea response must identify runner_id, job_id and status")
        if status != "accepted":
            raise RuntimeError("Avrea did not accept the bounded job")
        receipt = {
            "schema": "merlin-avrea-dispatch-receipt/1",
            "provider": "avrea",
            "runner_id": runner_id,
            "job_id": job_id,
            "status": status,
            "task_id": payload.get("task_id"),
            "resource_budget": budget,
            "approval_ref": approval_ref,
            "lease_ref": lease_ref,
        }
        receipt["receipt_sha256"] = hashlib.sha256(
            _canonical(receipt).encode("utf-8")
        ).hexdigest()
        self.outbox.enqueue("avrea-dispatch:" + job_id, "merlin.avrea.dispatch.accepted", receipt)
        self.emit_event(
            kind="task.started", run_id=job_id, task_id=str(payload.get("task_id", job_id)),
            payload={"agent_id": runner_id, "role": "Avrea runner",
                     "status": "accepted", "activity": "bounded job accepted",
                     "job_id": job_id, "resource_budget": budget},
        )
        self.emit_event(
            kind="agent.status", run_id=job_id, task_id=str(payload.get("task_id", job_id)),
            payload={"agent_id": runner_id, "role": "Avrea runner",
                     "status": "accepted", "activity": "runner accepted job",
                     "job_id": job_id},
        )
        return receipt

    def collect(self, job_id: str, *, project_id: str,
                logical_prefix: str = "avrea-results") -> dict[str, Any]:
        if self.collect_transport is None:
            raise RuntimeError("Avrea result collection transport is not configured")
        response = self.collect_transport(job_id)
        if not isinstance(response, Mapping) or response.get("job_id") != job_id:
            raise ValueError("Avrea result does not match requested job")
        runner_id = response.get("runner_id")
        if not isinstance(runner_id, str) or not runner_id.strip():
            raise ValueError("Avrea result is missing runner identity")
        dispatch_event_id = "evt_" + hashlib.sha256(
            ("avrea-dispatch:" + job_id).encode("utf-8")
        ).hexdigest()
        dispatch_record = self.outbox.get(dispatch_event_id)
        if dispatch_record is None or dispatch_record["payload"].get("runner_id") != runner_id:
            raise ValueError("Avrea result runner does not match the accepted dispatch receipt")
        raw_artifacts = response.get("artifacts")
        if not isinstance(raw_artifacts, list):
            raise ValueError("Avrea result artifacts must be a list")
        saved = []
        for index, item in enumerate(raw_artifacts):
            if not isinstance(item, Mapping):
                raise ValueError("Avrea artifact entry must be a mapping")
            name, content = item.get("name"), item.get("content")
            if not isinstance(name, str) or not name.strip() or not isinstance(content, bytes):
                raise ValueError("Avrea artifact requires a name and raw bytes")
            logical_path = logical_prefix.rstrip("/") + "/" + job_id + "/" + name
            digest = self.registry.put_artifact(project_id, logical_path, content)
            if not self.registry.verify_artifact(digest):
                raise RuntimeError("collected Avrea artifact failed digest verification")
            saved.append({"name": name, "logical_path": logical_path,
                          "sha256": digest, "size_bytes": len(content)})
        result = {
            "schema": "merlin-avrea-result-receipt/1",
            "provider": "avrea", "runner_id": runner_id, "job_id": job_id,
            "status": str(response.get("status", "completed")),
            "artifacts": saved,
        }
        result["receipt_sha256"] = hashlib.sha256(_canonical(result).encode("utf-8")).hexdigest()
        self.outbox.enqueue("avrea-result:" + job_id, "merlin.avrea.result.collected", result)
        task_id = str(response.get("task_id") or job_id)
        metrics = response.get("resource_metrics")
        if isinstance(metrics, Mapping):
            observed = {key: metrics[key] for key in (
                "cpu_percent", "memory_bytes", "gpu_percent", "gpu_memory_bytes",
                "wall_seconds", "cpu_seconds", "peak_memory_bytes",
            ) if key in metrics}
            observed["measurement_kind"] = "observed"
            observed["runner_id"] = runner_id
            observed["job_id"] = job_id
            self.emit_event(kind="resource.sample", run_id=job_id, task_id=task_id,
                            payload=observed)
        self.emit_event(
            kind="task.completed", run_id=job_id, task_id=task_id,
            payload={"agent_id": runner_id, "status": result["status"],
                     "activity": "runner results collected",
                     "artifact_count": len(saved)},
            evidence_refs=["sha256:" + result["receipt_sha256"]],
        )
        self.emit_event(
            kind="agent.status", run_id=job_id, task_id=task_id,
            payload={"agent_id": runner_id, "role": "Avrea runner",
                     "status": "completed", "activity": "results collected",
                     "job_id": job_id},
        )
        return result


def _canonical(value: Any) -> str:
    import json
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


__all__ = ["AvreaAdapter"]
