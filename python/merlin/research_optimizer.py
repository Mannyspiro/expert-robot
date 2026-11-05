"""Transparent multi-objective research task ranking for Merlin.

This module ranks only tasks that pass caller-supplied hard admission constraints.
It does not grant permissions, reserve resources, dispatch work or change verifier policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class ResearchMetrics:
    information_gain: float
    verified_progress: float
    dependency_unlock_value: float
    reproducibility: float
    uncertainty: float
    compute_cost: float
    wall_time: float
    verification_cost: float

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True)
class ResearchWeights:
    information_gain: float = 1.0
    verified_progress: float = 1.5
    dependency_unlock_value: float = 0.8
    reproducibility: float = 0.5
    uncertainty: float = 0.5
    compute_cost: float = 0.4
    wall_time: float = 0.2
    verification_cost: float = 0.3

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"weight {name} must be numeric")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"weight {name} must be finite and non-negative")


@dataclass(frozen=True)
class ResearchCandidate:
    task_id: str
    metrics: ResearchMetrics
    constraints: dict[str, bool]
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RankedCandidate:
    task_id: str
    score: float
    components: dict[str, float]
    pareto_optimal: bool
    evidence_refs: tuple[str, ...]


MAXIMIZE = (
    "information_gain", "verified_progress",
    "dependency_unlock_value", "reproducibility",
)
MINIMIZE = ("uncertainty", "compute_cost", "wall_time", "verification_cost")


def _dominates(left: ResearchMetrics, right: ResearchMetrics) -> bool:
    """True when left is no worse in every objective and better in at least one."""
    a, b = asdict(left), asdict(right)
    no_worse = all(a[key] >= b[key] for key in MAXIMIZE) and all(
        a[key] <= b[key] for key in MINIMIZE
    )
    strictly_better = any(a[key] > b[key] for key in MAXIMIZE) or any(
        a[key] < b[key] for key in MINIMIZE
    )
    return no_worse and strictly_better


def pareto_front(candidates: Iterable[ResearchCandidate]) -> set[str]:
    items = list(candidates)
    for item in items:
        item.metrics.validate()
    return {
        item.task_id for item in items
        if not any(
            other.task_id != item.task_id and _dominates(other.metrics, item.metrics)
            for other in items
        )
    }


def rank_research_candidates(
    candidates: Iterable[ResearchCandidate],
    weights: ResearchWeights | None = None,
) -> list[RankedCandidate]:
    """Return admissible candidates with visible score components and Pareto flags.

    A missing/false hard constraint excludes a candidate. Constraint values are
    never inferred from a model score. Weights are explicit policy inputs.
    """
    policy = weights or ResearchWeights()
    policy.validate()
    items = list(candidates)
    seen: set[str] = set()
    for item in items:
        if not isinstance(item.task_id, str) or not item.task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if item.task_id in seen:
            raise ValueError(f"duplicate task_id: {item.task_id}")
        seen.add(item.task_id)
        item.metrics.validate()
        if not isinstance(item.constraints, dict) or any(
            not isinstance(key, str) or not isinstance(value, bool)
            for key, value in item.constraints.items()
        ):
            raise ValueError("constraints must map string names to booleans")
        if any(not isinstance(ref, str) or not ref.strip() for ref in item.evidence_refs):
            raise ValueError("evidence_refs must contain non-empty strings")

    admissible = [item for item in items if item.constraints and all(item.constraints.values())]
    front = pareto_front(admissible)
    ranked: list[RankedCandidate] = []
    for item in admissible:
        values = asdict(item.metrics)
        components = {
            "information_gain": policy.information_gain * values["information_gain"],
            "verified_progress": policy.verified_progress * values["verified_progress"],
            "dependency_unlock_value": policy.dependency_unlock_value * values["dependency_unlock_value"],
            "reproducibility": policy.reproducibility * values["reproducibility"],
            "uncertainty": -policy.uncertainty * values["uncertainty"],
            "compute_cost": -policy.compute_cost * values["compute_cost"],
            "wall_time": -policy.wall_time * values["wall_time"],
            "verification_cost": -policy.verification_cost * values["verification_cost"],
        }
        ranked.append(RankedCandidate(
            task_id=item.task_id,
            score=sum(components.values()),
            components=components,
            pareto_optimal=item.task_id in front,
            evidence_refs=item.evidence_refs,
        ))
    return sorted(ranked, key=lambda item: (
        not item.pareto_optimal, -item.score, item.task_id
    ))


__all__ = [
    "ResearchMetrics", "ResearchWeights", "ResearchCandidate",
    "RankedCandidate", "pareto_front", "rank_research_candidates",
]
