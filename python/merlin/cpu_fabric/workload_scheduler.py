"""Priority/FIFO MCFC workload queue backed by bounded execution leases.

This scheduler performs admission and reservation only. It does not start worker
processes, preempt running work, or persist queue state across restarts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from threading import RLock
from typing import Any

from merlin.cpu_fabric.leases import LeaseBook, LeaseError, WorkloadRequest


@dataclass(frozen=True)
class _Queued:
    request: WorkloadRequest
    sequence: int


class WorkloadScheduler:
    """Stable priority queue with first-fit admission against an MCFC LeaseBook."""

    def __init__(self, lease_book: LeaseBook):
        if not isinstance(lease_book, LeaseBook):
            raise ValueError("lease_book must be a LeaseBook")
        self.lease_book = lease_book
        self._pending: dict[str, _Queued] = {}
        self._submitted: set[str] = set()
        self._sequence = 0
        self._lock = RLock()

    def submit(self, request: WorkloadRequest) -> dict[str, Any]:
        if not isinstance(request, WorkloadRequest):
            raise ValueError("request must be a WorkloadRequest")
        with self._lock:
            if request.workload_id in self._submitted:
                raise ValueError("workload_id has already been submitted to this scheduler")
            self._sequence += 1
            self._submitted.add(request.workload_id)
            self._pending[request.workload_id] = _Queued(request, self._sequence)
            return {
                "workload_id": request.workload_id,
                "queue_position": len(self._ordered()),
                "priority": request.priority,
                "status": "queued",
            }

    def _ordered(self) -> list[_Queued]:
        return sorted(
            self._pending.values(),
            key=lambda item: (-item.request.priority, item.sequence, item.request.workload_id),
        )

    def cancel(self, workload_id: str) -> bool:
        with self._lock:
            return self._pending.pop(workload_id, None) is not None

    def pending(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(item.request.workload_id for item in self._ordered())

    def dispatch(
        self,
        *,
        now: str | datetime,
        ttl_seconds: int,
        max_grants: int | None = None,
    ) -> dict[str, Any]:
        """Grant leases in priority/FIFO order; skip temporarily unfit requests."""
        if max_grants is not None and (
            isinstance(max_grants, bool) or not isinstance(max_grants, int) or max_grants < 1
        ):
            raise ValueError("max_grants must be a positive integer or None")
        with self._lock:
            granted = []
            blocked: dict[str, str] = {}
            for item in self._ordered():
                if max_grants is not None and len(granted) >= max_grants:
                    break
                request = item.request
                try:
                    lease = self.lease_book.grant(request, now=now, ttl_seconds=ttl_seconds)
                except LeaseError as exc:
                    blocked[request.workload_id] = str(exc)
                    continue
                del self._pending[request.workload_id]
                granted.append(lease)
            return {
                "schema": "mcfc-dispatch-result/0.1",
                "granted": [asdict(lease) for lease in granted],
                "blocked": blocked,
                "pending": list(self.pending()),
                "priority_policy": "descending_priority_fifo_ties",
                "admission_policy": "first_fit_skip_blocked",
                "promotion_authority": False,
            }


__all__ = ["WorkloadScheduler"]
