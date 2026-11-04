"""Typed MCFC workload admission and expiring execution leases.

The lease book is an in-process reference implementation. Capacity values must
come from an explicit measured snapshot; unknown GPU capacity remains unknown.
Leases authorize bounded execution only and never authorize qualification,
promotion, repository mutation, or deployment.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from threading import RLock
from typing import Any, Callable
from uuid import uuid4

from merlin.telemetry import normalize_event

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class LeaseError(ValueError):
    """A workload cannot be admitted under the current MCFC contract."""


def _integer(value: Any, name: str, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _datetime(value: str | datetime, name: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    else:
        raise ValueError(f"{name} must be an ISO-8601 timestamp")
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return result.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResourceRequest:
    cpu_cores: int
    memory_bytes: int
    gpu_count: int = 0
    gpu_memory_bytes: int = 0

    def __post_init__(self):
        _integer(self.cpu_cores, "cpu_cores", 1)
        _integer(self.memory_bytes, "memory_bytes", 1)
        _integer(self.gpu_count, "gpu_count")
        _integer(self.gpu_memory_bytes, "gpu_memory_bytes")
        if self.gpu_count == 0 and self.gpu_memory_bytes != 0:
            raise ValueError("gpu_memory_bytes requires gpu_count > 0")


@dataclass(frozen=True)
class WorkloadRequest:
    workload_id: str
    capability: str
    resources: ResourceRequest
    max_wall_seconds: int
    compute_budget_units: int
    priority: int = 0

    def __post_init__(self):
        if not self.workload_id.strip() or len(self.workload_id) > 128:
            raise ValueError("workload_id must be 1 to 128 characters")
        if not self.capability.strip() or len(self.capability) > 160:
            raise ValueError("capability must be 1 to 160 characters")
        if not isinstance(self.resources, ResourceRequest):
            raise ValueError("resources must be a ResourceRequest")
        _integer(self.max_wall_seconds, "max_wall_seconds", 1)
        _integer(self.compute_budget_units, "compute_budget_units", 1)
        _integer(self.priority, "priority")


@dataclass(frozen=True)
class CapacitySnapshot:
    cpu_cores: int
    memory_bytes: int
    gpu_count: int | None
    gpu_memory_bytes: int | None
    compute_budget_units: int | None
    observed_at: str
    source: str
    evidence_sha256: str

    def __post_init__(self):
        _integer(self.cpu_cores, "capacity.cpu_cores", 0)
        _integer(self.memory_bytes, "capacity.memory_bytes", 0)
        if self.gpu_count is not None:
            _integer(self.gpu_count, "capacity.gpu_count")
        if self.gpu_memory_bytes is not None:
            _integer(self.gpu_memory_bytes, "capacity.gpu_memory_bytes")
        if self.compute_budget_units is not None:
            _integer(self.compute_budget_units, "capacity.compute_budget_units", 0)
        _datetime(self.observed_at, "capacity.observed_at")
        if not self.source.strip():
            raise ValueError("capacity.source must identify the measurement source")
        if not _SHA256.fullmatch(self.evidence_sha256):
            raise ValueError("capacity.evidence_sha256 must be lowercase SHA-256")


@dataclass(frozen=True)
class ExecutionLease:
    lease_id: str
    workload_id: str
    capability: str
    resources: ResourceRequest
    issued_at: str
    deadline_at: str
    expires_at: str
    max_wall_seconds: int
    compute_budget_units: int
    capacity_evidence_sha256: str
    authority: str = "execution_only"
    promotion_authority: bool = False
    status: str = "active"


def cad_wire_route_request(
    workload_id: str,
    *,
    estimated_memory_bytes: int,
    max_wall_seconds: int,
    compute_budget_units: int,
    priority: int = 0,
) -> WorkloadRequest:
    """Build a CPU-only MCFC request; memory/time estimates must be supplied."""
    return WorkloadRequest(
        workload_id=workload_id,
        capability="cad.wire_route_proposal",
        resources=ResourceRequest(cpu_cores=1, memory_bytes=estimated_memory_bytes),
        max_wall_seconds=max_wall_seconds,
        compute_budget_units=compute_budget_units,
        priority=priority,
    )


class LeaseBook:
    """Thread-safe in-process admission book with explicit resource reservations."""

    def __init__(
        self,
        capacity: CapacitySnapshot,
        *,
        max_snapshot_age_seconds: int = 60,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ):
        if not isinstance(capacity, CapacitySnapshot):
            raise ValueError("capacity must be a CapacitySnapshot")
        _integer(max_snapshot_age_seconds, "max_snapshot_age_seconds", 1)
        self.capacity = capacity
        self.max_snapshot_age_seconds = max_snapshot_age_seconds
        self.event_sink = event_sink
        self.telemetry_errors: list[str] = []
        self._leases: dict[str, ExecutionLease] = {}
        self._by_workload: dict[str, tuple[str, str]] = {}
        self._lock = RLock()

    def _emit(self, event_name: str, lease: ExecutionLease, now: datetime) -> None:
        if self.event_sink is None:
            return
        event = normalize_event({
            "event_id": f"{lease.lease_id}:{event_name}",
            "source": "runtime",
            "kind": "resource.sample",
            "timestamp": _iso(now),
            "run_id": lease.lease_id,
            "task_id": lease.workload_id,
            "payload": {
                "component": "mcfc_lease_book",
                "event": event_name,
                "capability": lease.capability,
                "cpu_cores_reserved": lease.resources.cpu_cores,
                "memory_bytes_reserved": lease.resources.memory_bytes,
                "gpu_count_reserved": lease.resources.gpu_count,
                "gpu_memory_bytes_reserved": lease.resources.gpu_memory_bytes,
                "compute_budget_units_reserved": lease.compute_budget_units,
                "lease_status": lease.status,
                "promotion_authority": False,
            },
        })
        try:
            self.event_sink(event)
        except Exception as exc:
            # Telemetry failure must not silently revoke or duplicate a reservation.
            self.telemetry_errors.append(type(exc).__name__)

    def _expire_locked(self, now: datetime) -> list[ExecutionLease]:
        expired = []
        for lease_id, lease in tuple(self._leases.items()):
            if lease.status != "active":
                continue
            if now >= _datetime(lease.deadline_at, "lease.deadline_at") or now >= _datetime(lease.expires_at, "lease.expires_at"):
                updated = replace(lease, status="expired")
                self._leases[lease_id] = updated
                expired.append(updated)
                self._emit("lease.expired", updated, now)
        return expired

    def expire(self, now: str | datetime) -> tuple[ExecutionLease, ...]:
        current = _datetime(now, "now")
        with self._lock:
            return tuple(self._expire_locked(current))

    def _reserved(self, now: datetime) -> ResourceRequest:
        self._expire_locked(now)
        active = [lease for lease in self._leases.values() if lease.status == "active"]
        return ResourceRequest(
            cpu_cores=sum(x.resources.cpu_cores for x in active),
            memory_bytes=max(1, sum(x.resources.memory_bytes for x in active)),
            gpu_count=sum(x.resources.gpu_count for x in active),
            gpu_memory_bytes=sum(x.resources.gpu_memory_bytes for x in active),
        ) if active else ResourceRequest(cpu_cores=1, memory_bytes=1)

    def grant(
        self,
        request: WorkloadRequest,
        *,
        now: str | datetime,
        ttl_seconds: int,
    ) -> ExecutionLease:
        if not isinstance(request, WorkloadRequest):
            raise ValueError("request must be a WorkloadRequest")
        _integer(ttl_seconds, "ttl_seconds", 1)
        if ttl_seconds < request.max_wall_seconds:
            raise ValueError("lease TTL cannot be shorter than the workload wall-time limit")
        current = _datetime(now, "now")
        observed = _datetime(self.capacity.observed_at, "capacity.observed_at")
        age = (current - observed).total_seconds()
        if age < 0 or age > self.max_snapshot_age_seconds:
            raise LeaseError("capacity snapshot is stale or from the future")
        with self._lock:
            self._expire_locked(current)
            fingerprint = _fingerprint(asdict(request))
            previous = self._by_workload.get(request.workload_id)
            if previous is not None:
                old_fingerprint, old_lease_id = previous
                if old_fingerprint != fingerprint:
                    raise LeaseError("workload_id was reused with different requirements")
                old_lease = self._leases[old_lease_id]
                if old_lease.status == "active":
                    return old_lease
                raise LeaseError("workload_id is already closed; submit a new workload_id")

            need = request.resources
            cap = self.capacity
            if need.cpu_cores > cap.cpu_cores:
                raise LeaseError("insufficient CPU capacity")
            if need.memory_bytes > cap.memory_bytes:
                raise LeaseError("insufficient memory capacity")
            if need.gpu_count:
                if cap.gpu_count is None or cap.gpu_memory_bytes is None:
                    raise LeaseError("GPU capacity is unknown")
                if need.gpu_count > cap.gpu_count:
                    raise LeaseError("insufficient GPU count")
                if need.gpu_memory_bytes > cap.gpu_memory_bytes:
                    raise LeaseError("insufficient GPU memory")

            active = [x for x in self._leases.values() if x.status == "active"]
            used_cpu = sum(x.resources.cpu_cores for x in active)
            used_memory = sum(x.resources.memory_bytes for x in active)
            used_gpu = sum(x.resources.gpu_count for x in active)
            used_gpu_memory = sum(x.resources.gpu_memory_bytes for x in active)
            used_budget = sum(x.compute_budget_units for x in active)
            if used_cpu + need.cpu_cores > cap.cpu_cores:
                raise LeaseError("CPU reservation budget exhausted")
            if used_memory + need.memory_bytes > cap.memory_bytes:
                raise LeaseError("memory reservation budget exhausted")
            if need.gpu_count and (used_gpu + need.gpu_count > cap.gpu_count or
                                   used_gpu_memory + need.gpu_memory_bytes > cap.gpu_memory_bytes):
                raise LeaseError("GPU reservation budget exhausted")
            if cap.compute_budget_units is None:
                raise LeaseError("compute budget capacity is unknown")
            if used_budget + request.compute_budget_units > cap.compute_budget_units:
                raise LeaseError("compute budget exhausted")

            lease = ExecutionLease(
                lease_id=str(uuid4()),
                workload_id=request.workload_id,
                capability=request.capability,
                resources=request.resources,
                issued_at=_iso(current),
                deadline_at=_iso(current + timedelta(seconds=request.max_wall_seconds)),
                expires_at=_iso(current + timedelta(seconds=ttl_seconds)),
                max_wall_seconds=request.max_wall_seconds,
                compute_budget_units=request.compute_budget_units,
                capacity_evidence_sha256=cap.evidence_sha256,
            )
            self._leases[lease.lease_id] = lease
            self._by_workload[request.workload_id] = (fingerprint, lease.lease_id)
            self._emit("lease.granted", lease, current)
            return lease

    def validate_start(self, lease_id: str, *, now: str | datetime) -> bool:
        current = _datetime(now, "now")
        with self._lock:
            self._expire_locked(current)
            lease = self._leases.get(lease_id)
            return bool(
                lease and lease.status == "active"
                and current < _datetime(lease.deadline_at, "lease.deadline_at")
                and current < _datetime(lease.expires_at, "lease.expires_at")
            )

    def complete(self, lease_id: str, *, now: str | datetime) -> ExecutionLease:
        current = _datetime(now, "now")
        with self._lock:
            self._expire_locked(current)
            lease = self._leases.get(lease_id)
            if lease is None:
                raise KeyError(lease_id)
            if lease.status != "active":
                raise LeaseError(f"cannot complete lease in state {lease.status}")
            updated = replace(lease, status="completed")
            self._leases[lease_id] = updated
            self._emit("lease.completed", updated, current)
            return updated

    def revoke(self, lease_id: str, *, now: str | datetime) -> ExecutionLease:
        current = _datetime(now, "now")
        with self._lock:
            self._expire_locked(current)
            lease = self._leases.get(lease_id)
            if lease is None:
                raise KeyError(lease_id)
            if lease.status != "active":
                raise LeaseError(f"cannot revoke lease in state {lease.status}")
            updated = replace(lease, status="revoked")
            self._leases[lease_id] = updated
            self._emit("lease.revoked", updated, current)
            return updated

    def get(self, lease_id: str) -> ExecutionLease:
        with self._lock:
            if lease_id not in self._leases:
                raise KeyError(lease_id)
            return self._leases[lease_id]

    def snapshot(self, *, now: str | datetime) -> dict[str, Any]:
        current = _datetime(now, "now")
        with self._lock:
            self._expire_locked(current)
            active = [x for x in self._leases.values() if x.status == "active"]
            used = {
                "cpu_cores": sum(x.resources.cpu_cores for x in active),
                "memory_bytes": sum(x.resources.memory_bytes for x in active),
                "gpu_count": sum(x.resources.gpu_count for x in active),
                "gpu_memory_bytes": sum(x.resources.gpu_memory_bytes for x in active),
                "compute_budget_units": sum(x.compute_budget_units for x in active),
            }
            cap = self.capacity
            return {
                "schema": "mcfc-capacity-snapshot/0.1",
                "source": cap.source,
                "capacity_evidence_sha256": cap.evidence_sha256,
                "capacity": {
                    "cpu_cores": cap.cpu_cores, "memory_bytes": cap.memory_bytes,
                    "gpu_count": cap.gpu_count, "gpu_memory_bytes": cap.gpu_memory_bytes,
                    "compute_budget_units": cap.compute_budget_units,
                },
                "reserved": used,
                "available": {
                    "cpu_cores": cap.cpu_cores - used["cpu_cores"],
                    "memory_bytes": cap.memory_bytes - used["memory_bytes"],
                    "gpu_count": None if cap.gpu_count is None else cap.gpu_count - used["gpu_count"],
                    "gpu_memory_bytes": None if cap.gpu_memory_bytes is None else cap.gpu_memory_bytes - used["gpu_memory_bytes"],
                    "compute_budget_units": None if cap.compute_budget_units is None else cap.compute_budget_units - used["compute_budget_units"],
                },
                "active_lease_count": len(active),
                "promotion_authority": False,
            }


__all__ = [
    "CapacitySnapshot", "ExecutionLease", "LeaseBook", "LeaseError",
    "ResourceRequest", "WorkloadRequest", "cad_wire_route_request",
]
