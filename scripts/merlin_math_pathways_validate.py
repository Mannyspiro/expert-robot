#!/usr/bin/env python3
"""Validate the machine-readable Merlin mathematics pathway map."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "docs/research/merlin-mathematical-idea-catalog.v1.json"
PATHWAYS_PATH = ROOT / "docs/merlin/MERLIN_MATH_LEARNING_PATHWAYS_V1.json"
EXPECTED_PATHWAYS = {"mathematician", "mathematics_programmer", "computational_hacker"}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def validate(catalog: dict[str, Any], plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ideas = catalog.get("ideas")
    pathways = plan.get("pathways")
    index = plan.get("idea_index")
    if not isinstance(ideas, list) or not isinstance(pathways, list) or not isinstance(index, list):
        return ["catalog ideas, pathways, and idea_index must be arrays"]
    if plan.get("schema") != "merlin-math-learning-pathways/1":
        errors.append("unsupported pathways schema")
    if plan.get("catalog_id") != catalog.get("catalog_id"):
        errors.append("pathway map points to a different idea catalog")
    if plan.get("catalog_schema") != catalog.get("schema_version"):
        errors.append("pathway map catalog schema does not match canonical catalog")

    idea_by_id: dict[str, dict[str, Any]] = {}
    for idea in ideas:
        if not isinstance(idea, dict) or not isinstance(idea.get("id"), str):
            errors.append("every catalog idea must have a string ID")
            continue
        if idea["id"] in idea_by_id:
            errors.append(f"duplicate catalog idea ID: {idea['id']}")
        idea_by_id[idea["id"]] = idea

    pathway_by_id: dict[str, dict[str, Any]] = {}
    for pathway in pathways:
        if not isinstance(pathway, dict) or not isinstance(pathway.get("id"), str):
            errors.append("every pathway must have a string ID")
            continue
        if pathway["id"] in pathway_by_id:
            errors.append(f"duplicate pathway ID: {pathway['id']}")
        pathway_by_id[pathway["id"]] = pathway
    if set(pathway_by_id) != EXPECTED_PATHWAYS:
        errors.append("pathways must be exactly mathematician, mathematics_programmer, and computational_hacker")

    assigned: dict[str, set[str]] = {key: set() for key in pathway_by_id}
    for pathway_id, pathway in pathway_by_id.items():
        stages = pathway.get("stages")
        if not isinstance(stages, list) or not stages:
            errors.append(f"{pathway_id} must contain at least one stage")
            continue
        stage_ids: set[str] = set()
        for stage in stages:
            if not isinstance(stage, dict) or not isinstance(stage.get("id"), str):
                errors.append(f"{pathway_id} contains a malformed stage")
                continue
            if stage["id"] in stage_ids:
                errors.append(f"{pathway_id} has duplicate stage ID {stage['id']}")
            stage_ids.add(stage["id"])
            idea_ids = stage.get("idea_ids")
            if not isinstance(idea_ids, list) or not idea_ids:
                errors.append(f"{pathway_id}/{stage['id']} must reference ideas")
                continue
            if len(set(idea_ids)) != len(idea_ids):
                errors.append(f"{pathway_id}/{stage['id']} repeats an idea ID")
            for idea_id in idea_ids:
                if idea_id not in idea_by_id:
                    errors.append(f"{pathway_id}/{stage['id']} references unknown idea {idea_id}")
                assigned[pathway_id].add(idea_id)

    expected_assignments = {
        idea_id: [pathway_id for pathway_id, ids in assigned.items() if idea_id in ids]
        for idea_id in idea_by_id
    }
    if set(expected_assignments) != set(idea_by_id):
        errors.append("pathway assignment construction failed")
    missing = sorted(idea_id for idea_id, owners in expected_assignments.items() if not owners)
    if missing:
        errors.append("unassigned catalog ideas: " + ", ".join(missing))

    index_by_id: dict[str, dict[str, Any]] = {}
    for item in index:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            errors.append("idea_index contains a malformed record")
            continue
        if item["id"] in index_by_id:
            errors.append(f"duplicate idea_index ID: {item['id']}")
        index_by_id[item["id"]] = item
    if set(index_by_id) != set(idea_by_id):
        errors.append("idea_index must contain each canonical idea exactly once")

    for idea_id, idea in idea_by_id.items():
        item = index_by_id.get(idea_id)
        if item is None:
            continue
        if item.get("title") != idea.get("title") or item.get("kind") != idea.get("kind"):
            errors.append(f"idea_index title/kind drift for {idea_id}")
        lesson_id = (idea.get("learning") or {}).get("lesson_id")
        if item.get("lesson_id") != lesson_id:
            errors.append(f"lesson reference drift for {idea_id}")
        expected_state = "lesson_reference_present" if lesson_id else "lesson_not_yet_linked"
        if item.get("lesson_state") != expected_state:
            errors.append(f"lesson state drift for {idea_id}")
        if item.get("pathways") != expected_assignments.get(idea_id):
            errors.append(f"pathway assignment drift for {idea_id}")

    prerequisites = {
        idea_id: list((idea.get("learning") or {}).get("prerequisites") or [])
        for idea_id, idea in idea_by_id.items()
    }
    for idea_id, required in prerequisites.items():
        if len(set(required)) != len(required):
            errors.append(f"duplicate prerequisites for {idea_id}")
        for prerequisite in required:
            if prerequisite not in idea_by_id:
                errors.append(f"{idea_id} requires unknown idea {prerequisite}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(idea_id: str) -> None:
        if idea_id in visiting:
            errors.append(f"learning prerequisite cycle includes {idea_id}")
            return
        if idea_id in visited:
            return
        visiting.add(idea_id)
        for prerequisite in prerequisites.get(idea_id, []):
            if prerequisite in prerequisites:
                visit(prerequisite)
        visiting.remove(idea_id)
        visited.add(idea_id)

    for idea_id in sorted(prerequisites):
        visit(idea_id)
    return errors


def main() -> int:
    errors = validate(_read(CATALOG_PATH), _read(PATHWAYS_PATH))
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    catalog = _read(CATALOG_PATH)
    print(f"Merlin math pathways valid: {len(catalog['ideas'])} canonical ideas mapped across 3 pathways.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
