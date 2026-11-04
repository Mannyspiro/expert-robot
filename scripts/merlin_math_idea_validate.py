#!/usr/bin/env python3
"""Validate Merlin's durable mathematical idea catalog using only the stdlib."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

STATUSES = {
    "candidate", "literature_checked", "counterexample_checked", "finite_tested",
    "formalized", "supported", "refuted", "unresolved",
}
KINDS = {
    "concept", "representation", "transformation", "conjecture", "theorem",
    "experiment", "engineering_mapping", "open_question",
}
RELATIONS = {
    "generalizes", "specializes", "depends_on", "equivalent_under", "maps_to",
    "contrasts_with", "tested_by", "formalized_by", "implemented_by",
    "applies_to", "motivated_by",
}
REQUIRED = {
    "id", "title", "kind", "claim", "definitions", "assumptions", "status",
    "provenance", "relations", "objections", "next_steps",
}


def validate_catalog(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["catalog root must be an object"]
    if data.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    ideas = data.get("ideas")
    if not isinstance(ideas, list):
        return errors + ["ideas must be an array"]
    ids: set[str] = set()
    for index, idea in enumerate(ideas):
        prefix = f"ideas[{index}]"
        if not isinstance(idea, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED - idea.keys()
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(sorted(missing))}")
            continue
        ident = idea["id"]
        if not isinstance(ident, str) or not ident.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        elif ident in ids:
            errors.append(f"duplicate idea id: {ident}")
        else:
            ids.add(ident)
        if idea["kind"] not in KINDS:
            errors.append(f"{prefix}.kind is not recognized: {idea['kind']}")
        if idea["status"] not in STATUSES:
            errors.append(f"{prefix}.status is not recognized: {idea['status']}")
        for field in ("title", "claim"):
            if not isinstance(idea[field], str) or not idea[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        for field in ("definitions", "assumptions", "provenance", "relations", "objections", "next_steps"):
            if not isinstance(idea[field], list):
                errors.append(f"{prefix}.{field} must be an array")
        for j, relation in enumerate(idea["relations"] if isinstance(idea["relations"], list) else []):
            if not isinstance(relation, dict) or set(relation) != {"type", "target"}:
                errors.append(f"{prefix}.relations[{j}] must contain exactly type and target")
                continue
            if relation["type"] not in RELATIONS:
                errors.append(f"{prefix}.relations[{j}] has unknown relation type")
    # Resolve edges after collecting all IDs, allowing forward references.
    for index, idea in enumerate(ideas):
        if not isinstance(idea, dict) or not isinstance(idea.get("relations"), list):
            continue
        for j, relation in enumerate(idea["relations"]):
            if isinstance(relation, dict) and isinstance(relation.get("target"), str):
                if relation["target"] not in ids:
                    errors.append(f"ideas[{index}].relations[{j}] targets missing id: {relation['target']}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "catalog",
        nargs="?",
        default="docs/research/merlin-mathematical-idea-catalog.v1.json",
    )
    args = parser.parse_args()
    path = Path(args.catalog)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"catalog read error: {exc}")
        return 2
    errors = validate_catalog(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {len(data['ideas'])} mathematical ideas; IDs and typed links valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
