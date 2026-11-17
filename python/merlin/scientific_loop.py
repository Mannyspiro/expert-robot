"""Evidence-first scientific operating loop for Merlin.

This module supplies deterministic policy primitives. It does not infer that a
hypothesis is true, execute experiments, promote capabilities, or grant authority.
Model-generated ideas remain hypotheses until their evidence is independently checked.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
from typing import Any, Mapping, Sequence
from datetime import datetime


@dataclass(frozen=True)
class Observation:
    observation_id: str
    question: str
    method: str
    measurements: Mapping[str, float]
    units: Mapping[str, str]
    uncertainty: Mapping[str, float]
    conditions: Mapping[str, str]
    source_refs: tuple[str, ...]
    observed_at: str
    artifact_sha256: str = ""

    def validate(self) -> None:
        for name, value in (
            ("observation_id", self.observation_id),
            ("question", self.question),
            ("method", self.method),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if not self.measurements:
            raise ValueError("at least one measured quantity is required")
        if not self.source_refs or any(not str(x).strip() for x in self.source_refs):
            raise ValueError("observations require source references")
        try:
            stamp = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise ValueError("observed_at must be an offset-aware ISO-8601 timestamp") from exc
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("observed_at must include a timezone offset")
        if not self.conditions:
            raise ValueError("measurement conditions must be recorded")
        for metric, value in self.measurements.items():
            if not isinstance(metric, str) or not metric.strip():
                raise ValueError("measurement names must be non-empty")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"measurement {metric!r} must be finite numeric data")
            unit = self.units.get(metric)
            sigma = self.uncertainty.get(metric)
            if not isinstance(unit, str) or not unit.strip():
                raise ValueError(f"measurement {metric!r} requires an explicit unit")
            if isinstance(sigma, bool) or not isinstance(sigma, (int, float)) or not math.isfinite(sigma) or sigma < 0:
                raise ValueError(f"measurement {metric!r} requires finite nonnegative uncertainty")
        if self.artifact_sha256 and (
            len(self.artifact_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in self.artifact_sha256)
        ):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class Prediction:
    metric: str
    expected: float
    tolerance: float
    unit: str

    def validate(self) -> None:
        for label, value in (("metric", self.metric), ("unit", self.unit)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("prediction " + label + " must be non-empty text")
        for value in (self.expected, self.tolerance):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("prediction expectation/tolerance must be finite numeric data")
        if self.tolerance < 0 or not all(
            math.isfinite(self.expected + sign * self.tolerance) for sign in (-1, 1)
        ):
            raise ValueError("prediction tolerance/interval must be finite and nonnegative")


def compare_observation(observation: Observation, predictions: Sequence[Prediction]) -> dict[str, Any]:
    """Deductively compare preregistered predictions with measured intervals."""
    observation.validate()
    if not predictions:
        raise ValueError("at least one preregistered prediction is required")
    comparisons = []
    for prediction in predictions:
        if not isinstance(prediction, Prediction):
            raise ValueError("predictions must contain typed Prediction records")
        prediction.validate()
        if prediction.metric not in observation.measurements:
            comparisons.append({"metric": prediction.metric, "result": "unobserved"})
            continue
        if prediction.unit != observation.units[prediction.metric]:
            comparisons.append({"metric": prediction.metric, "result": "incomparable_unit"})
            continue
        measured = float(observation.measurements[prediction.metric])
        sigma = float(observation.uncertainty[prediction.metric])
        lo, hi = measured - sigma, measured + sigma
        if not math.isfinite(lo) or not math.isfinite(hi):
            raise ValueError("measured interval must be finite")
        expected_lo = prediction.expected - prediction.tolerance
        expected_hi = prediction.expected + prediction.tolerance
        if hi < expected_lo or lo > expected_hi:
            result = "contradicts"
        elif lo >= expected_lo and hi <= expected_hi:
            result = "supports"
        else:
            result = "inconclusive_overlap"
        comparisons.append({
            "metric": prediction.metric, "result": result,
            "measured_interval": [lo, hi],
            "predicted_interval": [expected_lo, expected_hi],
            "unit": prediction.unit,
        })
    states = {item["result"] for item in comparisons}
    overall = (
        "contradicted" if "contradicts" in states
        else "inconclusive" if states - {"supports"}
        else "consistent_with_prediction"
    )
    return {
        "schema": "merlin-observation-assessment/1",
        "observation_id": observation.observation_id,
        "reasoning_mode": "deductive_prediction_check",
        "overall": overall,
        "comparisons": comparisons,
        "claim_boundary": "Consistency with predictions is not proof of a general claim.",
    }


def update_plan_from_observations(
    current_plan: Mapping[str, Any],
    observations: Sequence[Observation],
    *,
    next_actions: Sequence[str],
) -> dict[str, Any]:
    """Create an auditable inductive update; never silently overwrite the plan."""
    if not isinstance(current_plan, Mapping) or not current_plan:
        raise ValueError("current_plan must be a non-empty versioned plan")
    plan_id, version = current_plan.get("plan_id"), current_plan.get("version")
    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("current_plan requires an explicit parent plan_id")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("current_plan requires a positive parent plan version")
    if not observations:
        raise ValueError("at least one observation is required for an inductive update")
    for item in observations:
        item.validate()
    if isinstance(next_actions, (str, bytes)) or not next_actions or any(
        not isinstance(x, str) or not x.strip() for x in next_actions
    ):
        raise ValueError("next_actions must state at least one concrete next step")
    return {
        "schema": "merlin-plan-update/1",
        "parent_plan_id": current_plan.get("plan_id"),
        "parent_plan_version": current_plan.get("version"),
        "reasoning_mode": "inductive_revision",
        "observation_ids": [item.observation_id for item in observations],
        "observed_artifacts": [item.artifact_sha256 for item in observations if item.artifact_sha256],
        "changes": [{
            "type": "evidence_informed_revision",
            "rationale": "Plan update is linked to explicit observations; conclusions remain provisional.",
        }],
        "next_actions": list(next_actions),
        "requires_review": True,
        "authority_effect": "none",
    }


def enumerate_useful_combinations(
    primitives: Sequence[Mapping[str, Any]],
    compatible_pairs: set[frozenset[str]],
    *,
    trigger: str,
    problem: str,
    max_size: int = 3,
    max_cost: float = float("inf"),
    limit: int = 64,
) -> list[dict[str, Any]]:
    """Bounded Ideonomy enumeration; refuses unguided Cartesian-product ideation."""
    if not trigger.strip() or not problem.strip():
        raise ValueError("enumeration requires an explicit trigger and problem")
    if not 2 <= max_size <= 3 or not 1 <= limit <= 512:
        raise ValueError("max_size must be 2–3 and limit must be 1–512")
    if isinstance(max_cost, bool) or not isinstance(max_cost, (int, float)) or max_cost < 0 or math.isnan(max_cost):
        raise ValueError("max_cost must be a nonnegative number")
    ids = [str(p.get("id", "")) for p in primitives]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError("primitive IDs must be present and unique")
    output = []
    for size in range(2, max_size + 1):
        for group in combinations(primitives, size):
            names = [str(p["id"]) for p in group]
            domains = {str(p.get("domain", "")) for p in group}
            if "" in domains or len(domains) < 2:
                continue
            if any(frozenset(pair) not in compatible_pairs for pair in combinations(names, 2)):
                continue
            if any(p.get("status") in {"refuted", "rejected", "disabled"} for p in group):
                continue
            cost = sum(float(p.get("estimated_cost", 0.0)) for p in group)
            if not math.isfinite(cost) or cost > max_cost:
                continue
            output.append({
                "combination_id": "ideonomy-" + "-".join(names),
                "primitive_ids": names,
                "domains": sorted(domains),
                "problem": problem,
                "trigger": trigger,
                "estimated_cost": cost,
                "epistemic_status": "hypothesis_combination",
                "required_next_step": "state a falsifiable mechanism and measurable test",
            })
    output.sort(key=lambda item: (item["estimated_cost"], item["combination_id"]))
    return output[:limit]


def decompose_by_analogy(
    problem: str,
    analogy: str,
    invariant_mapping: Mapping[str, str],
    subproblems: Sequence[str],
) -> dict[str, Any]:
    """Translate a blocked task only when the invariants survive the mapping."""
    if not problem.strip() or not analogy.strip() or not subproblems:
        raise ValueError("problem, analogy and subproblems are required")
    if not invariant_mapping or any(not str(k).strip() or not str(v).strip()
                                    for k, v in invariant_mapping.items()):
        raise ValueError("explicit source-to-analogue invariant mapping is required")
    return {
        "schema": "merlin-analogy-decomposition/1",
        "original_problem": problem,
        "analogue": analogy,
        "invariant_mapping": dict(invariant_mapping),
        "subproblems": list(subproblems),
        "translation_back_gate": "recheck every mapped invariant against the original task",
        "acceptance_gate": "original-task tests must pass after translation back",
        "epistemic_status": "problem_reframing_not_evidence",
    }


def scientific_loop_contract() -> dict[str, Any]:
    """Machine-readable invariants every Merlin research workflow must enforce."""
    return {
        "schema": "merlin-scientific-loop-contract/1",
        "mandatory_stages": [
            "capture_observation_with_provenance_and_uncertainty",
            "separate_observation_interpretation_and_hypothesis",
            "enumerate_competing_explanations_when_ambiguity_is_material",
            "preregister_predictions_and_falsifiers",
            "choose_lowest_cost_discriminating_experiment",
            "record_negative_and_null_results",
            "independently_verify_critical_artifacts",
            "update_plan_with_parent_version_and_observation_ids",
            "preserve_dissent_and_unresolved_unknowns",
        ],
        "reasoning_modes": ["inductive", "deductive", "abductive", "analogical"],
        "ideonomy_policy": "enumerate only when a concrete problem/trigger exists; filter by compatibility, constraints, testability and cost",
        "analogy_policy": "map invariants explicitly, decompose, solve, translate back and rerun original tests",
        "promotion_policy": "evidence and human/policy gates required; capability grows, authority never expands",
        "failure_policy": "classify root cause, add regression test and detection rule, verify prevention",
    }


__all__ = [
    "Observation", "Prediction", "compare_observation",
    "update_plan_from_observations", "enumerate_useful_combinations",
    "decompose_by_analogy", "scientific_loop_contract",
]
