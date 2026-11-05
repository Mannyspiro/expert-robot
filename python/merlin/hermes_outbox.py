"""Hermes-facing outbox consumer protocol.

The consumer receives normalized Merlin events through an injected handler. It does
not launch shell commands, grant tool permissions, or alter Hermes authority.
"""
from __future__ import annotations
from collections.abc import Callable, Mapping
from typing import Any

from merlin.event_outbox import MerlinEventOutbox


class HermesOutboxConsumer:
    """At-least-once event consumer with explicit result acknowledgement."""
    def __init__(self, outbox: MerlinEventOutbox):
        if not isinstance(outbox, MerlinEventOutbox):
            raise ValueError("outbox must be a MerlinEventOutbox")
        self.outbox = outbox

    def consume_one(self, worker_id: str, handler: Callable[[dict[str, Any]], Mapping[str, Any]],
                    *, lease_seconds: float = 60, retry_delay_seconds: float = 5,
                    max_attempts: int = 5,
                    topics: tuple[str, ...] = ("merlin.hermes.task",),
                    now: float | None = None) -> dict[str, Any] | None:
        lease = self.outbox.claim_next(worker_id, lease_seconds=lease_seconds,
                                       topics=topics, now=now)
        if lease is None:
            return None
        event = {key: value for key, value in lease.items() if key != "lease_token"}
        try:
            result = handler(event)
            if not isinstance(result, Mapping):
                raise TypeError("Hermes handler must return a mapping result")
            acknowledged = self.outbox.acknowledge(
                lease["event_id"], worker_id, lease["lease_token"],
                result=dict(result), now=now,
            )
            return {"event_id": lease["event_id"], "state": "acknowledged",
                    "result": acknowledged.get("result")}
        except Exception as exc:
            retried = self.outbox.retry(
                lease["event_id"], worker_id, lease["lease_token"], str(exc),
                delay_seconds=retry_delay_seconds, max_attempts=max_attempts, now=now,
            )
            return {"event_id": lease["event_id"], "state": retried["state"],
                    "error": str(exc)[:2000]}
