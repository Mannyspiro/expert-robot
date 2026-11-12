"""Canonical logic and discrete mathematics course loader."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .learning_platform import LearningPlatform

CURRICULUM_ID = "math-logic-discrete-v1"
PATHWAYS = {"mathematician", "mathematics_programmer", "computational_hacker"}
STAGE_MODES = {"concrete", "observation", "visual", "language", "symbol", "code"}
ANSWER_FORMATS = {
    "written_explanation", "table_and_explanation", "conjecture_or_python_code",
    "proof", "python_code_and_tests", "python_experiment_and_explanation",
}


def validate_math_curriculum_manifest(
    manifest: Mapping[str, Any], catalog: Mapping[str, Any], expected_curriculum_id: str
) -> dict[str, Any]:
    if not isinstance(manifest, Mapping) or manifest.get("curriculum_id") != expected_curriculum_id:
        raise ValueError(f"unsupported curriculum: expected {expected_curriculum_id}")
    ideas = catalog.get("ideas") if isinstance(catalog, Mapping) else None
    if not isinstance(ideas, list):
        raise ValueError("canonical idea catalog must contain ideas")
    idea_by_id = {item.get("id"): item for item in ideas if isinstance(item, dict)}
    objectives = manifest["objectives"]
    objective_by_id = {item["id"]: item for item in objectives}
    for objective_id, objective in objective_by_id.items():
        idea = idea_by_id.get(objective_id)
        if idea is None or not isinstance(idea.get("learning"), dict):
            raise ValueError(f"{objective_id}: missing canonical learning metadata")
        learning = idea["learning"]
        if objective.get("dimensions") != learning.get("dimensions"):
            raise ValueError(f"{objective_id}: dimensions differ from canonical idea")
        if objective.get("title") != idea.get("title"):
            raise ValueError(f"{objective_id}: title differs from canonical idea")
        if objective.get("prerequisites") != learning.get("prerequisites"):
            raise ValueError(f"{objective_id}: prerequisites differ from canonical idea")
        external = objective.get("external_prerequisites", [])
        expected_external = [
            prerequisite for prerequisite in learning.get("prerequisites", [])
            if prerequisite not in objective_by_id
        ]
        if set(external) != set(expected_external):
            raise ValueError(f"{objective_id}: external prerequisites must exactly cover prerequisites outside this course")
        for prerequisite in external:
            external_idea = idea_by_id.get(prerequisite)
            if (
                external_idea is None
                or not isinstance(external_idea.get("learning"), dict)
                or not external_idea["learning"].get("lesson_id")
            ):
                raise ValueError(f"{objective_id}: external prerequisite {prerequisite} has no canonical lesson")
        if not isinstance(objective.get("pathways"), list) or set(objective["pathways"]) != PATHWAYS:
            raise ValueError(f"{objective_id}: objective must be assigned to all three pathways")
    # Check canonical metadata before generic reference validation so callers
    # receive the precise catalog-drift error rather than a secondary graph error.
    LearningPlatform._validate_manifest(manifest)
    lesson_ids: set[str] = set()
    task_ids: set[str] = set()
    lesson_by_id = {}
    for lesson in manifest["lessons"]:
        lesson_id = lesson["id"]
        if lesson_id in lesson_ids:
            raise ValueError(f"duplicate lesson ID {lesson_id}")
        lesson_ids.add(lesson_id)
        lesson_by_id[lesson_id] = lesson
        idea = idea_by_id[lesson["objective_id"]]
        if lesson_id != idea["learning"].get("lesson_id"):
            raise ValueError(f"{lesson['objective_id']}: lesson ID differs from canonical catalog")
        if not isinstance(lesson.get("pathways"), list) or set(lesson["pathways"]) != PATHWAYS:
            raise ValueError(f"{lesson_id}: lesson must be assigned to all three pathways")
        stages = lesson.get("stages")
        if not isinstance(stages, list) or not stages or stages[0].get("mode") != "concrete":
            raise ValueError(f"{lesson_id}: first stage must be concrete")
        explored = False
        for stage in stages:
            if stage.get("mode") not in STAGE_MODES or not isinstance(stage.get("prompt"), str) or not stage["prompt"].strip():
                raise ValueError(f"{lesson_id}: malformed stage")
            if stage["mode"] in {"observation", "visual"}:
                explored = True
            if stage["mode"] == "symbol" and not explored:
                raise ValueError(f"{lesson_id}: symbols appear before exploration")
        exercise = lesson.get("exercise")
        if not isinstance(exercise, dict):
            raise ValueError(f"{lesson_id}: exercise is required")
        task_id = exercise.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id in task_ids:
            raise ValueError(f"{lesson_id}: exercise task ID must be unique")
        task_ids.add(task_id)
        if exercise.get("answer_format") not in ANSWER_FORMATS:
            raise ValueError(f"{lesson_id}: unsupported answer format")
        if any(not isinstance(exercise.get(field), str) or not exercise[field].strip()
               for field in ("objective", "prompt", "transfer_prompt")):
            raise ValueError(f"{lesson_id}: objective, prompt and transfer prompt are required")
        hints = exercise.get("hints")
        if not isinstance(hints, list) or len(hints) < 2 or any(not isinstance(x, str) or not x.strip() for x in hints):
            raise ValueError(f"{lesson_id}: at least two progressive hints are required")
        if not isinstance(exercise.get("rubric"), list) or not exercise["rubric"]:
            raise ValueError(f"{lesson_id}: rubric is required")
        exercise_dimensions = set()
        for criterion in exercise["rubric"]:
            if not isinstance(criterion, dict):
                raise ValueError(f"{lesson_id}: malformed exercise rubric")
            dimension = criterion.get("dimension")
            points = criterion.get("points")
            if not isinstance(dimension, str) or not dimension.strip() or dimension in exercise_dimensions:
                raise ValueError(f"{lesson_id}: rubric dimensions must be non-empty and unique")
            if isinstance(points, bool) or not isinstance(points, int) or points < 1:
                raise ValueError(f"{lesson_id}: rubric points must be positive integers")
            if not isinstance(criterion.get("description"), str) or not criterion["description"].strip():
                raise ValueError(f"{lesson_id}: rubric description is required")
            exercise_dimensions.add(dimension)
    if set(objective_by_id) != {lesson["objective_id"] for lesson in manifest["lessons"]}:
        raise ValueError("every objective must have a lesson")
    pathway_modules = {
        "mathematician": "mathematician",
        "mathematics-programmer": "mathematics_programmer",
        "computational-hacker": "computational_hacker",
    }
    covered = set()
    covered_by_pathway = {}
    module_pathways = set()
    for module in manifest["modules"]:
        module_id = module.get("id")
        if module_id not in pathway_modules or module_id in module_pathways:
            raise ValueError(f"unknown or duplicate module {module_id!r}")
        module_pathways.add(module_id)
        pathway = pathway_modules[module_id]
        refs = module.get("lesson_ids")
        if not isinstance(refs, list) or not refs or any(ref not in lesson_ids for ref in refs):
            raise ValueError(f"{module_id}: module must reference known lessons")
        for lesson_id in refs:
            if pathway not in lesson_by_id[lesson_id].get("pathways", []):
                raise ValueError(f"{module_id}: lesson {lesson_id} is not assigned to its pathway")
        covered.update(refs)
        covered_by_pathway[pathway] = set(refs)
    if (set(pathway_modules) != module_pathways or covered != lesson_ids
            or any(covered_by_pathway.get(pathway, set()) != lesson_ids for pathway in PATHWAYS)):
        raise ValueError("all three pathways must cover every lesson")
    assessment_ids = set()
    for assessment in manifest["assessments"]:
        if assessment.get("objective_id") not in objective_by_id:
            raise ValueError("assessment references unknown objective")
        if assessment["objective_id"] in assessment_ids:
            raise ValueError("duplicate assessment for objective")
        assessment_ids.add(assessment["objective_id"])
        if assessment.get("high_stakes") is not False or assessment.get("human_review_required") is not True:
            raise ValueError("course assessments must be low-stakes and human-reviewed")
        rubric = assessment.get("rubric")
        if not isinstance(rubric, list) or not rubric:
            raise ValueError("every assessment requires a versioned rubric")
        seen_dimensions = set()
        for criterion in rubric:
            if not isinstance(criterion, dict):
                raise ValueError("assessment rubric criteria must be objects")
            dimension = criterion.get("dimension")
            points = criterion.get("points")
            if not isinstance(dimension, str) or not dimension.strip() or dimension in seen_dimensions:
                raise ValueError("assessment rubric dimensions must be non-empty and unique")
            if isinstance(points, bool) or not isinstance(points, int) or points < 1:
                raise ValueError("assessment rubric points must be positive integers")
            if not isinstance(criterion.get("description"), str) or not criterion["description"].strip():
                raise ValueError("assessment rubric descriptions are required")
            seen_dimensions.add(dimension)
    if assessment_ids != set(objective_by_id):
        raise ValueError("each objective must have exactly one assessment")
    return {"curriculum_id": expected_curriculum_id, "objective_count": len(objectives),
            "lesson_count": len(lesson_ids), "exercise_count": len(task_ids)}


def validate_math_logic_discrete_manifest(
    manifest: Mapping[str, Any], catalog: Mapping[str, Any]
) -> dict[str, Any]:
    return validate_math_curriculum_manifest(manifest, catalog, CURRICULUM_ID)


def load_math_logic_discrete_manifest(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "docs/merlin/MERLIN_MATH_LOGIC_DISCRETE_COURSE_V1.json").read_text(encoding="utf-8"))
    catalog = json.loads((root / "docs/research/merlin-mathematical-idea-catalog.v1.json").read_text(encoding="utf-8"))
    validate_math_logic_discrete_manifest(manifest, catalog)
    return manifest
