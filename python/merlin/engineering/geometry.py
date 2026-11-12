"""Typed geometry IR for Merlin drafting/CAD adapters.

This module validates topology and exports OpenSCAD source. It does not claim
mechanical, structural, manufacturing, or safety qualification.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable

UNIT_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}


@dataclass(frozen=True)
class Point3D:
    id: str
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class GeometrySpec:
    name: str
    unit: str
    points: tuple[Point3D, ...]
    faces: tuple[tuple[str, ...], ...]
    closed_solid: bool = False


@dataclass(frozen=True)
class GeometryIssue:
    code: str
    message: str


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _face_area(points: list[Point3D]) -> float:
    total = (0.0, 0.0, 0.0)
    for i, point in enumerate(points):
        nxt = points[(i + 1) % len(points)]
        cross = _cross((point.x, point.y, point.z), (nxt.x, nxt.y, nxt.z))
        total = (total[0] + cross[0], total[1] + cross[1], total[2] + cross[2])
    return 0.5 * (total[0] ** 2 + total[1] ** 2 + total[2] ** 2) ** 0.5


def validate_geometry(spec: GeometrySpec) -> list[GeometryIssue]:
    issues: list[GeometryIssue] = []
    if spec.unit not in UNIT_TO_MM:
        issues.append(GeometryIssue("unit.unsupported", f"Unsupported unit: {spec.unit}"))
    if not spec.name.strip():
        issues.append(GeometryIssue("name.empty", "Geometry name must not be empty."))

    ids = [point.id for point in spec.points]
    if len(ids) != len(set(ids)):
        issues.append(GeometryIssue("point.duplicate_id", "Point identifiers must be unique."))
    point_map = {point.id: point for point in spec.points}
    for point in spec.points:
        if not point.id:
            issues.append(GeometryIssue("point.empty_id", "Point identifiers must not be empty."))
        if not all(isfinite(v) for v in (point.x, point.y, point.z)):
            issues.append(GeometryIssue("point.non_finite", f"Point {point.id} has a non-finite coordinate."))

    if not spec.faces:
        issues.append(GeometryIssue("face.none", "At least one face is required for a surface mesh."))
    edge_use: dict[tuple[str, str], int] = {}
    face_signatures: set[tuple[str, ...]] = set()
    for index, face in enumerate(spec.faces):
        if len(face) < 3 or len(set(face)) < 3:
            issues.append(GeometryIssue("face.degenerate", f"Face {index} must contain at least three distinct points."))
            continue
        if any(pid not in point_map for pid in face):
            issues.append(GeometryIssue("face.unknown_point", f"Face {index} references an unknown point."))
            continue
        signature = tuple(sorted(face))
        if signature in face_signatures:
            issues.append(GeometryIssue("face.duplicate", f"Face {index} duplicates another face."))
        face_signatures.add(signature)
        coords = [point_map[pid] for pid in face]
        if _face_area(coords) <= 1e-10:
            issues.append(GeometryIssue("face.zero_area", f"Face {index} has zero area."))
        for i, pid in enumerate(face):
            other = face[(i + 1) % len(face)]
            edge = tuple(sorted((pid, other)))
            edge_use[edge] = edge_use.get(edge, 0) + 1

    if spec.closed_solid:
        for edge, count in edge_use.items():
            if count != 2:
                issues.append(GeometryIssue("mesh.non_manifold_edge", f"Edge {edge} is used by {count} faces; closed solids require exactly two."))
    else:
        for edge, count in edge_use.items():
            if count > 2:
                issues.append(GeometryIssue("mesh.non_manifold_edge", f"Edge {edge} is used by {count} faces."))

    return issues


def bounding_box(spec: GeometrySpec) -> dict[str, tuple[float, float, float]]:
    if not spec.points:
        raise ValueError("Cannot compute a bounding box without points.")
    factor = UNIT_TO_MM.get(spec.unit)
    if factor is None:
        raise ValueError(f"Unsupported unit: {spec.unit}")
    xs = [p.x * factor for p in spec.points]
    ys = [p.y * factor for p in spec.points]
    zs = [p.z * factor for p in spec.points]
    return {"min_mm": (min(xs), min(ys), min(zs)), "max_mm": (max(xs), max(ys), max(zs))}


def to_openscad(spec: GeometrySpec) -> str:
    issues = validate_geometry(spec)
    if issues:
        raise ValueError("Geometry validation failed: " + "; ".join(i.code for i in issues))
    factor = UNIT_TO_MM[spec.unit]
    point_index = {point.id: i for i, point in enumerate(spec.points)}
    points = ",\n".join(
        f"    [{p.x * factor:.9g}, {p.y * factor:.9g}, {p.z * factor:.9g}]"
        for p in spec.points
    )
    faces = ",\n".join(
        "    [" + ", ".join(str(point_index[pid]) for pid in face) + "]"
        for face in spec.faces
    )
    return (
        f"// Merlin geometry IR: {spec.name}; source unit: {spec.unit}; output unit: mm\n"
        "polyhedron(\n"
        f"  points=[\n{points}\n  ],\n"
        f"  faces=[\n{faces}\n  ],\n"
        "  convexity=10\n"
        ");\n"
    )
