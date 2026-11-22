"""Durable Merlin loop snapshots in the existing hash-linked evidence ledger.

A restored running loop is blocked, never silently resumed. This adapter does
not execute tasks, grant authority, or independently validate evidence locators.
"""
from __future__ import annotations

from merlin_loop_coordinator import LoopCoordinator


def checkpoint(coordinator: LoopCoordinator, ledger, *, plan_id: str) -> dict:
    if not isinstance(plan_id, str) or not plan_id or len(plan_id) > 128:
        raise ValueError("invalid plan identity")
    ledger.verify()
    return ledger.append({
        "subsystem": "merlin_loop_coordinator",
        "state": "checkpoint",
        "schema": "merlin-loop-checkpoint/1",
        "plan_id": plan_id,
        "max_depth": coordinator.max_depth,
        "loops": coordinator.snapshot(),
    })


def restore(ledger, *, plan_id: str) -> LoopCoordinator:
    if not isinstance(plan_id, str) or not plan_id or len(plan_id) > 128:
        raise ValueError("invalid plan identity")
    ledger.verify()
    latest = None
    if ledger.path.exists():
        for line in ledger.path.read_text(encoding="utf-8").splitlines():
            import json
            event = json.loads(line)["event"]
            if (event.get("subsystem") == "merlin_loop_coordinator"
                    and event.get("plan_id") == plan_id
                    and event.get("state") == "checkpoint"):
                if event.get("schema") != "merlin-loop-checkpoint/1":
                    raise ValueError("unknown loop checkpoint schema")
                latest = event
    if latest is None:
        return LoopCoordinator()
    depth = latest.get("max_depth")
    if type(depth) is not int or not 0 <= depth <= 32:
        raise ValueError("invalid stored depth")
    raw = latest.get("loops")
    if not isinstance(raw, dict) or len(raw) > 10000:
        raise ValueError("invalid stored loops")
    # One canonical graph validator for both direct snapshots and hash-linked
    # ledger snapshots: avoid divergent acceptance of impossible successes.
    restored = LoopCoordinator.restore(raw, max_depth=depth)
    for name, source in raw.items():
        if source.get("state") == "running":
            # Retain the prior durable marker for the ledger API's consumers.
            evidence = restored.loops[name].evidence
            if not evidence or evidence[-1] != "interrupted:requires-review":
                raise RuntimeError("interruption marker was not recorded")
            restored.loops[name].evidence = (
                *evidence[:-1], "interrupted_execution_requires_review")
    return restored
