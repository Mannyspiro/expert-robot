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
        if not self.lesson_id or not self.title:
            raise ValueError("lesson id and title are required")
        if not math.isfinite(self.priority) or self.priority <= 0:
            raise ValueError("lesson priority must be finite and greater than zero")
        if len({stage.stage_id for stage in self.stages}) != len(self.stages):
            raise ValueError("lesson stage ids must be unique")
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


@dataclass
class LessonSession:
    """Sequential lesson runner; later stages cannot be skipped."""

    lesson: LessonSpec
    stage_index: int = 0
    completed_stage_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.lesson.validate()
        if self.stage_index < 0 or self.stage_index > len(self.lesson.stages):
            raise ValueError("stage_index is outside the lesson")
        expected = [stage.stage_id for stage in self.lesson.stages[: self.stage_index]]
        if self.completed_stage_ids != expected:
            raise ValueError("completed stages must be the exact sequential lesson prefix")

    @property
    def current_stage(self) -> LessonStage | None:
        if self.stage_index >= len(self.lesson.stages):
            return None
        return self.lesson.stages[self.stage_index]

    @property
    def is_complete(self) -> bool:
        return self.stage_index == len(self.lesson.stages)

    def complete_current_stage(self, stage_id: str) -> LessonStage | None:
        current = self.current_stage
        if current is None:
            raise ValueError("lesson is already complete")
        if stage_id != current.stage_id:
            raise ValueError(f"expected current stage {current.stage_id}, got {stage_id}")
        self.completed_stage_ids.append(current.stage_id)
        self.stage_index += 1
        return self.current_stage


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
        known_concepts = {concept.concept_id for concept in concepts.all()}
        unknown_concepts = (set(lesson.target_concepts) | set(lesson.prerequisites)) - known_concepts
        if unknown_concepts:
            raise ValueError(
                f"lesson {lesson.lesson_id} references unknown concepts: {sorted(unknown_concepts)}"
            )
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


# --- Spaced repetition, comprehensive input, and strategy-mix experiments ---

from datetime import datetime, timedelta, timezone\nimport hashlib
from typing import Literal


INPUT_MODES = frozenset({
    "text", "choice", "numeric", "expression", "code", "proof",
    "graph", "audio", "video", "mixed",
})
TEACHING_STRATEGIES = (
    "retrieval_practice",
    "worked_example",
    "interleaving",
    "visual_exploration",
    "self_explanation",
    "spaced_review",
)


@dataclass(frozen=True)
class LearningInput:
    """A normalized envelope for diverse learner responses and media references."""
    learner_id: str
    lesson_id: str
    task_id: str
    mode: str
    response: Mapping[str, Any]
    confidence: float | None = None
    hints_used: int = 0
    elapsed_seconds: float | None = None
    accessibility: Mapping[str, Any] = field(default_factory=dict)
    source_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not all((self.learner_id, self.lesson_id, self.task_id)):
            raise ValueError("learner, lesson and task identifiers are required")
        if self.mode not in INPUT_MODES:
            raise ValueError(f"unsupported input mode: {self.mode}")
        if not isinstance(self.response, Mapping) or not self.response:
            raise ValueError("response must be a non-empty mapping")
        if self.confidence is not None and (
            not math.isfinite(float(self.confidence)) or not 0 <= self.confidence <= 1
        ):
            raise ValueError("confidence must be between zero and one")
        if self.hints_used < 0:
            raise ValueError("hints_used cannot be negative")
        if self.elapsed_seconds is not None and (
            not math.isfinite(float(self.elapsed_seconds)) or self.elapsed_seconds < 0
        ):
            raise ValueError("elapsed_seconds must be finite and non-negative")
        if any(not isinstance(ref, str) or not ref.strip() for ref in self.source_refs):
            raise ValueError("source references must be non-empty strings")


@dataclass(frozen=True)
class ReviewCard:
    learner_id: str
    concept_id: str
    due_at: str
    interval_days: int
    repetitions: int
    ease_factor: float
    last_quality: int | None


@dataclass(frozen=True)
class ReviewResult:
    card: ReviewCard
    quality: int
    next_due_at: str


class SpacedRepetition:
    """SM-2-inspired scheduler; quality 0..5 is learner recall quality."""
    def __init__(self, store: LearnerStore) -> None:
        self.store = store
        with store._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS review_cards (
                    learner_id TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    interval_days INTEGER NOT NULL DEFAULT 0,
                    repetitions INTEGER NOT NULL DEFAULT 0,
                    ease_factor REAL NOT NULL DEFAULT 2.5,
                    last_quality INTEGER,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (learner_id, concept_id)
                );
                """
            )

    def ensure_card(self, learner_id: str, concept_id: str, *, now: datetime | None = None) -> ReviewCard:
        if not learner_id or not concept_id:
            raise ValueError("learner and concept identifiers are required")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        due = current.astimezone(timezone.utc).isoformat()
        with self.store._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO review_cards
                (learner_id, concept_id, due_at) VALUES (?, ?, ?)""",
                (learner_id, concept_id, due),
            )
        return self.get_card(learner_id, concept_id)

    def get_card(self, learner_id: str, concept_id: str) -> ReviewCard:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT * FROM review_cards WHERE learner_id=? AND concept_id=?",
                (learner_id, concept_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"no review card for {learner_id}/{concept_id}")
        return ReviewCard(
            row["learner_id"], row["concept_id"], row["due_at"],
            int(row["interval_days"]), int(row["repetitions"]),
            float(row["ease_factor"]), row["last_quality"],
        )

    def due_cards(self, learner_id: str, *, now: datetime | None = None, limit: int = 50) -> tuple[ReviewCard, ...]:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or limit < 1:
            raise ValueError("timezone-aware now and positive limit are required")
        stamp = current.astimezone(timezone.utc).isoformat()
        with self.store._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM review_cards WHERE learner_id=? AND due_at<=?
                ORDER BY due_at, concept_id LIMIT ?""",
                (learner_id, stamp, int(limit)),
            ).fetchall()
        return tuple(ReviewCard(
            r["learner_id"], r["concept_id"], r["due_at"],
            int(r["interval_days"]), int(r["repetitions"]),
            float(r["ease_factor"]), r["last_quality"],
        ) for r in rows)

    def defer(self, learner_id: str, concept_id: str, days: int, *, now: datetime | None = None) -> ReviewCard:
        if isinstance(days, bool) or not isinstance(days, int) or days < 1:
            raise ValueError("deferral must be a positive whole number of days")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        self.ensure_card(learner_id, concept_id, now=current)
        due = (current.astimezone(timezone.utc) + timedelta(days=days)).isoformat()
        with self.store._connect() as connection:
            connection.execute(
                "UPDATE review_cards SET due_at=?, updated_at=CURRENT_TIMESTAMP WHERE learner_id=? AND concept_id=?",
                (due, learner_id, concept_id),
            )
        return self.get_card(learner_id, concept_id)

    def review(
        self, learner_id: str, concept_id: str, quality: int,
        *, now: datetime | None = None,
    ) -> ReviewResult:
        if isinstance(quality, bool) or not isinstance(quality, int) or not 0 <= quality <= 5:
            raise ValueError("review quality must be an integer from 0 to 5")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        self.ensure_card(learner_id, concept_id, now=current)
        card = self.get_card(learner_id, concept_id)
        ease = max(1.3, card.ease_factor + (0.1 - (5-quality) * (0.08 + (5-quality) * 0.02)))
        if quality < 3:
            repetitions, interval = 0, 1
        elif card.repetitions == 0:
            repetitions, interval = 1, 1
        elif card.repetitions == 1:
            repetitions, interval = 2, 6
        else:
            repetitions = card.repetitions + 1
            interval = max(1, round(card.interval_days * ease))
        due = (current.astimezone(timezone.utc) + timedelta(days=interval)).isoformat()
        with self.store._connect() as connection:
            connection.execute(
                """UPDATE review_cards SET due_at=?, interval_days=?, repetitions=?,
                ease_factor=?, last_quality=?, updated_at=CURRENT_TIMESTAMP
                WHERE learner_id=? AND concept_id=?""",
                (due, interval, repetitions, ease, quality, learner_id, concept_id),
            )
        # Delayed retrieval is direct evidence about retention, not merely completion.
        self.store.record_attempt(
            Attempt(
                learner_id, "spaced-repetition", f"review:{concept_id}",
                {"retention": quality / 5.0}, independent=True, hints_used=0,
                outcome="recalled" if quality >= 3 else "needs_relearning",
                evidence={"quality_0_to_5": quality, "interval_days_before_review": card.interval_days},
            ),
            (concept_id,),
        )
        return ReviewResult(self.get_card(learner_id, concept_id), quality, due)


class LearningInputStore:
    """Persists normalized response envelopes without storing raw media blobs."""
    def __init__(self, store: LearnerStore) -> None:
        self.store = store
        with store._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS learning_inputs (
                input_id INTEGER PRIMARY KEY AUTOINCREMENT,
                learner_id TEXT NOT NULL, lesson_id TEXT NOT NULL, task_id TEXT NOT NULL,
                mode TEXT NOT NULL, response_json TEXT NOT NULL, confidence REAL,
                hints_used INTEGER NOT NULL, elapsed_seconds REAL,
                accessibility_json TEXT NOT NULL, source_refs_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""
            )

    def record(self, item: LearningInput) -> int:
        item.validate()
        try:
            response = json.dumps(dict(item.response), sort_keys=True, allow_nan=False)
            accessibility = json.dumps(dict(item.accessibility), sort_keys=True, allow_nan=False)
            refs = json.dumps(list(item.source_refs), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("input metadata must be JSON-serializable and finite") from exc
        with self.store._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO learning_inputs
                (learner_id, lesson_id, task_id, mode, response_json, confidence,
                 hints_used, elapsed_seconds, accessibility_json, source_refs_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item.learner_id, item.lesson_id, item.task_id, item.mode, response,
                 item.confidence, item.hints_used, item.elapsed_seconds, accessibility, refs),
            )
            return int(cursor.lastrowid)


@dataclass(frozen=True)
class StrategyAssignment:
    learner_id: str
    concept_id: str
    session_index: int
    strategy: str
    policy: str


class ParrondoLearningExperiment:
    """Compare single-strategy baselines with a mixed strategy portfolio.

    This operationalizes a Parrondo-inspired hypothesis, not a mathematical
    guarantee: alternation may outperform individual strategies in some learner
    states. Outcomes must be measured against randomized, comparable controls.
    """
    def __init__(self, strategies: Sequence[str] = TEACHING_STRATEGIES) -> None:
        if not strategies or any(s not in TEACHING_STRATEGIES for s in strategies):
            raise ValueError("experiment strategies must be known and non-empty")
        self.strategies = tuple(dict.fromkeys(strategies))

    def assign(
        self, learner_id: str, concept_id: str, session_index: int,
        *, policy: str = "mixed",
    ) -> StrategyAssignment:
        if not learner_id or not concept_id or session_index < 0:
            raise ValueError("learner, concept and non-negative session index required")
        if policy == "mixed":
            # Rotate rather than repeat a single method. A production experiment
            # should randomize policy assignment at learner/concept cluster level.
            strategy = self.strategies[session_index % len(self.strategies)]
        elif policy.startswith("single:"):
            strategy = policy.split(":", 1)[1]
            if strategy not in self.strategies:
                raise ValueError("single-strategy control is not in this experiment")
        else:
            raise ValueError("policy must be 'mixed' or 'single:<strategy>'")
        return StrategyAssignment(learner_id, concept_id, session_index, strategy, policy)


def compare_strategy_policies(
    outcomes: Mapping[str, Sequence[Mapping[str, float]]],
) -> dict[str, dict[str, float]]:
    """Summarize measured delayed retention/transfer; never infer causality."""
    metrics = ("immediate_accuracy", "delayed_retention", "transfer", "independent_solve")
    summary: dict[str, dict[str, float]] = {}
    for policy, rows in outcomes.items():
        if not rows:
            continue
        summary[policy] = {}
        for metric in metrics:
            values = [float(row[metric]) for row in rows if metric in row]
            if any(not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                raise ValueError(f"{policy}/{metric} values must be in [0, 1]")
            if values:
                summary[policy][metric] = sum(values) / len(values)
        summary[policy]["sample_count"] = float(len(rows))
    return summary


class StrategyArmAllocator:
    """Reproducible cluster-level arm assignment for controlled learning studies.

    Hash-based allocation is deterministic for audit/replay. It is not a
    substitute for checking balance, preregistering outcomes, or estimating
    uncertainty; production studies should preserve the allocation receipt.
    """
    @staticmethod
    def assign_arm(
        learner_id: str, concept_id: str, experiment_id: str,
        arms: Sequence[str], *, seed: str,
    ) -> str:
        if not learner_id or not concept_id or not experiment_id or not seed:
            raise ValueError("learner, concept, experiment and seed are required")
        unique_arms = tuple(dict.fromkeys(arms))
        if len(unique_arms) < 2 or any(not arm for arm in unique_arms):
            raise ValueError("at least two distinct non-empty experiment arms are required")
        payload = "\\x1f".join((seed, experiment_id, learner_id, concept_id)).encode("utf-8")
        digest = hashlib.sha256(payload).digest()
        index = int.from_bytes(digest[:8], "big") % len(unique_arms)
        return unique_arms[index]
