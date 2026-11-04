"""Hierarchical rigid coordinate frames for CAD and engineering geometry."""
from __future__ import annotations

from dataclasses import dataclass
import math

from merlin.cad_assembly import Transform3D, validate_transform


@dataclass(frozen=True)
class CoordinateFrame:
    frame_id: str
    parent_id: str | None = None
    transform: Transform3D = Transform3D()


def compose(parent: Transform3D, child: Transform3D) -> Transform3D:
    """Return parent ∘ child using row-major active rotation matrices."""
    a, b = parent.rotation, child.rotation
    rotation = tuple(
        sum(a[row * 3 + k] * b[k * 3 + col] for k in range(3))
        for row in range(3) for col in range(3)
    )
    t = child.translation_mm
    translated = tuple(
        parent.translation_mm[row] +
        sum(a[row * 3 + col] * t[col] for col in range(3))
        for row in range(3)
    )
    return Transform3D(rotation=rotation, translation_mm=translated)


def inverse(transform: Transform3D) -> Transform3D:
    """Inverse of a validated rigid transform."""
    errors = validate_transform(transform)
    if errors:
        raise ValueError("cannot invert invalid transform: " + "; ".join(errors))
    r = transform.rotation
    transpose = tuple(r[col * 3 + row] for row in range(3) for col in range(3))
    t = transform.translation_mm
    inverse_t = tuple(-sum(transpose[row * 3 + col] * t[col] for col in range(3))
                      for row in range(3))
    return Transform3D(rotation=transpose, translation_mm=inverse_t)


def transform_point(transform: Transform3D, point_mm: tuple[float, float, float]):
    if len(point_mm) != 3 or any(not math.isfinite(value) for value in point_mm):
        raise ValueError("point must contain three finite coordinates")
    r = transform.rotation
    return tuple(
        transform.translation_mm[row] +
        sum(r[row * 3 + col] * point_mm[col] for col in range(3))
        for row in range(3)
    )


def resolve_frames(frames: tuple[CoordinateFrame, ...]) -> dict[str, Transform3D]:
    """Resolve every frame into world coordinates; reject missing parents and cycles."""
    by_id = {frame.frame_id: frame for frame in frames}
    if len(by_id) != len(frames):
        raise ValueError("coordinate frame IDs must be unique")
    if any(not frame.frame_id.strip() for frame in frames):
        raise ValueError("coordinate frame IDs must be non-empty")
    for frame in frames:
        if frame.parent_id is not None and frame.parent_id not in by_id:
            raise ValueError("unknown parent frame: " + frame.parent_id)
        errors = validate_transform(frame.transform)
        if errors:
            raise ValueError(frame.frame_id + ": " + "; ".join(errors))

    resolved: dict[str, Transform3D] = {}
    visiting: set[str] = set()

    def visit(frame_id: str) -> Transform3D:
        if frame_id in resolved:
            return resolved[frame_id]
        if frame_id in visiting:
            raise ValueError("coordinate frame cycle detected at " + frame_id)
        visiting.add(frame_id)
        frame = by_id[frame_id]
        world = frame.transform if frame.parent_id is None else compose(
            visit(frame.parent_id), frame.transform
        )
        visiting.remove(frame_id)
        resolved[frame_id] = world
        return world

    for frame_id in sorted(by_id):
        visit(frame_id)
    return resolved
