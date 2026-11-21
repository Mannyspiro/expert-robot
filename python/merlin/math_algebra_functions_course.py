"""Canonical algebra and functions course loader."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .math_logic_discrete_course import validate_math_curriculum_manifest

CURRICULUM_ID = "math-algebra-functions-v1"


def validate_math_algebra_functions_manifest(
    manifest: Mapping[str, Any], catalog: Mapping[str, Any]
) -> dict[str, Any]:
    return validate_math_curriculum_manifest(manifest, catalog, CURRICULUM_ID)


def load_math_algebra_functions_manifest(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "docs/merlin/MERLIN_MATH_ALGEBRA_FUNCTIONS_COURSE_V1.json").read_text(encoding="utf-8"))
    catalog = json.loads((root / "docs/research/merlin-mathematical-idea-catalog.v1.json").read_text(encoding="utf-8"))
    validate_math_algebra_functions_manifest(manifest, catalog)
    return manifest
