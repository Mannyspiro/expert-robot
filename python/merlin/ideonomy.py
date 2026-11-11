"""Bounded combinatorial Ideonomy for coherent mathematics lesson designs.

The enumerator makes the idea space explicit, counts the full Cartesian product,
rejects pedagogically or technically incoherent combinations with reasons, and
ranks viable candidates deterministically. It proposes designs; it does not
claim that a design is empirically effective or award learner mastery.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import product
from typing import Iterable


PATHS = ("mathematician", "mathematics_programmer", "computational_hacker")
REPRESENTATIONS = ("concrete_objects", "visual_graph", "state_table", "executable_model")
ACTIVITIES = ("predict_then_test", "explore_simulation", "derive_transition_rule", "implement_simulation")
EVIDENCE = ("concept_check", "independent_transfer", "formal_proof", "reflection_only")
SEQUENCES = ("concrete_visual_symbolic", "concrete_table_model_symbolic", "problem_code_explain")
CONTEXTS = ("everyday_game", "resource_allocation", "scientific_system")


@dataclass(frozen=True)
class LessonDesign:
    path: str
    representation: str
    activity: str
    evidence: str
    sequence: str
    context: str
    score: float
    rationale: tuple[str, ...]


@dataclass(frozen=True)
class IdeonomyReport:
    cartesian_size: int
    evaluated: int
    retained: tuple[LessonDesign, ...]
    rejection_counts: dict[str, int]

    @property
    def rejected(self) -> int:
        return self.evaluated - len(self.retained)


def _rejection_reasons(path: str, representation: str, activity: str,
                       evidence: str, sequence: str, context: str) -> tuple[str, ...]:
    reasons: list[str] = []
    if evidence == "formal_proof" and path != "mathematician":
        reasons.append("formal-proof-evidence-outside-mathematician-path")
    if activity == "implement_simulation" and path == "mathematician":
        reasons.append("implementation-task-mismatched-to-path")
    if activity == "derive_transition_rule" and path == "computational_hacker":
        reasons.append("symbolic-derivation-not-primary-hacker-task")
    if representation == "executable_model" and activity not in ("explore_simulation", "implement_simulation"):
        reasons.append("executable-model-without-computational-activity")
    if sequence == "problem_code_explain" and representation != "executable_model":
        reasons.append("code-sequence-without-executable-representation")
    if sequence == "problem_code_explain" and activity == "derive_transition_rule":
        reasons.append("code-sequence-conflicts-with-derivation-only-activity")
    if evidence == "reflection_only":
        reasons.append("reflection-alone-cannot-establish-mastery")
    if context == "everyday_game" and representation == "executable_model" and activity == "derive_transition_rule":
        reasons.append("game-context-derivation-needs-visible-state-model")
    return tuple(reasons)


def _score(path: str, representation: str, activity: str, evidence: str,
           sequence: str, context: str) -> tuple[float, tuple[str, ...]]:
    score = 1.0
    rationale = ["starts from a concrete or observable problem"]
    if representation in ("visual_graph", "state_table"):
        score += 1.2
        rationale.append("makes state and change inspectable")
    if activity == "predict_then_test":
        score += 1.5
        rationale.append("elicits a falsifiable prediction before feedback")
    elif activity == "explore_simulation":
        score += 1.0
        rationale.append("supports controlled experimentation")
    elif activity == "derive_transition_rule":
        score += 1.4
        rationale.append("connects observations to a general rule")
    elif activity == "implement_simulation":
        score += 1.2
        rationale.append("turns the model into an executable artifact")
    if evidence == "independent_transfer":
        score += 2.0
        rationale.append("checks independent transfer to a changed situation")
    elif evidence == "formal_proof":
        score += 1.8
        rationale.append("adds a deductive proof obligation")
    elif evidence == "concept_check":
        score += 1.0
        rationale.append("checks conceptual understanding")
    if sequence != "problem_code_explain":
        score += 0.8
        rationale.append("delays formalism until after exploration")
    if path == "mathematics_programmer" and activity == "implement_simulation":
        score += 0.8
    if path == "computational_hacker" and activity in ("predict_then_test", "explore_simulation"):
        score += 0.6
    if context == "scientific_system":
        score += 0.3
    return score, tuple(rationale)


def enumerate_lesson_designs(*, limit: int = 24) -> IdeonomyReport:
    """Enumerate every bounded combination, explain exclusions, return top designs."""
    if limit < 1:
        raise ValueError("limit must be positive")
    axes = (PATHS, REPRESENTATIONS, ACTIVITIES, EVIDENCE, SEQUENCES, CONTEXTS)
    cartesian_size = 1
    for axis in axes:
        cartesian_size *= len(axis)
    retained: list[LessonDesign] = []
    rejected: Counter[str] = Counter()
    evaluated = 0
    for path, representation, activity, evidence, sequence, context in product(*axes):
        evaluated += 1
        reasons = _rejection_reasons(path, representation, activity, evidence, sequence, context)
        if reasons:
            rejected.update(reasons)
            continue
        score, rationale = _score(path, representation, activity, evidence, sequence, context)
        retained.append(LessonDesign(path, representation, activity, evidence, sequence, context, score, rationale))
    retained.sort(key=lambda item: (-item.score, item.path, item.representation,
                                    item.activity, item.evidence, item.sequence, item.context))
    return IdeonomyReport(cartesian_size, evaluated, tuple(retained[:limit]), dict(sorted(rejected.items())))


def parrondo_design_shortlist(*, limit: int = 12) -> IdeonomyReport:
    """Named entry point for the current Parrondo lesson design problem."""
    return enumerate_lesson_designs(limit=limit)
