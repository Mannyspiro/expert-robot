"""Budgeted, resumable scientific research sub-loops.

An experiment and an independent assessor are host-provided callables. This
module does not execute model weights or become a daemon; it provides a durable
state machine that a separately approved process may repeatedly resume.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Callable

SCHEMA = "merlin-research-subloops/1"
_ID = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
MAX_TASKS = 64
MAX_STEPS = 32
MAX_DEPTH = 4
MAX_FANOUT = 4
MAX_CHECKPOINT_BYTES = 524288


def _json(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(data.encode()) > MAX_CHECKPOINT_BYTES:
        raise ValueError("bounded research record exceeded maximum size")
    return data


def _hash(value):
    return sha256(_json(value).encode()).hexdigest()


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise ValueError(field + " needs bounded non-empty text")
    return value


@dataclass(frozen=True)
class Question:
    task_id: str
    hypothesis: str
    baseline: str
    falsifier: str
    independent_check: str
    parent_id: str | None = None
    depth: int = 0

    def __post_init__(self):
        if not isinstance(self.task_id, str) or _ID.fullmatch(self.task_id) is None:
            raise ValueError("bounded task identity required")
        for name in ("hypothesis", "baseline", "falsifier", "independent_check"):
            _text(getattr(self, name), name)
        if self.parent_id is not None and (not isinstance(self.parent_id, str)
                                           or not _ID.fullmatch(self.parent_id)):
            raise ValueError("invalid parent identity")
        if type(self.depth) is not int or not 0 <= self.depth <= MAX_DEPTH:
            raise ValueError("invalid research depth")


class ResearchSubloops:
    def __init__(self, max_steps=12, max_tasks=32, max_depth=3):
        for value, maximum in ((max_steps, MAX_STEPS), (max_tasks, MAX_TASKS),
                               (max_depth, MAX_DEPTH)):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError("invalid bounded subloop budget")
        self.max_steps = max_steps
        self.max_tasks = max_tasks
        self.max_depth = max_depth
        self.tasks: dict[str, Question] = {}
        self.queue: list[str] = []
        self.receipts: list[dict] = []

    def add(self, task: Question):
        if len(self.tasks) >= self.max_tasks or task.task_id in self.tasks:
            raise ValueError("bounded or duplicate task")
        if task.parent_id is None:
            if task.depth != 0:
                raise ValueError("root must have depth zero")
        else:
            parent = self.tasks.get(task.parent_id)
            if parent is None or task.depth != parent.depth + 1:
                raise ValueError("child must cite existing exact parent/depth")
        if task.depth > self.max_depth:
            raise ValueError("configured depth exceeded")
        self.tasks[task.task_id] = task
        self.queue.append(task.task_id)

    def step(self, experiment: Callable[[Question], dict],
             independent_verify: Callable[[Question, dict], dict]):
        """One bounded step; callbacks must be trusted, never model-generated.

        Experimental success is not proof of novelty or physical equivalence.
        Children are enqueued only after an explicit independent check.
        """
        if not self.queue or len(self.receipts) >= self.max_steps:
            return None
        task_id = self.queue.pop(0)
        task = self.tasks[task_id]
        receipt = {"task_id": task_id, "parent_id": task.parent_id,
                   "children_admitted": [], "novelty_proven": False,
                   "physical_gain_proven": False, "model_weights_changed": False,
                   "production_qualified": False}
        try:
            raw = experiment(task)
            if not isinstance(raw, dict) or set(raw) != {"observation", "children"}:
                raise ValueError("experiment returns observation and children only")
            obs, children = raw["observation"], raw["children"]
            if len(_json(obs).encode("utf-8")) > 8192:
                raise ValueError("bounded observation exceeds 8 KiB per task")
            if not isinstance(obs, dict) or not isinstance(children, list) or len(children) > MAX_FANOUT:
                raise ValueError("bad observation or child fanout")
            assessment = independent_verify(task, obs)
            if (not isinstance(assessment, dict) or set(assessment) != {"accepted", "checker", "reason"}
                    or type(assessment["accepted"]) is not bool):
                raise ValueError("checker must return Boolean accepted, checker and reason")
            _text(assessment["checker"], "checker")
            _text(assessment["reason"], "reason")
            receipt["observation"] = obs
            receipt["observation_sha256"] = _hash(obs)
            receipt["verification"] = assessment
            receipt["status"] = "checked" if assessment["accepted"] else "rejected"
            if assessment["accepted"]:
                if task.depth >= self.max_depth and children:
                    raise ValueError("max depth reached")
                if len(self.tasks) + len(children) > self.max_tasks:
                    raise ValueError("task capacity exceeded")
                prepared = []
                for item in children:
                    if not isinstance(item, dict) or set(item) != {
                        "task_id", "hypothesis", "baseline", "falsifier", "independent_check"
                    }:
                        raise ValueError("child protocol incomplete")
                    child = Question(**item, parent_id=task_id, depth=task.depth + 1)
                    if child.task_id in self.tasks or child.task_id in {x.task_id for x in prepared}:
                        raise ValueError("duplicate child task")
                    prepared.append(child)
                for child in prepared:
                    self.add(child)
                receipt["children_admitted"] = [x.task_id for x in prepared]
        except Exception as exc:
            receipt["status"] = "error"
            receipt["error_type"] = type(exc).__name__
            receipt.pop("verification", None)
            receipt["children_admitted"] = []
        receipt["receipt_sha256"] = _hash(receipt)
        self.receipts.append(receipt)
        return receipt

    def summary(self):
        return {
            "schema": SCHEMA, "steps_used": len(self.receipts),
            "steps_limit": self.max_steps, "tasks": len(self.tasks),
            "queued": list(self.queue),
            "status": "paused_budget" if self.queue and len(self.receipts) == self.max_steps
                      else "ready" if self.queue else "ended_with_unverified_claims",
            "background_worker_running": False, "auto_merge_or_deploy": False,
            "proof_of_novelty": False, "production_qualified": False,
        }

    def snapshot(self):
        body = {
            "schema": SCHEMA,
            "limits": {"max_steps": self.max_steps, "max_tasks": self.max_tasks,
                       "max_depth": self.max_depth},
            "tasks": [asdict(q) for q in self.tasks.values()],
            "queue": list(self.queue),
            "receipts": list(self.receipts),
        }
        return {**body, "sha256": _hash(body)}

    @classmethod
    def restore(cls, saved):
        if not isinstance(saved, dict) or set(saved) != {
            "schema", "limits", "tasks", "queue", "receipts", "sha256"
        } or saved.get("schema") != SCHEMA:
            raise ValueError("checkpoint schema mismatch")
        body = {k: v for k, v in saved.items() if k != "sha256"}
        if _hash(body) != saved["sha256"]:
            raise ValueError("checkpoint integrity mismatch")
        x = cls(**saved["limits"])
        if not isinstance(saved["tasks"], list) or len(saved["tasks"]) > x.max_tasks:
            raise ValueError("invalid task inventory")
        for raw in saved["tasks"]:
            if not isinstance(raw, dict):
                raise ValueError("untyped task")
            x.add(Question(**raw))
        q, receipts = saved["queue"], saved["receipts"]
        if (not isinstance(q, list) or len(q) != len(set(q)) or not set(q).issubset(x.tasks)
                or not isinstance(receipts, list) or len(receipts) > x.max_steps):
            raise ValueError("bad queue or receipt budget")
        processed = []
        for rec in receipts:
            if not isinstance(rec, dict) or rec.get("receipt_sha256") != _hash({
                k: v for k, v in rec.items() if k != "receipt_sha256"}):
                raise ValueError("corrupt receipt")
            if rec.get("status") in ("checked", "rejected"):
                if (not isinstance(rec.get("observation"), dict)
                        or rec.get("observation_sha256") != _hash(rec["observation"])):
                    raise ValueError("observation bytes do not match scientific receipt")
                ver = rec.get("verification")
                if (not isinstance(ver, dict)
                        or set(ver) != {"accepted", "checker", "reason"}
                        or type(ver["accepted"]) is not bool
                        or (rec["status"] == "checked") != ver["accepted"]):
                    raise ValueError("checker status disagrees with research receipt")
            processed.append(rec["task_id"])
        if len(set(processed)) != len(processed) or set(processed) != set(x.tasks) - set(q):
            raise ValueError("incomplete or duplicated checkpoint history")
        x.queue = list(q)
        x.receipts = list(receipts)
        return x
