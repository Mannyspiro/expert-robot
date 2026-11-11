#!/usr/bin/env python3
"""Validate review-gated mathematics lesson blueprints against the canonical idea graph."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/research/merlin-mathematical-idea-catalog.v1.json"
BACKLOG = ROOT / "docs/merlin/MERLIN_MATH_LESSON_BACKLOG_V1.json"
PATHWAYS = {"mathematician", "mathematics_programmer", "computational_hacker"}
MODES = ["concrete", "observation", "visual", "language", "symbol", "code"]


def read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def validate(catalog: dict[str, Any], backlog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ideas = catalog.get("ideas")
    blueprints = backlog.get("blueprints")
    if not isinstance(ideas, list) or not isinstance(blueprints, list):
        return ["catalog ideas and backlog blueprints must be arrays"]
    if backlog.get("schema") != "merlin-math-lesson-backlog/1":
        errors.append("unsupported lesson backlog schema")
    if backlog.get("catalog_id") != catalog.get("catalog_id"):
        errors.append("lesson backlog catalog identity mismatch")
    if backlog.get("catalog_schema") != catalog.get("schema_version"):
        errors.append("lesson backlog catalog schema mismatch")

    idea_by_id = {idea.get("id"): idea for idea in ideas if isinstance(idea, dict)}
    if len(idea_by_id) != len(ideas):
        errors.append("canonical idea IDs must be unique and well-formed")
    expected = {
        idea_id for idea_id, idea in idea_by_id.items()
        if not isinstance(idea.get("learning"), dict)
        or not idea["learning"].get("lesson_id")
    }
    seen: set[str] = set()
    blueprint_ids: set[str] = set()
    task_ids: set[str] = set()
    for blueprint in blueprints:
        if not isinstance(blueprint, dict):
            errors.append("blueprint must be an object")
            continue
        idea_id = blueprint.get("idea_id")
        if not isinstance(idea_id, str) or idea_id not in idea_by_id:
            errors.append(f"blueprint references unknown idea: {idea_id!r}")
            continue
        if idea_id in seen:
            errors.append(f"duplicate blueprint for {idea_id}")
        seen.add(idea_id)
        idea = idea_by_id[idea_id]
        bid = blueprint.get("blueprint_id")
        if not isinstance(bid, str) or not bid or bid in blueprint_ids:
            errors.append(f"{idea_id}: blueprint_id must be unique")
        blueprint_ids.add(bid)
        if blueprint.get("title") != idea.get("title"):
            errors.append(f"{idea_id}: title differs from canonical idea")
        for field in ("kind", "catalog_status"):
            if blueprint.get(field) != idea.get("kind" if field == "kind" else "status"):
                errors.append(f"{idea_id}: {field} differs from canonical idea")
        if blueprint.get("source_claim") != idea.get("claim"):
            errors.append(f"{idea_id}: source claim drift")
        if blueprint.get("definitions") != idea.get("definitions", []):
            errors.append(f"{idea_id}: definition drift")
        if blueprint.get("assumptions") != idea.get("assumptions", []):
            errors.append(f"{idea_id}: assumption drift")
        if blueprint.get("known_objections") != idea.get("objections", []):
            errors.append(f"{idea_id}: objection drift")
        prereqs = (idea.get("learning") or {}).get("prerequisites", [])
        if blueprint.get("prerequisite_idea_ids") != prereqs:
            errors.append(f"{idea_id}: prerequisite drift")
        if not isinstance(blueprint.get("pathways"), list) or not blueprint["pathways"] or not set(blueprint["pathways"]) <= PATHWAYS:
            errors.append(f"{idea_id}: pathway list is missing or invalid")
        if not isinstance(blueprint.get("skill_dimensions"), list) or not blueprint["skill_dimensions"]:
            errors.append(f"{idea_id}: skill dimensions are required")
        if blueprint.get("review_required") is not True:
            errors.append(f"{idea_id}: instructor review must remain required")
        if blueprint.get("delivery_state") not in {"instructional_candidate", "research_laboratory", "audit_only"}:
            errors.append(f"{idea_id}: invalid delivery_state")
        if idea.get("status") == "refuted":
            if blueprint.get("delivery_state") != "audit_only":
                errors.append(f"{idea_id}: refuted idea must remain audit_only")
            if "never present" not in blueprint.get("epistemic_guardrail", ""):
                errors.append(f"{idea_id}: refutation guardrail missing")
        if idea.get("status") != "refuted" and (idea.get("kind") in {"open_question", "conjecture"} or idea.get("status") == "unresolved"):
            if blueprint.get("delivery_state") != "research_laboratory":
                errors.append(f"{idea_id}: open or unresolved idea must remain research_laboratory")
        stages = blueprint.get("stages")
        if not isinstance(stages, list) or [s.get("mode") for s in stages if isinstance(s, dict)] != MODES:
            errors.append(f"{idea_id}: lesson stages must follow the concrete-to-code sequence")
        exercise = blueprint.get("exercise")
        if not isinstance(exercise, dict):
            errors.append(f"{idea_id}: exercise is required")
            continue
        task = exercise.get("task_id")
        if not isinstance(task, str) or not task or task in task_ids:
            errors.append(f"{idea_id}: exercise task ID must be unique")
        task_ids.add(task)
        for field in ("objective", "prompt", "answer_format", "transfer_prompt"):
            if not isinstance(exercise.get(field), str) or not exercise[field].strip():
                errors.append(f"{idea_id}: exercise {field} is required")
        if exercise.get("answer_format") != "written_explanation":
            errors.append(f"{idea_id}: unsupported blueprint answer format")
        if len(exercise.get("hints", [])) < 2 or not exercise.get("rubric"):
            errors.append(f"{idea_id}: progressive hints and rubric are required")
        tasks = blueprint.get("pathway_tasks", {})
        if set(tasks) != PATHWAYS:
            errors.append(f"{idea_id}: pathway-specific tasks must cover all three pathways")

    if seen != expected:
        errors.append(
            "blueprint coverage mismatch; missing=" + ",".join(sorted(expected - seen))
            + "; unexpected=" + ",".join(sorted(seen - expected))
        )
    if backlog.get("blueprint_count") != len(blueprints):
        errors.append("blueprint_count metadata does not match actual records")
    if backlog.get("generated_from_catalog_count") != len(ideas):
        errors.append("generated_from_catalog_count metadata is stale")
    return errors


def main() -> int:
    errors = validate(read(CATALOG), read(BACKLOG))
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    backlog = read(BACKLOG)
    print(f"Merlin math lesson backlog valid: {backlog['blueprint_count']} review-gated blueprints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
