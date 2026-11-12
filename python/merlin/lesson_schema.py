"""Typed, zero-first lesson document schema and validation.

The document format is UI-framework neutral. Rendering is a separate adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

BLOCK_TYPES = frozenset({
    "story", "manipulative", "choice", "simulation", "chart",
    "explanation", "reflection", "retrieval", "assessment",
})
PATHS = frozenset({"mathematician", "mathematics_programmer", "computational_hacker"})


@dataclass(frozen=True)
class LessonBlock:
    block_id: str
    kind: str
    content: Mapping[str, Any] = field(default_factory=dict)
    introduces_symbols: bool = False

    def validate(self) -> None:
        if not self.block_id:
            raise ValueError("block_id is required")
        if self.kind not in BLOCK_TYPES:
            raise ValueError(f"unsupported block kind: {self.kind}")
        if not isinstance(self.content, Mapping):
            raise ValueError("block content must be a mapping")
        if self.kind == "simulation":
            if "engine" not in self.content or "parameters" not in self.content:
                raise ValueError("simulation blocks require engine and parameters")
            seed = self.content.get("seed")
            if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
                raise ValueError("simulation seed must be an integer")
        if self.kind == "choice" and not self.content.get("options"):
            raise ValueError("choice blocks require options")
        if self.kind == "chart" and not self.content.get("series"):
            raise ValueError("chart blocks require series")


@dataclass(frozen=True)
class LessonDocument:
    lesson_id: str
    version: int
    title: str
    concept_ids: tuple[str, ...]
    prerequisites: tuple[str, ...]
    path_tags: tuple[str, ...]
    blocks: tuple[LessonBlock, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self, known_concepts: Sequence[str] | None = None) -> None:
        if not self.lesson_id or not self.title:
            raise ValueError("lesson_id and title are required")
        if self.version < 1:
            raise ValueError("lesson version must be positive")
        if not self.concept_ids:
            raise ValueError("at least one concept is required")
        if not self.blocks:
            raise ValueError("lesson requires blocks")
        if not self.path_tags or not set(self.path_tags) <= PATHS:
            raise ValueError("path_tags must contain supported learning paths")
        if known_concepts is not None:
            unknown = set(self.concept_ids + self.prerequisites) - set(known_concepts)
            if unknown:
                raise ValueError(f"unknown concept ids: {sorted(unknown)}")
        ids = [block.block_id for block in self.blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("block ids must be unique")
        for block in self.blocks:
            block.validate()

        # First instructional block must establish concrete experience.
        instructional = [b for b in self.blocks if b.kind not in {"assessment", "retrieval"}]
        if not instructional or instructional[0].kind not in {"story", "manipulative"}:
            raise ValueError("zero-first lessons must begin with a story or manipulative")
        first_symbol = next((i for i, b in enumerate(self.blocks) if b.introduces_symbols), None)
        if first_symbol is not None:
            prior = self.blocks[:first_symbol]
            if not any(b.kind in {"manipulative", "simulation", "chart"} for b in prior):
                raise ValueError("symbolic notation requires prior concrete or visual exploration")
        if any(b.kind == "assessment" for b in self.blocks[:1]):
            raise ValueError("assessment cannot precede instruction")


def lesson_to_dict(lesson: LessonDocument) -> dict[str, Any]:
    lesson.validate()
    return {
        "lesson_id": lesson.lesson_id,
        "version": lesson.version,
        "title": lesson.title,
        "concept_ids": list(lesson.concept_ids),
        "prerequisites": list(lesson.prerequisites),
        "path_tags": list(lesson.path_tags),
        "metadata": dict(lesson.metadata),
        "blocks": [
            {
                "block_id": block.block_id,
                "kind": block.kind,
                "content": dict(block.content),
                "introduces_symbols": block.introduces_symbols,
            }
            for block in lesson.blocks
        ],
    }
