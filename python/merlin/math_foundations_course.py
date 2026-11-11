"""Canonical math foundations course loader and graph consistency checks."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .learning_platform import LearningPlatform

CURRICULUM_ID = "math-foundations-v1"
PATHWAYS = frozenset({
    "mathematician",
    "mathematics_programmer",
    "computational_hacker",
})
STAGE_MODES = frozenset({"concrete", "observation", "visual", "language", "symbol", "code"})


def validate_math_foundations_manifest(
    manifest: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the course manifest against both platform and idea-catalog contracts."""
    if not isinstance(manifest, Mapping):
        raise ValueError("math foundations manifest must be an object")
    if manifest.get("curriculum_id") != CURRICULUM_ID:
        raise ValueError("unsupported math foundations curriculum_id")
    LearningPlatform._validate_manifest(manifest)

    ideas = catalog.get("ideas") if isinstance(catalog, Mapping) else None
    if not isinstance(ideas, list):
        raise ValueError("canonical math idea catalog must contain an ideas array")
    idea_by_id = {
        idea.get("id"): idea for idea in ideas
        if isinstance(idea, dict) and isinstance(idea.get("id"), str)
    }

    objectives = manifest["objectives"]
    objective_by_id = {item["id"]: item for item in objectives}
    for objective_id, objective in objective_by_id.items():
        idea = idea_by_id.get(objective_id)
        if idea is None:
            raise ValueError(f"{objective_id}: missing from canonical mathematical idea catalog")
        learning = idea.get("learning")
        if not isinstance(learning, dict):
            raise ValueError(f"{objective_id}: canonical idea has no learning metadata")
        if objective.get("dimensions") != learning.get("dimensions"):
            raise ValueError(f"{objective_id}: objective dimensions differ from canonical learning metadata")
        if objective.get("prerequisites") != learning.get("prerequisites"):
            raise ValueError(f"{objective_id}: objective prerequisites differ from canonical learning metadata")

    lesson_ids: set[str] = set()
    task_ids: set[str] = set()
    lessons_by_objective: dict[str, int] = {}
    for lesson in manifest["lessons"]:
        lesson_id = lesson["id"]
        if lesson_id in lesson_ids:
            raise ValueError(f"duplicate lesson id: {lesson_id}")
        lesson_ids.add(lesson_id)
        objective_id = lesson["objective_id"]
        lessons_by_objective[objective_id] = lessons_by_objective.get(objective_id, 0) + 1
        idea_learning = idea_by_id[objective_id]["learning"]
        if lesson_id != idea_learning.get("lesson_id"):
            raise ValueError(f"{objective_id}: lesson id differs from canonical learning metadata")

        pathways = lesson.get("pathways")
        if not isinstance(pathways, list) or not pathways or any(
            not isinstance(path, str) or path not in PATHWAYS for path in pathways
        ):
            raise ValueError(f"{lesson_id}: pathways must contain known learning paths")
        interests = lesson.get("interest_tags", [])
        if not isinstance(interests, list) or any(not isinstance(tag, str) or not tag for tag in interests):
            raise ValueError(f"{lesson_id}: interest_tags must be non-empty strings")
        minutes = lesson.get("estimated_minutes")
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 1:
            raise ValueError(f"{lesson_id}: estimated_minutes must be a positive integer")

        stages = lesson.get("stages")
        if not isinstance(stages, list) or not stages:
            raise ValueError(f"{lesson_id}: stages must be a non-empty array")
        if stages[0].get("mode") != "concrete":
            raise ValueError(f"{lesson_id}: first stage must be concrete")
        seen_exploration = False
        for stage in stages:
            if not isinstance(stage, dict) or stage.get("mode") not in STAGE_MODES:
                raise ValueError(f"{lesson_id}: invalid lesson stage")
            if not isinstance(stage.get("prompt"), str) or not stage["prompt"].strip():
                raise ValueError(f"{lesson_id}: every stage requires a prompt")
            if stage["mode"] in {"observation", "visual"}:
                seen_exploration = True
            if stage["mode"] == "symbol" and not seen_exploration:
                raise ValueError(f"{lesson_id}: symbolic notation precedes exploration")

        exercise = lesson.get("exercise")
        if not isinstance(exercise, dict):
            raise ValueError(f"{lesson_id}: exercise content is required")
        task_id = exercise.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id in task_ids:
            raise ValueError(f"{lesson_id}: exercise task_id must be unique and non-empty")
        task_ids.add(task_id)
        for field in ("objective", "prompt", "answer_format", "transfer_prompt"):
            if not isinstance(exercise.get(field), str) or not exercise[field].strip():
                raise ValueError(f"{lesson_id}: exercise {field} is required")
        hints = exercise.get("hints")
        if not isinstance(hints, list) or len(hints) < 2 or any(
            not isinstance(hint, str) or not hint.strip() for hint in hints
        ):
            raise ValueError(f"{lesson_id}: at least two progressive hints are required")
        rubric = exercise.get("rubric")
        if not isinstance(rubric, list) or not rubric:
            raise ValueError(f"{lesson_id}: rubric is required")
        dimensions: set[str] = set()
        for criterion in rubric:
            if not isinstance(criterion, dict):
                raise ValueError(f"{lesson_id}: rubric criterion must be an object")
            dimension = criterion.get("dimension")
            points = criterion.get("points")
            if not isinstance(dimension, str) or not dimension or dimension in dimensions:
                raise ValueError(f"{lesson_id}: rubric dimensions must be unique")
            if isinstance(points, bool) or not isinstance(points, int) or points < 1:
                raise ValueError(f"{lesson_id}: rubric points must be positive integers")
            if not isinstance(criterion.get("description"), str) or not criterion["description"].strip():
                raise ValueError(f"{lesson_id}: rubric description is required")
            dimensions.add(dimension)

    missing_lessons = sorted(set(objective_by_id) - set(lessons_by_objective))
    if missing_lessons:
        raise ValueError(f"objectives missing lessons: {missing_lessons}")

    # Validate the prerequisite graph independently of the platform's reference checks.
    indegree = {
        objective_id: len(set(objective.get("prerequisites", [])))
        for objective_id, objective in objective_by_id.items()
    }
    dependents = {objective_id: [] for objective_id in objective_by_id}
    for objective_id, objective in objective_by_id.items():
        for prerequisite in set(objective.get("prerequisites", [])):
            dependents[prerequisite].append(objective_id)
    ready = sorted(key for key, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for dependent in sorted(dependents[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
                ready.sort()
    if len(order) != len(objective_by_id):
        raise ValueError("math foundations prerequisite graph contains a cycle")

    for module in manifest["modules"]:
        if not isinstance(module, dict):
            raise ValueError("course modules must be objects")
        lesson_refs = module.get("lesson_ids", [])
        if not isinstance(lesson_refs, list) or any(ref not in lesson_ids for ref in lesson_refs):
            raise ValueError(f"module {module.get('id')!r} references an unknown lesson")

    return {
        "curriculum_id": CURRICULUM_ID,
        "objective_order": order,
        "objective_count": len(objectives),
        "lesson_count": len(lesson_ids),
        "exercise_count": len(task_ids),
    }


def load_math_foundations_manifest(repo_root: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the packaged-in-repository course and canonical idea catalog."""
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    manifest_path = root / "docs" / "merlin" / "MERLIN_MATH_FOUNDATIONS_COURSE_V1.json"
    catalog_path = root / "docs" / "research" / "merlin-mathematical-idea-catalog.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    validate_math_foundations_manifest(manifest, catalog)
    return manifest
