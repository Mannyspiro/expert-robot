#!/usr/bin/env python3
"""Validate the mathematics course portfolio as one canonical prerequisite graph."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from python.merlin.math_foundations_course import load_math_foundations_manifest
from python.merlin.math_logic_discrete_course import load_math_logic_discrete_manifest
from python.merlin.math_algebra_functions_course import load_math_algebra_functions_manifest
from python.merlin.math_calculus_probability_course import load_math_calculus_probability_manifest
from python.merlin.math_numerical_scientific_computing_course import (
    load_math_numerical_scientific_computing_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "docs/research/merlin-mathematical-idea-catalog.v1.json"


def validate_portfolio(
    catalog: Mapping[str, Any], manifests: Sequence[Mapping[str, Any]]
) -> list[str]:
    errors: list[str] = []
    ideas = catalog.get("ideas")
    if not isinstance(ideas, list):
        return ["canonical catalog must contain an ideas array"]
    idea_by_id = {
        item.get("id"): item for item in ideas
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if len(idea_by_id) != len(ideas):
        errors.append("canonical idea IDs must be unique and well formed")

    course_ids: set[str] = set()
    lesson_by_id: dict[str, dict[str, Any]] = {}
    objective_by_id: dict[str, dict[str, Any]] = {}
    objective_course: dict[str, str] = {}

    for manifest in manifests:
        course_id = manifest.get("curriculum_id")
        if not isinstance(course_id, str) or not course_id:
            errors.append("every course manifest requires a curriculum_id")
            continue
        if course_id in course_ids:
            errors.append(f"duplicate curriculum_id: {course_id}")
        course_ids.add(course_id)
        objectives = manifest.get("objectives")
        lessons = manifest.get("lessons")
        if not isinstance(objectives, list) or not isinstance(lessons, list):
            errors.append(f"{course_id}: objectives and lessons must be arrays")
            continue
        local_objectives = {item.get("id") for item in objectives if isinstance(item, dict)}
        for objective in objectives:
            if not isinstance(objective, dict):
                errors.append(f"{course_id}: malformed objective")
                continue
            idea_id = objective.get("id")
            idea = idea_by_id.get(idea_id)
            if idea is None:
                errors.append(f"{course_id}: objective {idea_id!r} is absent from the canonical catalog")
                continue
            learning = idea.get("learning") or {}
            for field in ("title", "dimensions", "prerequisites"):
                canonical_field = "title" if field == "title" else field
                if objective.get(field) != (
                    idea.get("title") if field == "title" else learning.get(canonical_field)
                ):
                    errors.append(f"{course_id}: {idea_id} {field} differs from canonical catalog")
            external = objective.get("external_prerequisites", [])
            expected_external = [
                prerequisite for prerequisite in learning.get("prerequisites", [])
                if prerequisite not in local_objectives
            ]
            if set(external) != set(expected_external):
                errors.append(f"{course_id}: {idea_id} external prerequisite declaration is incomplete or excessive")
            if idea_id in objective_by_id:
                prior = objective_by_id[idea_id]
                if any(prior.get(field) != objective.get(field) for field in ("title", "dimensions", "prerequisites")):
                    errors.append(f"cross-course objective drift for {idea_id}")
            else:
                objective_by_id[idea_id] = objective
                objective_course[idea_id] = course_id

        for lesson in lessons:
            if not isinstance(lesson, dict):
                errors.append(f"{course_id}: malformed lesson")
                continue
            lesson_id = lesson.get("id")
            objective_id = lesson.get("objective_id")
            idea = idea_by_id.get(objective_id)
            if not isinstance(lesson_id, str) or not lesson_id:
                errors.append(f"{course_id}: lesson ID is missing")
                continue
            if idea is None or (idea.get("learning") or {}).get("lesson_id") != lesson_id:
                errors.append(f"{course_id}: lesson {lesson_id} is not the canonical lesson for {objective_id}")
            previous = lesson_by_id.get(lesson_id)
            if previous is not None and previous != lesson:
                errors.append(f"lesson ID {lesson_id} has divergent content across course manifests")
            else:
                lesson_by_id[lesson_id] = dict(lesson)

    for idea_id, objective in objective_by_id.items():
        course_id = objective_course[idea_id]
        for prerequisite in objective.get("external_prerequisites", []):
            prerequisite_idea = idea_by_id.get(prerequisite)
            if prerequisite_idea is None:
                errors.append(f"{course_id}: external prerequisite {prerequisite} is unknown")
                continue
            lesson_id = (prerequisite_idea.get("learning") or {}).get("lesson_id")
            if not lesson_id or lesson_id not in lesson_by_id:
                errors.append(
                    f"{course_id}: external prerequisite {prerequisite} has no lesson in the authored course portfolio"
                )

    if not manifests:
        errors.append("course portfolio is empty")
    return errors


def load_portfolio() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    manifests = [
        load_math_foundations_manifest(),
        load_math_logic_discrete_manifest(),
        load_math_algebra_functions_manifest(),
        load_math_calculus_probability_manifest(),
        load_math_numerical_scientific_computing_manifest(),
    ]
    return catalog, manifests


def main() -> int:
    catalog, manifests = load_portfolio()
    errors = validate_portfolio(catalog, manifests)
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    objective_count = len({
        objective["id"]
        for manifest in manifests
        for objective in manifest.get("objectives", [])
    })
    lesson_count = len({
        lesson["id"]
        for manifest in manifests
        for lesson in manifest.get("lessons", [])
    })
    print(
        f"Merlin mathematics portfolio valid: {len(manifests)} courses, "
        f"{objective_count} unique objectives, {lesson_count} unique lesson IDs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
