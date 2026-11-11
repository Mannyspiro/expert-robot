"""Framework-neutral interactive lesson renderer and evidence adapter."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from typing import Any, Mapping

from .lesson_schema import LessonBlock, LessonDocument
from .learning_core import Attempt, LearnerStore, MASTERY_DIMENSIONS


@dataclass(frozen=True)
class RenderedBlock:
    block_id: str
    kind: str
    presentation: Mapping[str, Any]
    interaction_contract: tuple[str, ...]


INTERACTIONS = {
    "story": ("continue", "replay_audio"),
    "manipulative": ("apply_action", "reset", "undo"),
    "choice": ("submit_choice", "change_choice"),
    "simulation": ("run", "replay_seed", "change_seed", "change_parameters"),
    "chart": ("inspect_point", "change_series"),
    "explanation": ("reveal_next", "open_glossary"),
    "reflection": ("submit_reflection", "set_confidence"),
    "retrieval": ("submit_recall", "request_hint"),
    "assessment": ("submit_response", "request_hint"),
}


def render_block(block: LessonBlock) -> RenderedBlock:
    block.validate()
    # The adapter returns semantic view data; a web/mobile UI owns actual widgets.
    presentation = dict(block.content)
    if block.kind == "simulation":
        presentation.setdefault("reproducible", True)
        presentation.setdefault("show_seed", True)
        presentation.setdefault("show_parameters", True)
    if block.kind == "chart":
        presentation.setdefault("accessible_description", "")
        presentation.setdefault("show_uncertainty", True)
    if block.kind == "explanation":
        presentation.setdefault("progressive_disclosure", True)
    return RenderedBlock(
        block_id=block.block_id,
        kind=block.kind,
        presentation=presentation,
        interaction_contract=INTERACTIONS[block.kind],
    )


def render_lesson(lesson: LessonDocument) -> dict[str, Any]:
    lesson.validate()
    return {
        "lesson_id": lesson.lesson_id,
        "version": lesson.version,
        "title": lesson.title,
        "concept_ids": lesson.concept_ids,
        "blocks": tuple(render_block(block) for block in lesson.blocks),
        "accessibility": {
            "keyboard": True,
            "screen_reader_labels_required": True,
            "reduced_motion": True,
            "captions": True,
            "text_alternatives": True,
        },
    }


def record_interaction(
    store: LearnerStore,
    *,
    learner_id: str,
    lesson: LessonDocument,
    block_id: str,
    event_type: str,
    response: Any,
    independent: bool = True,
    hints_used: int = 0,
    scores: Mapping[str, float] | None = None,
    timestamp: datetime | None = None,
    seed: int | None = None,
    parameters: Mapping[str, Any] | None = None,
) -> int:
    """Persist a typed interaction as an attempt; mastery only changes if scores supplied.

    Raw response data is caller-controlled. Avoid passing sensitive audio/video payloads.
    """
    lesson.validate()
    block = next((b for b in lesson.blocks if b.block_id == block_id), None)
    if block is None:
        raise KeyError(f"unknown block_id: {block_id}")
    if not event_type:
        raise ValueError("event_type is required")
    if hints_used < 0:
        raise ValueError("hints_used cannot be negative")
    if scores is not None:
        if block.kind not in {"assessment", "retrieval", "reflection"}:
            raise ValueError("only assessment, retrieval, or reflection blocks can update mastery")
        unknown = set(scores) - set(MASTERY_DIMENSIONS)
        if unknown:
            raise ValueError(f"unknown mastery dimensions: {sorted(unknown)}")
        if any(not math.isfinite(float(value)) or not 0 <= float(value) <= 1 for value in scores.values()):
            raise ValueError("mastery scores must be finite values between 0 and 1")
    now = timestamp or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    evidence = {
        "event_type": event_type,
        "response": response,
        "timestamp": now.isoformat(),
        "block_kind": block.kind,
        "lesson_version": lesson.version,
        "seed": seed,
        "parameters": dict(parameters or {}),
    }
    # Interaction-only events are persisted with zero-valued evidence in no dimensions.
    # The current LearnerStore requires scores; use an explicit engagement dimension only
    # would pollute mastery, so add an append-only interaction_events table separately.
    with store._connect() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS interaction_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                learner_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                lesson_version INTEGER NOT NULL,
                block_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        cursor = connection.execute(
            """INSERT INTO interaction_events
            (learner_id, lesson_id, lesson_version, block_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (learner_id, lesson.lesson_id, lesson.version, block_id, event_type,
             json.dumps(evidence, sort_keys=True, default=str), now.isoformat()),
        )
        event_id = int(cursor.lastrowid)

    # Mastery is updated only for an explicitly scored assessment event.
    if scores:
            store.record_attempt(
                Attempt(
                    learner_id=learner_id,
                    lesson_id=lesson.lesson_id,
                    task_id=block_id,
                    scores=scores,
                    independent=independent,
                    hints_used=hints_used,
                    outcome=event_type,
                    evidence=evidence,
                ),
                lesson.concept_ids,
            )
    return event_id


def interaction_count(store: LearnerStore, learner_id: str) -> int:
    with store._connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM interaction_events WHERE learner_id=?",
            (learner_id,),
        ).fetchone()
    return int(row[0])
