"""Server-owned learner-facing API for canonical zero-first mathematics lessons.

The loopback MVP intentionally exposes one local learner identity per server
instance. Browser requests cannot select another learner_id or submit lesson
definitions. Progress is not assessment evidence and never grants mastery.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .learning_core import LearnerStore, LessonSession, parrondo_lesson_for_path


ALLOWED_PATHS = frozenset({
    "mathematician", "mathematics_programmer", "computational_hacker",
})


class MathLearningService:
    def __init__(self, database: str | Path, *, learner_id: str = "local-default") -> None:
        if not learner_id or len(learner_id) > 128:
            raise ValueError("server learner identity must be non-empty and at most 128 characters")
        self.store = LearnerStore(database)
        self.learner_id = learner_id

    @staticmethod
    def _lesson(path: Any):
        if not isinstance(path, str) or path not in ALLOWED_PATHS:
            raise ValueError("path must be one of the canonical mathematics learning paths")
        return parrondo_lesson_for_path(path)

    def snapshot(self, path: str = "mathematician") -> dict[str, Any]:
        lesson = self._lesson(path)
        session = self.store.load_lesson_session(self.learner_id, lesson) or LessonSession(lesson)
        current = session.current_stage
        return {
            "schema": "merlin-math-lesson-session/1",
            "lesson": {
                "id": lesson.lesson_id,
                "title": lesson.title,
                "path": path,
                "target_concepts": list(lesson.target_concepts),
                "stages": [
                    {"id": stage.stage_id, "mode": stage.mode,
                     "prompt": stage.learner_prompt,
                     "introduces_symbols": stage.introduces_symbols}
                    for stage in lesson.stages
                ],
            },
            "progress": {
                "stage_index": session.stage_index,
                "completed_stage_ids": list(session.completed_stage_ids),
                "current_stage": (
                    {"id": current.stage_id, "mode": current.mode,
                     "prompt": current.learner_prompt,
                     "introduces_symbols": current.introduces_symbols}
                    if current else None
                ),
                "is_complete": session.is_complete,
            },
            "assessment": {
                "mastery_awarded": False,
                "attempt_count": self.store.attempt_count(self.learner_id),
                "authority": "lesson_progress_is_not_assessment_evidence",
            },
        }

    def complete_stage(self, path: str, stage_id: Any) -> dict[str, Any]:
        if not isinstance(stage_id, str) or not stage_id:
            raise ValueError("stage_id must be a non-empty string")
        lesson = self._lesson(path)
        session = self.store.load_lesson_session(self.learner_id, lesson) or LessonSession(lesson)
        session.complete_current_stage(stage_id)
        self.store.save_lesson_session(self.learner_id, session)
        return self.snapshot(path)
