"""Canonical numerical methods and scientific computing course loader."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .math_logic_discrete_course import validate_math_curriculum_manifest

CURRICULUM_ID = "math-numerical-scientific-computing-v1"


def validate_math_numerical_scientific_computing_manifest(
    manifest: Mapping[str, Any], catalog: Mapping[str, Any]
) -> dict[str, Any]:
    return validate_math_curriculum_manifest(manifest, catalog, CURRICULUM_ID)


def load_math_numerical_scientific_computing_manifest(
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    manifest = json.loads(
        (root / "docs/merlin/MERLIN_MATH_NUMERICAL_SCIENTIFIC_COMPUTING_COURSE_V1.json").read_text(encoding="utf-8")
    )
    catalog = json.loads(
        (root / "docs/research/merlin-mathematical-idea-catalog.v1.json").read_text(encoding="utf-8")
    )
    validate_math_numerical_scientific_computing_manifest(manifest, catalog)
    return manifest
