"""Zero-first, evidence-aware mathematics learning primitives for Merlin.

This module is intentionally dependency-free. It provides a small, testable
vertical slice: a prerequisite graph, typed scalar expression IR, a beginner-
first derivative lesson, numerical differentiation, SQLite learning evidence,
and deterministic next-lesson selection. It does not claim formal proof or
independent CACE verification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


MASTERY_DIMENSIONS = (
    "conceptual",
    "procedural",
    "representational",
    "transfer",
    "proof",
    "retention",
)


@dataclass(frozen=True)
class Concept:
    concept_id: str
    title: str
    description: str
    prerequisites: tuple[str, ...] = ()


class ConceptRegistry:
    """Canonical concept registry with unknown-edge and cycle validation."""

    def __init__(self, concepts: Iterable[Concept] = ()) -> None:
        self._concepts: dict[str, Concept] = {}
        for concept in concepts:
            self.add(concept)

    def add(self, concept: Concept) -> None:
        if not concept.concept_id or concept.concept_id in self._concepts:
            raise ValueError(f"duplicate or empty concept id: {concept.concept_id!r}")
        self._concepts[concept.concept_id] = concept

    def get(self, concept_id: str) -> Concept:
        return self._concepts[concept_id]

    def all(self) -> tuple[Concept, ...]:
        return tuple(self._concepts[key] for key in sorted(self._concepts))

    def validate(self) -> None:
        for concept in self._concepts.values():
            missing = set(concept.prerequisites) - self._concepts.keys()
            if missing:
                raise ValueError(
                    f"{concept.concept_id} has unknown prerequisites: {sorted(missing)}"
                )
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(concept_id: str) -> None:
            if concept_id in visiting:
                raise ValueError(f"prerequisite cycle includes {concept_id}")
            if concept_id in visited:
                return
            visiting.add(concept_id)
            for prerequisite in self._concepts[concept_id].prerequisites:
                visit(prerequisite)
            visiting.remove(concept_id)
            visited.add(concept_id)

        for concept_id in self._concepts:
            visit(concept_id)


DEFAULT_CONCEPTS = ConceptRegistry(
    (
        Concept("quantity", "Amount", "How much of something there is."),
        Concept("change", "Change", "How an amount becomes larger or smaller.", ("quantity",)),
        Concept("rate", "Rate", "How much something changes per unit of something else.", ("change",)),
        Concept("graph", "Graph", "A visual picture of how two quantities relate.", ("quantity",)),
        Concept("slope", "Steepness", "How much a graph rises or falls as we move across.", ("graph", "rate")),
        Concept("function", "Input-output rule", "A rule that assigns an output to an input.", ("quantity",)),
        Concept("limit", "Approaching a value", "What a quantity gets close to as we approach a point.", ("rate", "slope")),
        Concept("derivative", "Derivative", "The instantaneous rate of change of a function.", ("function", "limit", "slope")),
        Concept("probability", "Probability", "A mathematical model for uncertainty and long-run frequencies.", ("quantity",)),
        Concept("state", "State", "The information about a system needed to describe its current condition.", ("quantity",)),
        Concept("transition", "State transition", "A rule describing how a system moves from one state to another.", ("state",)),
        Concept("expected_value", "Expected value", "The probability-weighted average outcome of a random process.", ("probability", "change")),
        Concept("markov_chain", "Markov chain", "A model of state changes whose next step depends on the current state.", ("transition", "probability")),
        Concept("stationary_distribution", "Stationary distribution", "A stable long-run distribution over states of a stochastic process.", ("markov_chain", "expected_value")),
    )
)


@dataclass(frozen=True)
class Expr:
    """A small typed real-scalar expression tree."""

    op: str
    args: tuple["Expr", ...] = ()
    value: float | None = None
    name: str | None = None

    @staticmethod
    def constant(value: float) -> "Expr":
        if not math.isfinite(float(value)):
            raise ValueError("constants must be finite")
        return Expr("const", value=float(value))

    @staticmethod
    def variable(name: str) -> "Expr":
        if not name or not name.isidentifier():
            raise ValueError("variable name must be a non-empty identifier")
        return Expr("var", name=name)

    @staticmethod
    def make(op: str, *args: "Expr") -> "Expr":
        return Expr(op, tuple(args))


def validate_expression(expr: Expr) -> None:
    arity = {"const": 0, "var": 0, "add": 2, "sub": 2, "mul": 2, "div": 2}
    if expr.op not in arity:
        raise ValueError(f"unsupported expression operation: {expr.op}")
    if len(expr.args) != arity[expr.op]:
        raise ValueError(f"{expr.op} expects {arity[expr.op]} arguments")
    if expr.op == "const":
        if expr.value is None or not math.isfinite(expr.value):
            raise ValueError("constant expression requires a finite value")
    elif expr.op == "var":
        if not expr.name or not expr.name.isidentifier():
            raise ValueError("variable expression requires an identifier")
    else:
        for child in expr.args:
            validate_expression(child)


def evaluate_expression(expr: Expr, environment: Mapping[str, float]) -> float:
    validate_expression(expr)
    if expr.op == "const":
        assert expr.value is not None
        return expr.value
    if expr.op == "var":
        assert expr.name is not None
        if expr.name not in environment:
            raise KeyError(f"missing variable: {expr.name}")
        return float(environment[expr.name])
    left = evaluate_expression(expr.args[0], environment)
    right = evaluate_expression(expr.args[1], environment)
    if expr.op == "add":
        result = left + right
    elif expr.op == "sub":
        result = left - right
    elif expr.op == "mul":
        result = left * right
    else:
        if right == 0:
            raise ZeroDivisionError("division by zero in expression")
        result = left / right
    if not math.isfinite(result):
        raise ValueError("expression produced a non-finite result")
    return result


@dataclass(frozen=True)
class LessonStage:
    stage_id: str
    mode: str
    learner_prompt: str
    introduces_symbols: bool = False


@dataclass(frozen=True)
class LessonSpec:
    lesson_id: str
    title: str
    target_concepts: tuple[str, ...]
    prerequisites: tuple[str, ...]
    stages: tuple[LessonStage, ...]
    path_tags: tuple[str, ...] = ("mathematician", "mathematics_programmer", "computational_hacker")
    priority: float = 1.0

    def validate(self) -> None:
        if not self.stages:
            raise ValueError("lesson must contain at least one stage")
        if self.stages[0].mode != "concrete" or self.stages[0].introduces_symbols:
            raise ValueError("zero-first lessons must begin with concrete, symbol-free experience")
        first_symbol = next(
            (i for i, stage in enumerate(self.stages) if stage.introduces_symbols), None
        )
        if first_symbol is not None:
            earlier_modes = {stage.mode for stage in self.stages[:first_symbol]}
            if "visual" not in earlier_modes and "observation" not in earlier_modes:
                raise ValueError("symbols may only follow concrete observation or visual exploration")


DERIVATIVE_DISCOVERY = LessonSpec(
    lesson_id="math.derivative.discovery.zero_first.v1",
    title="How quickly is something changing?",
    target_concepts=("quantity", "change", "rate", "graph", "slope", "function", "limit", "derivative"),
    prerequisites=(),
    stages=(
        LessonStage("everyday-story", "concrete", "A bicycle travels along a path. Compare how far it goes in equal time intervals."),
        LessonStage("build-a-table", "observation", "Sort the distance observations into equal time steps. Which intervals show more movement?"),
        LessonStage("watch-the-graph", "visual", "Move along the curve and watch how its steepness changes. Describe what you notice."),
        LessonStage("compare-nearby-points", "visual", "Choose two nearby points. Compare the average change between them, then bring them closer."),
        LessonStage("name-the-idea", "language", "Explain the difference between change over an interval and change at one instant."),
        LessonStage("introduce-notation", "symbol", "Now introduce f(x), the derivative, and the limit notation as compact names for ideas already explored.", True),
        LessonStage("try-a-computation", "code", "Estimate the rate of change from nearby measurements and compare methods."),
    ),
)
DERIVATIVE_DISCOVERY.validate()


@dataclass(frozen=True)
class DifferenceEstimate:
    method: str
    x: float
    h: float
    estimate: float


def _checked_step(h: float) -> float:
    h = float(h)
    if not math.isfinite(h) or h <= 0:
        raise ValueError("step size h must be finite and greater than zero")
    return h


def forward_difference(function, x: float, h: float) -> DifferenceEstimate:
    h = _checked_step(h)
    return DifferenceEstimate("forward", float(x), h, (function(x + h) - function(x)) / h)


def backward_difference(function, x: float, h: float) -> DifferenceEstimate:
    h = _checked_step(h)
    return DifferenceEstimate("backward", float(x), h, (function(x) - function(x - h)) / h)


def central_difference(function, x: float, h: float) -> DifferenceEstimate:
    h = _checked_step(h)
    return DifferenceEstimate("central", float(x), h, (function(x + h) - function(x - h)) / (2.0 * h))


@dataclass(frozen=True)
class Attempt:
    learner_id: str
    lesson_id: str
    task_id: str
    scores: Mapping[str, float]
    independent: bool
    hints_used: int = 0
    outcome: str = "completed"
    evidence: Mapping[str, Any] = field(default_factory=dict)


class LearnerStore:
    """SQLite persistence for attempts and dimension-specific mastery evidence."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    learner_id TEXT NOT NULL,
                    lesson_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    scores_json TEXT NOT NULL,
                    independent INTEGER NOT NULL,
                    hints_used INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS mastery (
                    learner_id TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    estimate REAL NOT NULL CHECK (estimate >= 0 AND estimate <= 1),
                    evidence_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (learner_id, concept_id, dimension)
                );
                """
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def record_attempt(
        self,
        attempt: Attempt,
        concept_ids: Sequence[str],
        *,
        learning_rate: float = 0.35,
    ) -> int:
        if not attempt.learner_id or not attempt.lesson_id or not attempt.task_id:
            raise ValueError("learner, lesson, and task identifiers are required")
        if not 0 < learning_rate <= 1:
            raise ValueError("learning_rate must be in (0, 1]")
        if attempt.hints_used < 0:
            raise ValueError("hints_used cannot be negative")
        unknown = set(attempt.scores) - set(MASTERY_DIMENSIONS)
        if unknown:
            raise ValueError(f"unknown mastery dimensions: {sorted(unknown)}")
        if not attempt.scores:
            raise ValueError("at least one mastery dimension must be assessed")
        for dimension, score in attempt.scores.items():
            if not math.isfinite(float(score)) or not 0 <= float(score) <= 1:
                raise ValueError(f"{dimension} score must be between 0 and 1")
        if not concept_ids:
            raise ValueError("at least one concept must receive evidence")

        evidence_weight = 1.0 if attempt.independent and attempt.hints_used == 0 else 0.75
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO attempts
                (learner_id, lesson_id, task_id, scores_json, independent,
                 hints_used, outcome, evidence_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    attempt.learner_id, attempt.lesson_id, attempt.task_id,
                    json.dumps(dict(attempt.scores), sort_keys=True),
                    int(attempt.independent), attempt.hints_used, attempt.outcome,
                    json.dumps(dict(attempt.evidence), sort_keys=True),
                ),
            )
            attempt_id = int(cursor.lastrowid)
            for concept_id in sorted(set(concept_ids)):
                for dimension, raw_score in attempt.scores.items():
                    score = float(raw_score) * evidence_weight
                    row = connection.execute(
                        """SELECT estimate, evidence_count FROM mastery
                        WHERE learner_id=? AND concept_id=? AND dimension=?""",
                        (attempt.learner_id, concept_id, dimension),
                    ).fetchone()
                    previous = float(row["estimate"]) if row else 0.0
                    count = int(row["evidence_count"]) if row else 0
                    estimate = previous + learning_rate * (score - previous)
                    connection.execute(
                        """INSERT INTO mastery
                        (learner_id, concept_id, dimension, estimate, evidence_count)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(learner_id, concept_id, dimension)
                        DO UPDATE SET estimate=excluded.estimate,
                                      evidence_count=excluded.evidence_count,
                                      updated_at=CURRENT_TIMESTAMP""",
                        (attempt.learner_id, concept_id, dimension, estimate, count + 1),
                    )
            return attempt_id

    def mastery(self, learner_id: str, concept_id: str) -> dict[str, float]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT dimension, estimate FROM mastery WHERE learner_id=? AND concept_id=?",
                (learner_id, concept_id),
            ).fetchall()
        result = {dimension: 0.0 for dimension in MASTERY_DIMENSIONS}
        result.update({row["dimension"]: float(row["estimate"]) for row in rows})
        return result

    def attempt_count(self, learner_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM attempts WHERE learner_id=?", (learner_id,)
            ).fetchone()
        return int(row["count"])


def select_next_lesson(
    learner_id: str,
    store: LearnerStore,
    lessons: Sequence[LessonSpec],
    concepts: ConceptRegistry = DEFAULT_CONCEPTS,
    *,
    path: str = "mathematician",
    mastery_threshold: float = 0.70,
) -> LessonSpec | None:
    """Select the highest-priority eligible lesson; zero-history learners start at zero."""
    concepts.validate()
    eligible: list[tuple[float, str, LessonSpec]] = []
    for lesson in lessons:
        lesson.validate()
        if path not in lesson.path_tags:
            continue
        if any(concept not in {c.concept_id for c in concepts.all()} for concept in lesson.target_concepts):
            raise ValueError(f"lesson {lesson.lesson_id} references an unknown concept")
        if any(
            sum(
                store.mastery(learner_id, prerequisite)[dimension]
                for dimension in ("conceptual", "procedural", "representational")
            ) / 3.0 < mastery_threshold
            for prerequisite in lesson.prerequisites
        ):
            continue
        gap = sum(
            1.0 - sum(store.mastery(learner_id, concept).values()) / len(MASTERY_DIMENSIONS)
            for concept in lesson.target_concepts
        )
        score = lesson.priority + gap
        eligible.append((score, lesson.lesson_id, lesson))
    if not eligible:
        return None
    eligible.sort(key=lambda item: (-item[0], item[1]))
    return eligible[0][2]
