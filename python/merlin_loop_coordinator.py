"""Bounded research/plan/subloop coordinator; pure state transitions, no execution authority."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

STATES = frozenset({"pending", "running", "passed", "failed", "blocked"})
TERMINAL = frozenset({"passed", "failed", "blocked"})


@dataclass
class Loop:
    identifier: str
    kind: str
    parent: str | None = None
    dependencies: Tuple[str, ...] = ()
    budget: int = 1
    state: str = "pending"
    attempts: int = 0
    evidence: Tuple[str, ...] = ()


@dataclass
class LoopCoordinator:
    """In-memory deterministic scheduler. Caller persists snapshots in canonical ledger."""
    max_depth: int = 3
    loops: Dict[str, Loop] = field(default_factory=dict)

    def add(self, loop: Loop) -> None:
        if not isinstance(loop.identifier, str) or not loop.identifier or loop.identifier in self.loops:
            raise ValueError("loop identifier must be new and nonempty")
        if loop.kind not in {"plan", "research", "subloop"}:
            raise ValueError("invalid loop kind")
        if type(loop.budget) is not int or loop.budget < 1 or loop.budget > 100:
            raise ValueError("invalid attempt budget")
        if loop.state != "pending" or loop.attempts or loop.evidence:
            raise ValueError("new loops must start pending")
        if loop.parent is not None:
            if loop.parent not in self.loops:
                raise ValueError("unknown parent")
            if self.loops[loop.parent].state in TERMINAL:
                raise ValueError("cannot add child to terminal parent")
            if self.depth(loop.parent) >= self.max_depth:
                raise ValueError("maximum nesting exceeded")
        if loop.identifier in loop.dependencies or len(set(loop.dependencies)) != len(loop.dependencies):
            raise ValueError("invalid dependencies")
        if any(dep not in self.loops for dep in loop.dependencies):
            raise ValueError("unknown dependency")
        self.loops[loop.identifier] = loop

    def depth(self, identifier: str) -> int:
        depth = 0
        current = self.loops[identifier]
        while current.parent is not None:
            depth += 1
            current = self.loops[current.parent]
        return depth

    def start(self, identifier: str) -> None:
        loop = self.loops[identifier]
        if loop.state != "pending" or loop.attempts >= loop.budget:
            raise ValueError("loop cannot start")
        if any(self.loops[dep].state != "passed" for dep in loop.dependencies):
            raise ValueError("dependencies not passed")
        if loop.parent is not None and self.loops[loop.parent].state != "running":
            raise ValueError("parent must be running")
        loop.state = "running"
        loop.attempts += 1

    def finish(self, identifier: str, *, passed: bool, evidence: str) -> None:
        loop = self.loops[identifier]
        if loop.state != "running" or not isinstance(evidence, str) or not evidence.strip():
            raise ValueError("running loop requires evidence")
        if any(child.parent == identifier and child.state == "running"
               for child in self.loops.values()):
            raise ValueError("active child prevents parent completion")
        if passed and any(child.parent == identifier and child.state != "passed"
                          for child in self.loops.values()):
            raise ValueError("unfinished or failed children prevent success")
        loop.evidence += (evidence,)
        loop.state = "passed" if passed else "failed"

    def retry(self, identifier: str) -> None:
        loop = self.loops[identifier]
        if loop.state != "failed" or loop.attempts >= loop.budget:
            raise ValueError("retry not allowed")
        if any(child.parent == identifier and child.state == "running"
               for child in self.loops.values()):
            raise ValueError("active child prevents retry")
        loop.state = "pending"

    def block(self, identifier: str, evidence: str) -> None:
        loop = self.loops[identifier]
        if loop.state not in {"pending", "failed"} or not isinstance(evidence, str) or not evidence.strip():
            raise ValueError("cannot block without reason")
        loop.evidence += (evidence,)
        loop.state = "blocked"

    def snapshot(self) -> dict:
        return {name: {"kind": x.kind, "parent": x.parent, "dependencies": list(x.dependencies),
                       "budget": x.budget, "state": x.state, "attempts": x.attempts,
                       "evidence": list(x.evidence)}
                for name, x in sorted(self.loops.items())}

    def next_steps(self) -> tuple[str, ...]:
        """Rank eligible pending work deterministically; no implicit execution.

        A running parent may schedule its pending children. A running leaf must
        finish or be interrupted explicitly before more work is started.
        """
        ready = []
        for identifier, loop in self.loops.items():
            if loop.state != "pending" or loop.attempts >= loop.budget:
                continue
            if any(self.loops[d].state != "passed" for d in loop.dependencies):
                continue
            if loop.parent is not None and self.loops[loop.parent].state != "running":
                continue
            ready.append(identifier)
        return tuple(sorted(ready, key=lambda name: (self.depth(name), name)))

    def handoff(self) -> dict:
        """Explain resumable work and blockers without granting execution rights."""
        ready = self.next_steps()
        blockers = {}
        for name, loop in sorted(self.loops.items()):
            if loop.state == "pending" and name not in ready:
                blockers[name] = {
                    "dependencies": [d for d in loop.dependencies
                                     if self.loops[d].state != "passed"],
                    "parent_state": self.loops[loop.parent].state
                                    if loop.parent is not None else None,
                }
        return {"next_steps": list(ready), "blocked_pending": blockers,
                "running": sorted(name for name, x in self.loops.items()
                                  if x.state == "running"),
                "failed": sorted(name for name, x in self.loops.items()
                                 if x.state == "failed"),
                "snapshot": self.snapshot()}

    @classmethod
    def restore(cls, snapshot: dict, *, max_depth: int = 3) -> "LoopCoordinator":
        """Validate a snapshot before restoring; interrupted work needs review.

        No running operation is silently resumed or marked successful.
        """
        if not isinstance(snapshot, dict):
            raise ValueError("snapshot must be an object")
        restored = cls(max_depth=max_depth)
        remaining = dict(snapshot)
        while remaining:
            progressed = False
            for name, record in list(remaining.items()):
                if not isinstance(record, dict):
                    raise ValueError("invalid loop record")
                parent = record.get("parent")
                deps = record.get("dependencies", [])
                if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
                    raise ValueError("invalid dependencies")
                if (parent is not None and parent not in restored.loops) or any(
                        dep not in restored.loops for dep in deps):
                    continue
                state = record.get("state")
                attempts = record.get("attempts")
                budget = record.get("budget")
                evidence = record.get("evidence", [])
                if (state not in STATES or type(attempts) is not int or
                        type(budget) is not int or not 0 <= attempts <= budget or
                        not isinstance(evidence, list) or
                        any(not isinstance(e, str) or not e.strip() for e in evidence)):
                    raise ValueError("invalid loop state")
                loop = Loop(name, record.get("kind"), parent, tuple(deps), budget)
                restored.add(loop)
                if state == "running":
                    loop.state = "blocked"
                    loop.evidence = tuple(evidence) + ("interrupted:requires-review",)
                else:
                    loop.state = state
                    loop.evidence = tuple(evidence)
                loop.attempts = attempts
                if state == "passed" and attempts == 0:
                    raise ValueError("passed loop without attempt")
                del remaining[name]
                progressed = True
            if not progressed:
                raise ValueError("snapshot has unresolved references or cycles")
        return restored

    def to_json(self) -> str:
        """Serialize the current scheduler state; caller owns durable storage."""
        import json
        return json.dumps({"schema": 1, "max_depth": self.max_depth,
                           "loops": self.snapshot()}, sort_keys=True)

    @classmethod
    def from_json(cls, serialized: str) -> "LoopCoordinator":
        """Restore validated state; running work becomes blocked for review."""
        import json
        obj = json.loads(serialized)
        if not isinstance(obj, dict) or obj.get("schema") != 1:
            raise ValueError("unsupported scheduler schema")
        depth = obj.get("max_depth")
        if type(depth) is not int or not 0 <= depth <= 100:
            raise ValueError("invalid maximum depth")
        return cls.restore(obj.get("loops"), max_depth=depth)
