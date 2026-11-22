"""Durable Merlin loop snapshots in the existing hash-linked evidence ledger.

A restored running loop is blocked, never silently resumed. This adapter does
not execute tasks, grant authority, or independently validate evidence locators.
"""
from __future__ import annotations

from merlin_loop_coordinator import Loop, LoopCoordinator


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
    if type(latest.get("max_depth")) is not int or not 0 <= latest["max_depth"] <= 32:
        raise ValueError("invalid stored depth")
    raw = latest.get("loops")
    if not isinstance(raw, dict) or len(raw) > 10000:
        raise ValueError("invalid stored loops")
    c = LoopCoordinator(max_depth=latest["max_depth"])
    # Snapshot insertion order is alphabetical, so resolve parent/dependency DAG.
    pending = dict(raw)
    restored_states = {}
    while pending:
        progressed = False
        for name, data in list(pending.items()):
            if not isinstance(data, dict):
                raise ValueError("invalid stored loop")
            parent = data.get("parent")
            deps = data.get("dependencies")
            if not isinstance(deps, list) or not all(isinstance(x, str) for x in deps):
                raise ValueError("invalid stored dependencies")
            if (parent is not None and parent not in c.loops) or any(x not in c.loops for x in deps):
                continue
            loop = Loop(name, data.get("kind"), parent, tuple(deps), data.get("budget"))
            c.add(loop)
            state, attempts, evidence = data.get("state"), data.get("attempts"), data.get("evidence")
            if state not in {"pending", "running", "passed", "failed", "blocked"}:
                raise ValueError("invalid stored state")
            if type(attempts) is not int or not 0 <= attempts <= loop.budget:
                raise ValueError("invalid stored attempts")
            if not isinstance(evidence, list) or not all(isinstance(x, str) and x for x in evidence):
                raise ValueError("invalid stored evidence")
            if state == "pending" and attempts and not evidence:
                raise ValueError("retried pending loop missing failure evidence")
            if state == "blocked" and not evidence:
                raise ValueError("blocked loop without reason")
            if state == "running" and attempts == 0:
                raise ValueError("running loop without attempt")
            if state in {"passed", "failed"} and (attempts == 0 or not evidence):
                raise ValueError("terminal loop without evidence")
            restored_states[name] = (state, attempts, tuple(evidence))
            del pending[name]
            progressed = True
        if not progressed:
            raise ValueError("cyclic or missing stored loop dependencies")
    # Restore structure first: a running parent may be interrupted and blocked,
    # but its children must still be reconstructed without violating add().
    for name, (state, attempts, evidence) in restored_states.items():
        loop = c.loops[name]
        loop.attempts = attempts
        loop.evidence = evidence
        if state == "running":
            loop.state = "blocked"
            loop.evidence += ("interrupted_execution_requires_review",)
        else:
            loop.state = state
    for loop in c.loops.values():
        if loop.parent is not None and c.loops[loop.parent].state == "passed" and loop.state != "passed":
            raise ValueError("passed parent has incomplete child")
    return c
