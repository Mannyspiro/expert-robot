"""Adaptive, deterministic retrieval scheduling for Merlin learning concepts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

Representation = Literal["story", "manipulative", "visual", "language", "symbol", "application"]
REPRESENTATIONS: tuple[Representation, ...] = (
    "story", "manipulative", "visual", "language", "symbol", "application"
)


@dataclass(frozen=True)
class RetrievalState:
    concept_id: str
    due_at: datetime
    interval_days: int = 0
    ease_factor: float = 2.5
    repetitions: int = 0
    lapses: int = 0
    representation_index: int = 0

    def validate(self) -> None:
        if not self.concept_id:
            raise ValueError("concept_id is required")
        if self.due_at.tzinfo is None or self.due_at.utcoffset() is None:
            raise ValueError("due_at must be timezone-aware")
        if self.interval_days < 0 or self.repetitions < 0 or self.lapses < 0:
            raise ValueError("interval, repetitions, and lapses cannot be negative")
        if not 1.3 <= self.ease_factor <= 3.0:
            raise ValueError("ease_factor must be between 1.3 and 3.0")
        if not 0 <= self.representation_index < len(REPRESENTATIONS):
            raise ValueError("invalid representation_index")


@dataclass(frozen=True)
class RetrievalResult:
    state: RetrievalState
    quality: int
    next_representation: Representation


def schedule_retrieval(
    previous: RetrievalState,
    *,
    quality: int,
    reviewed_at: datetime,
) -> RetrievalResult:
    """Apply an SM-2-inspired interval update with representation switching.

    Quality is 0..5. A score below 3 is a failed recall: schedule tomorrow,
    reset the successful streak, and change the representation. A successful
    recall lengthens intervals. Speed is deliberately not an input.
    """
    previous.validate()
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
        raise ValueError("reviewed_at must be timezone-aware")
    if not 0 <= quality <= 5:
        raise ValueError("quality must be an integer from 0 to 5")

    ease = previous.ease_factor
    if quality < 3:
        updated = RetrievalState(
            concept_id=previous.concept_id,
            due_at=reviewed_at + timedelta(days=1),
            interval_days=1,
            ease_factor=max(1.3, ease - 0.2),
            repetitions=0,
            lapses=previous.lapses + 1,
            representation_index=(previous.representation_index + 1) % len(REPRESENTATIONS),
        )
    else:
        ease = min(3.0, max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        if previous.repetitions == 0:
            interval = 1
        elif previous.repetitions == 1:
            interval = 3
        else:
            interval = max(1, round(max(1, previous.interval_days) * ease))
        updated = RetrievalState(
            concept_id=previous.concept_id,
            due_at=reviewed_at + timedelta(days=interval),
            interval_days=interval,
            ease_factor=ease,
            repetitions=previous.repetitions + 1,
            lapses=previous.lapses,
            representation_index=previous.representation_index,
        )
    updated.validate()
    return RetrievalResult(
        state=updated,
        quality=quality,
        next_representation=REPRESENTATIONS[updated.representation_index],
    )


def initial_retrieval_state(concept_id: str, learned_at: datetime) -> RetrievalState:
    if learned_at.tzinfo is None or learned_at.utcoffset() is None:
        raise ValueError("learned_at must be timezone-aware")
    state = RetrievalState(
        concept_id=concept_id,
        due_at=learned_at + timedelta(days=1),
        interval_days=1,
    )
    state.validate()
    return state


class SQLiteRetrievalScheduler:
    """Persist retrieval state in the same SQLite database used by LearnerStore."""

    def __init__(self, database: str) -> None:
        import sqlite3
        self.database = str(database)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS retrieval_schedule (
                    learner_id TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    interval_days INTEGER NOT NULL,
                    ease_factor REAL NOT NULL,
                    repetitions INTEGER NOT NULL,
                    lapses INTEGER NOT NULL,
                    representation_index INTEGER NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (learner_id, concept_id)
                )"""
            )

    def get(self, learner_id: str, concept_id: str) -> RetrievalState | None:
        import sqlite3
        with sqlite3.connect(self.database) as connection:
            row = connection.execute(
                """SELECT due_at, interval_days, ease_factor, repetitions, lapses,
                          representation_index
                   FROM retrieval_schedule WHERE learner_id=? AND concept_id=?""",
                (learner_id, concept_id),
            ).fetchone()
        if row is None:
            return None
        state = RetrievalState(
            concept_id=concept_id,
            due_at=datetime.fromisoformat(row[0]),
            interval_days=int(row[1]),
            ease_factor=float(row[2]),
            repetitions=int(row[3]),
            lapses=int(row[4]),
            representation_index=int(row[5]),
        )
        state.validate()
        return state

    def review(
        self,
        learner_id: str,
        concept_id: str,
        *,
        quality: int,
        reviewed_at: datetime,
    ) -> RetrievalResult:
        import sqlite3
        if not learner_id:
            raise ValueError("learner_id is required")
        previous = self.get(learner_id, concept_id)
        if previous is None:
            previous = initial_retrieval_state(concept_id, reviewed_at)
            # The first retrieval is the immediate lesson review, so make its
            # due time now before applying the recall outcome.
            previous = RetrievalState(
                concept_id=previous.concept_id,
                due_at=reviewed_at,
                interval_days=0,
                ease_factor=previous.ease_factor,
                repetitions=0,
                lapses=0,
                representation_index=0,
            )
        result = schedule_retrieval(previous, quality=quality, reviewed_at=reviewed_at)
        state = result.state
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """INSERT INTO retrieval_schedule
                   (learner_id, concept_id, due_at, interval_days, ease_factor,
                    repetitions, lapses, representation_index)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(learner_id, concept_id) DO UPDATE SET
                     due_at=excluded.due_at,
                     interval_days=excluded.interval_days,
                     ease_factor=excluded.ease_factor,
                     repetitions=excluded.repetitions,
                     lapses=excluded.lapses,
                     representation_index=excluded.representation_index,
                     updated_at=CURRENT_TIMESTAMP""",
                (learner_id, concept_id, state.due_at.isoformat(), state.interval_days,
                 state.ease_factor, state.repetitions, state.lapses,
                 state.representation_index),
            )
        return result

    def due(self, learner_id: str, *, as_of: datetime) -> tuple[RetrievalState, ...]:
        import sqlite3
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        with sqlite3.connect(self.database) as connection:
            rows = connection.execute(
                """SELECT concept_id, due_at, interval_days, ease_factor, repetitions,
                          lapses, representation_index
                   FROM retrieval_schedule
                   WHERE learner_id=? AND due_at<=? ORDER BY due_at, concept_id""",
                (learner_id, as_of.isoformat()),
            ).fetchall()
        states = tuple(
            RetrievalState(
                concept_id=row[0], due_at=datetime.fromisoformat(row[1]),
                interval_days=int(row[2]), ease_factor=float(row[3]),
                repetitions=int(row[4]), lapses=int(row[5]),
                representation_index=int(row[6]),
            )
            for row in rows
        )
        for state in states:
            state.validate()
        return states
