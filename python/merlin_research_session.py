"""Durable, bounded, evidence-first Merlin research cycle.

Orchestration only: no model, browser, experiment, or external action execution.
Procedural stage completion NEVER verifies a scientific claim or grants authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from hashlib import sha256
import json
import math
import re
from typing import Any

from merlin.scientific_loop import Observation, Prediction, compare_observation
from merlin_loop_coordinator import Loop, LoopCoordinator
from merlin_loop_persistence import checkpoint, restore

SCHEMA = "merlin-research-session/1"
STAGES = ("observe", "explain", "predict", "experiment", "challenge", "update")
EVIDENCE_CLASSES = frozenset({"observed", "reported", "simulated", "formal"})
SUBSYSTEM = "merlin_research_session"


def _text(value: str, name: str, limit: int = 2000) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} requires bounded nonempty text")


def _refs(values: tuple[str, ...], name: str) -> None:
    if not isinstance(values, tuple) or not 1 <= len(values) <= 32 or len(values) != len(set(values)):
        raise ValueError(f"{name} requires 1-32 distinct references")
    for item in values:
        _text(item, name, 512)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchFrame:
    """Immutable pre-result research question and acceptance conditions."""
    cycle_id: str
    plan_id: str
    plan_version: int
    source_commit: str
    question: str
    metric: str
    unit: str
    baseline_ref: str
    hypotheses: tuple[str, ...]
    predictions: tuple[Prediction, ...]
    falsifier: str
    stopping_rule: str
    acceptance_rule: str
    source_refs: tuple[str, ...]
    unknowns: tuple[str, ...]
    external_spend_ceiling_usd: int = 0

    def validate(self) -> None:
        if not isinstance(self.cycle_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", self.cycle_id):
            raise ValueError("bounded cycle identity required")
        _text(self.plan_id, "plan_id", 128)
        if type(self.plan_version) is not int or self.plan_version < 1:
            raise ValueError("versioned parent plan required")
        if not isinstance(self.source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", self.source_commit):
            raise ValueError("40-character lowercase source commit required")
        for name in ("question", "metric", "unit", "baseline_ref", "falsifier",
                     "stopping_rule", "acceptance_rule"):
            _text(getattr(self, name), name)
        _refs(self.source_refs, "source_refs")
        if (not isinstance(self.unknowns, tuple) or not self.unknowns
                or any(not isinstance(s, str) or not s.strip() for s in self.unknowns)):
            raise ValueError("unknowns must be explicit")
        if (not isinstance(self.hypotheses, tuple) or not 2 <= len(self.hypotheses) <= 8
                or len(self.hypotheses) != len(set(self.hypotheses))):
            raise ValueError("two to eight distinct competing hypotheses required")
        for value in self.hypotheses:
            _text(value, "hypothesis")
        if not isinstance(self.predictions, tuple) or not 1 <= len(self.predictions) <= 8:
            raise ValueError("one to eight preregistered predictions required")
        names = []
        for prediction in self.predictions:
            if not isinstance(prediction, Prediction):
                raise ValueError("typed prediction required")
            _text(prediction.metric, "prediction metric")
            _text(prediction.unit, "prediction unit")
            if (type(prediction.expected) not in (int, float)
                    or type(prediction.tolerance) not in (int, float)
                    or not math.isfinite(prediction.expected)
                    or not math.isfinite(prediction.tolerance)
                    or prediction.tolerance < 0):
                raise ValueError("finite prediction values and nonnegative tolerance required")
            names.append(prediction.metric)
        if len(names) != len(set(names)):
            raise ValueError("duplicate prediction metric")
        if not any(p.metric == self.metric and p.unit == self.unit for p in self.predictions):
            raise ValueError("target metric/unit missing from preregistered predictions")
        if type(self.external_spend_ceiling_usd) is not int or self.external_spend_ceiling_usd != 0:
            raise ValueError("this research lane does not authorize paid external services")

    @property
    def sha256(self) -> str:
        self.validate()
        return _digest(asdict(self))


@dataclass(frozen=True)
class ResearchReceipt:
    """Stage-specific evidence submitted by the caller, not independent proof."""
    stage: str
    artifact_sha256: str
    source_refs: tuple[str, ...]
    tool_name: str
    tool_version: str
    evidence_class: str
    status: str
    interpretation: str
    observation: Observation | None = None
    null_reason: str = ""
    challenge_scope: str = ""
    plan_update_ref: str = ""

    def validate(self) -> None:
        if self.stage not in STAGES or self.status not in {"recorded", "blocked"}:
            raise ValueError("unknown stage or status")
        if not isinstance(self.artifact_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.artifact_sha256):
            raise ValueError("exact SHA-256 receipt artifact identity required")
        _refs(self.source_refs, "receipt sources")
        for name in ("tool_name", "tool_version", "interpretation"):
            _text(getattr(self, name), name)
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise ValueError("unknown evidence class")
        if self.observation is not None:
            if self.stage != "experiment" or not isinstance(self.observation, Observation):
                raise ValueError("typed measurement belongs to experiment stage")
            self.observation.validate()
            if self.observation.artifact_sha256 != self.artifact_sha256:
                raise ValueError("measurement must bind the supplied raw artifact")
            if not set(self.observation.source_refs).issubset(set(self.source_refs)):
                raise ValueError("measurement source is not included in receipt sources")
        if self.status == "recorded" and self.stage == "experiment":
            if (self.observation is None) == (not bool(self.null_reason.strip())):
                raise ValueError("experiment requires measurement XOR explicit null outcome")
        if self.status == "recorded" and self.stage == "challenge":
            _text(self.challenge_scope, "bounded challenge/search scope")
        if self.status == "recorded" and self.stage == "update":
            _text(self.plan_update_ref, "append-only plan revision identity")

    @property
    def sha256(self) -> str:
        self.validate()
        return _digest(asdict(self))


def _new_scheduler(frame: ResearchFrame) -> LoopCoordinator:
    coordinator = LoopCoordinator(max_depth=0)
    preceding = None
    for stage in STAGES:
        identifier = frame.cycle_id + ":" + stage
        coordinator.add(Loop(identifier, "research",
                             dependencies=(preceding,) if preceding else (), budget=1))
        preceding = identifier
    return coordinator


def _entries(ledger) -> list[dict]:
    ledger.verify()
    if not ledger.path.exists():
        return []
    return [json.loads(line) for line in ledger.path.read_text(encoding="utf-8").splitlines()]


def _receipt_from_event(value: Any) -> ResearchReceipt:
    """Revalidate canonical receipt content after restart, not just a hash."""
    expected = {f.name for f in fields(ResearchReceipt)}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("stored stage receipt has unexpected fields")
    raw = dict(value)
    if not isinstance(raw["source_refs"], list):
        raise ValueError("stored receipt sources are malformed")
    raw["source_refs"] = tuple(raw["source_refs"])
    observation = raw.get("observation")
    if observation is not None:
        if (not isinstance(observation, dict)
                or set(observation) != {f.name for f in fields(Observation)}
                or not isinstance(observation["source_refs"], list)):
            raise ValueError("stored measured observation is malformed")
        observed = dict(observation)
        observed["source_refs"] = tuple(observed["source_refs"])
        try:
            raw["observation"] = Observation(**observed)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid stored observation") from exc
    try:
        receipt = ResearchReceipt(**raw)
        receipt.validate()
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("invalid stored research stage receipt") from exc
    return receipt


def _assert_stage_evidence(frame: ResearchFrame, entries: list[dict],
                           coordinator: LoopCoordinator) -> None:
    receipts: dict[str, dict] = {}
    for item in entries:
        event = item["event"]
        if event.get("subsystem") != SUBSYSTEM or event.get("cycle_id") != frame.cycle_id:
            continue
        if event.get("state") != "stage_result":
            continue
        stage = event.get("stage")
        if (stage not in STAGES or stage in receipts or event.get("schema") != SCHEMA
                or event.get("frame_sha256") != frame.sha256
                or event.get("receipt_sha256") != _digest(event.get("receipt"))):
            raise ValueError("conflicting or malformed research-stage evidence")
        receipt = _receipt_from_event(event.get("receipt"))
        if (receipt.stage != stage or receipt.sha256 != event["receipt_sha256"]
                or event.get("independent_verification") is not False
                or event.get("promotion_authority") is not False):
            raise ValueError("stage receipt, authority or event identity differs")
        receipts[stage] = (item, receipt)
    for stage in STAGES:
        loop = coordinator.loops[frame.cycle_id + ":" + stage]
        recorded = receipts.get(stage)
        if loop.state in {"passed", "failed"}:
            if recorded is None or "stage-result:" + recorded[0]["hash"] not in loop.evidence:
                raise ValueError("completed stage has no matching durable stage receipt")
            expected_state = "passed" if recorded[1].status == "recorded" else "failed"
            if loop.state != expected_state:
                raise ValueError("stage completion contradicts its evidence status")
        elif loop.state == "pending" and recorded is not None:
            raise ValueError("pending stage has a previously committed result")
        # A result written just before a crash may accompany a blocked running
        # stage. Preserve this ambiguous state; never infer successful execution.


class ResearchSession:
    """Frozen research frame with a durable six-stage scheduler and receipts."""

    def __init__(self, frame: ResearchFrame, ledger, scheduler: LoopCoordinator):
        self.frame, self.ledger, self.scheduler = frame, ledger, scheduler
        self.plan_key = "research:" + frame.cycle_id
        self.frame_sha256 = frame.sha256

    @classmethod
    def open(cls, frame: ResearchFrame, ledger) -> "ResearchSession":
        frame.validate()
        plan_key = "research:" + frame.cycle_id
        with ledger.recovery_guard("merlin-research-cycle") as owned:
            if not owned:
                raise RuntimeError("another research cycle process owns this ledger")
            entries = _entries(ledger)
            frames = [item["event"] for item in entries
                      if item["event"].get("subsystem") == SUBSYSTEM
                      and item["event"].get("cycle_id") == frame.cycle_id
                      and item["event"].get("state") == "frame"]
            if len(frames) > 1:
                raise ValueError("duplicate pinned research frame")
            if frames:
                first = frames[0]
                if (first.get("schema") != SCHEMA
                        or first.get("frame_sha256") != frame.sha256
                        or _canonical(first.get("frame")) != _canonical(asdict(frame))):
                    raise ValueError("research frame changed since its first commit")
                if not any(item["event"].get("subsystem") == "merlin_loop_coordinator"
                           and item["event"].get("plan_id") == plan_key
                           for item in entries):
                    raise ValueError("frame exists without matching scheduler checkpoint")
                scheduler = restore(ledger, plan_id=plan_key)
            else:
                if any(item["event"].get("subsystem") == "merlin_loop_coordinator"
                       and item["event"].get("plan_id") == plan_key for item in entries):
                    raise ValueError("orphan scheduler history for cycle identity")
                ledger.append({"subsystem": SUBSYSTEM, "schema": SCHEMA,
                               "state": "frame", "cycle_id": frame.cycle_id,
                               "frame_sha256": frame.sha256, "frame": asdict(frame),
                               "independent_verification": False, "promotion_authority": False})
                scheduler = _new_scheduler(frame)
                checkpoint(scheduler, ledger, plan_id=plan_key)
                entries = _entries(ledger)
            expected = _new_scheduler(frame).snapshot()
            current = scheduler.snapshot()
            keys = ("kind", "parent", "dependencies", "budget")
            if set(current) != set(expected) or any(
                    any(current[name][key] != expected[name][key] for key in keys)
                    for name in expected):
                raise ValueError("stored research stage graph changed")
            _assert_stage_evidence(frame, entries, scheduler)
            return cls(frame, ledger, scheduler)

    def next_stage(self) -> str | None:
        next_items = self.scheduler.next_steps()
        if not next_items:
            return None
        if len(next_items) != 1:
            raise RuntimeError("research stage order ambiguous")
        return next_items[0].split(":", 1)[1]

    def status(self) -> dict:
        states = self.scheduler.snapshot()
        return {"schema": SCHEMA, "cycle_id": self.frame.cycle_id,
                "source_commit": self.frame.source_commit,
                "parent_plan": {"id": self.frame.plan_id, "version": self.frame.plan_version},
                "frame_sha256": self.frame_sha256, "next_stage": self.next_stage(),
                "stages": {s: states[self.frame.cycle_id + ":" + s]["state"] for s in STAGES},
                "procedural_record_complete": all(r["state"] == "passed" for r in states.values()),
                "independent_verification": False, "scientific_claim_established": False,
                "promotion_authority": False, "external_spend_allowed": False}

    def record(self, receipt: ResearchReceipt) -> dict:
        receipt.validate()
        with self.ledger.recovery_guard("merlin-research-cycle") as owned:
            if not owned:
                raise RuntimeError("research ledger is busy")
            fresh = ResearchSession.open_unlocked(self.frame, self.ledger)
            if fresh.scheduler.snapshot() != self.scheduler.snapshot():
                raise RuntimeError("research stage has stale or interrupted state")
            if receipt.stage != self.next_stage():
                raise ValueError("research stage is out of order or blocked")
            stage_id = self.frame.cycle_id + ":" + receipt.stage
            if receipt.stage == "experiment" and receipt.observation is not None:
                assessment = compare_observation(receipt.observation, self.frame.predictions)
            elif receipt.stage == "experiment" and receipt.status == "recorded":
                assessment = {"overall": "null_result", "reason": receipt.null_reason}
            else:
                assessment = {"overall": "stage_" + receipt.status}
            self.scheduler.start(stage_id)
            checkpoint(self.scheduler, self.ledger, plan_id=self.plan_key)
            # Explicit intent checkpoint is persisted before committing an outcome.
            entry = self.ledger.append({
                "subsystem": SUBSYSTEM, "schema": SCHEMA, "state": "stage_result",
                "cycle_id": self.frame.cycle_id, "frame_sha256": self.frame_sha256,
                "stage": receipt.stage, "receipt_sha256": receipt.sha256,
                "receipt": asdict(receipt), "assessment": assessment,
                "independent_verification": False, "promotion_authority": False,
            })
            self.scheduler.finish(stage_id, passed=receipt.status == "recorded",
                                  evidence="stage-result:" + entry["hash"])
            checkpoint(self.scheduler, self.ledger, plan_id=self.plan_key)
            return {"stage": receipt.stage,
                    "state": self.scheduler.loops[stage_id].state,
                    "assessment": assessment, "evidence_sha256": entry["hash"],
                    "next_stage": self.next_stage(),
                    "scientific_claim_established": False, "promotion_authority": False}

    @classmethod
    def open_unlocked(cls, frame: ResearchFrame, ledger) -> "ResearchSession":
        """Internal reload, called ONLY while recovery_guard is owned."""
        entries = _entries(ledger)
        frames = [item["event"] for item in entries
                  if item["event"].get("subsystem") == SUBSYSTEM
                  and item["event"].get("cycle_id") == frame.cycle_id
                  and item["event"].get("state") == "frame"]
        if len(frames) != 1 or frames[0].get("frame_sha256") != frame.sha256:
            raise ValueError("missing or changed research frame")
        scheduler = restore(ledger, plan_id="research:" + frame.cycle_id)
        _assert_stage_evidence(frame, entries, scheduler)
        return cls(frame, ledger, scheduler)
