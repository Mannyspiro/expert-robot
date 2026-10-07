#!/usr/bin/env python3
"""Compile Magick IR geometry into deterministic exact rational geometry.

The compiler is intentionally fail-closed:
- no floating-point geometry is emitted;
- no missing coordinates are guessed;
- no manuscript visual features are reconstructed;
- unsupported formal primitive types are marked, not silently coerced.

The output is suitable for CACE ingestion and for subsequent lowering into the
Lean MathAI.Geometry exact kernel.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any


LEAN_FORMAL_TYPES = {"Point3", "Line3", "Sphere3", "Circle3"}


class CompileError(ValueError):
    pass


def _fraction(value: Any, label: str) -> Fraction:
    if isinstance(value, bool):
        raise CompileError(f"{label}: boolean is not a numeric coordinate")
    if isinstance(value, Decimal):
        return Fraction(value)
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, str):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise CompileError(f"{label}: invalid exact rational {value!r}") from exc
    raise CompileError(
        f"{label}: expected integer, decimal, or rational string; got {type(value).__name__}"
    )


def _q(value: Any, label: str) -> str:
    f = _fraction(value, label)
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def _vec3(values: Any, label: str) -> list[str]:
    if not isinstance(values, list) or len(values) != 3:
        raise CompileError(f"{label}: expected exactly three coordinates")
    return [_q(v, f"{label}[{i}]") for i, v in enumerate(values)]


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _compile_primitive(primitive: dict[str, Any]) -> dict[str, Any]:
    kind = primitive.get("type")
    ident = primitive.get("id")
    params = primitive.get("parameters")
    if not isinstance(ident, str) or not ident:
        raise CompileError("geometry primitive is missing a nonempty id")
    if not isinstance(params, dict):
        raise CompileError(f"{ident}: parameters must be an object")

    if kind == "point":
        xyz = params.get("xyz_m", params.get("point"))
        return {
            "id": ident,
            "source_type": kind,
            "exact_type": "Point3",
            "lean_formalized": True,
            "point": _vec3(xyz, f"{ident}.xyz"),
        }

    if kind == "line":
        return {
            "id": ident,
            "source_type": kind,
            "exact_type": "Line3",
            "lean_formalized": True,
            "point": _vec3(params.get("point"), f"{ident}.point"),
            "direction": _vec3(params.get("direction"), f"{ident}.direction"),
        }

    if kind == "sphere":
        center = _vec3(params.get("center"), f"{ident}.center")
        radius = _fraction(params.get("radius_m"), f"{ident}.radius_m")
        if radius < 0:
            raise CompileError(f"{ident}: radius_m must be nonnegative")
        return {
            "id": ident,
            "source_type": kind,
            "exact_type": "Sphere3",
            "lean_formalized": True,
            "center": center,
            "radiusSquared": _q(radius * radius, f"{ident}.radiusSquared"),
        }

    if kind == "circle":
        center = _vec3(params.get("center"), f"{ident}.center")
        normal = _vec3(params.get("normal"), f"{ident}.normal")
        if all(Fraction(x) == 0 for x in normal):
            raise CompileError(f"{ident}: circle normal must be nonzero")
        radius = _fraction(params.get("radius_m"), f"{ident}.radius_m")
        if radius < 0:
            raise CompileError(f"{ident}: radius_m must be nonnegative")
        return {
            "id": ident,
            "source_type": kind,
            "exact_type": "Circle3",
            "lean_formalized": True,
            "center": center,
            "normal": normal,
            "radiusSquared": _q(radius * radius, f"{ident}.radiusSquared"),
        }

    if kind == "polygon":
        vertices = params.get("vertices")
        if not isinstance(vertices, list) or len(vertices) < 3:
            raise CompileError(f"{ident}: polygon requires at least three vertices")
        return {
            "id": ident,
            "source_type": kind,
            "exact_type": "Polygon3ExactVertices",
            "lean_formalized": False,
            "vertices": [
                _vec3(v, f"{ident}.vertices[{i}]")
                for i, v in enumerate(vertices)
            ],
            "formal_gap": "Polygon3 is not yet a first-class MathAI.Geometry Lean type",
        }

    if kind == "glyph_path":
        points = params.get("points")
        if not isinstance(points, list) or len(points) < 2:
            raise CompileError(
                f"{ident}: glyph_path requires explicit points; image-only paths are not reconstructed"
            )
        return {
            "id": ident,
            "source_type": kind,
            "exact_type": "ExactPolyline3",
            "lean_formalized": False,
            "points": [
                _vec3(v, f"{ident}.points[{i}]")
                for i, v in enumerate(points)
            ],
            "formal_gap": "glyph/polyline semantics remain a separate formalization target",
        }

    raise CompileError(f"{ident}: unsupported geometry primitive type {kind!r}")


def compile_magick(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != "0.1":
        raise CompileError("only Magick IR schema_version 0.1 is supported")

    source = payload.get("source")
    geometry = payload.get("geometry")
    if not isinstance(source, dict) or not isinstance(geometry, dict):
        raise CompileError("source and geometry objects are required")

    policy = source.get("transmission_policy", {})
    if policy.get("missing_pixels_policy") != "latent_no_reconstruction":
        raise CompileError("missing-pixel policy must remain latent_no_reconstruction")

    witnesses = source.get("witnesses", [])
    for witness in witnesses:
        if (
            witness.get("provenance_status") == "missing"
            and witness.get("visual_features_imputed") is True
        ):
            raise CompileError(
                f"witness {witness.get('id')!r}: missing visual evidence may not be imputed"
            )

    primitives = geometry.get("primitives")
    if not isinstance(primitives, list) or not primitives:
        raise CompileError("geometry.primitives must be a nonempty array")

    exact = [_compile_primitive(p) for p in primitives]
    ids = [p["id"] for p in exact]
    if len(ids) != len(set(ids)):
        raise CompileError("geometry primitive ids must be unique")

    formal_gaps = [
        {"id": p["id"], "exact_type": p["exact_type"], "reason": p.get("formal_gap")}
        for p in exact
        if not p["lean_formalized"]
    ]

    return {
        "schema_version": 1,
        "compiler": "magick_ir_exact_geometry_v0.1",
        "experiment_id": payload.get("experiment_id"),
        "source_sha256": _canonical_digest(payload),
        "coordinate_frame": geometry.get("coordinate_frame"),
        "orientation_sensitive": bool(geometry.get("orientation_sensitive", False)),
        "exact_primitives": exact,
        "topology_constraints": geometry.get("topology", []),
        "formalization": {
            "lean_kernel": "MathAI.Geometry",
            "fully_formalized": not formal_gaps,
            "gaps": formal_gaps,
        },
        "epistemic_guards": {
            "floating_geometry_emitted": False,
            "missing_visual_features_imputed": False,
            "historical_claim_treated_as_physical_evidence": False,
        },
    }


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_float=Decimal)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument(
        "--require-fully-formalized",
        action="store_true",
        help="fail if any exact primitive lacks a first-class Lean type",
    )
    args = parser.parse_args()

    compiled = compile_magick(load_json(args.input))
    if args.require_fully_formalized and not compiled["formalization"]["fully_formalized"]:
        gaps = ", ".join(g["id"] for g in compiled["formalization"]["gaps"])
        raise SystemExit(f"formalization gaps remain: {gaps}")

    rendered = json.dumps(compiled, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
