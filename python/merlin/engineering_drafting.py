"""Deterministic SVG drafting views derived from Merlin's engineering IR.

This creates editable vector drawings from declared geometry. It is a
schematic visualization aid, not a dimensioned manufacturing drawing or
proof of fit, tolerance, electrical safety, or standards compliance.
"""
from __future__ import annotations

import html
from typing import Any

from merlin.engineering_ir import EngineeringProject, validate_project


def export_top_view_svg(project: EngineeringProject, assembly: Any,
                        scale: float = 4.0, margin_mm: float = 12.0) -> str:
    if scale <= 0 or margin_mm < 0:
        raise ValueError("scale must be positive and margin non-negative")
    errors = [issue for issue in validate_project(project) if issue.severity == "error"]
    if errors:
        raise ValueError("cannot draft an invalid engineering project")
    from merlin.cad_assembly import validate_assembly, compose, resolve_frames, Transform3D
    assembly_errors = [issue for issue in validate_assembly(project, assembly)
                       if issue.severity == "error"]
    if assembly_errors:
        raise ValueError("cannot draft an invalid assembly")
    parts = {part.ref: part for part in project.parts}
    frame_world = resolve_frames(assembly.frames)
    items = []
    for component in assembly.components:
        part = parts[component.part_ref]
        world = component.transform
        if component.frame_id is not None:
            world = compose(frame_world[component.frame_id], world)
        world = compose(world, Transform3D(translation_mm=part.position_mm))
        # Axis-aligned XY projection of the declared rectangular footprint.
        r = world.rotation
        sx, sy, _ = part.size_mm
        hx = (abs(r[0]) * sx + abs(r[1]) * sy) / 2
        hy = (abs(r[3]) * sx + abs(r[4]) * sy) / 2
        cx, cy = world.translation_mm[0], world.translation_mm[1]
        items.append((part.ref, part.name, cx-hx, cy-hy, 2*hx, 2*hy))
    if not items:
        raise ValueError("assembly has no components")
    min_x = min(item[2] for item in items) - margin_mm
    min_y = min(item[3] for item in items) - margin_mm
    max_x = max(item[2] + item[4] for item in items) + margin_mm
    max_y = max(item[3] + item[5] for item in items) + margin_mm
    width, height = (max_x-min_x)*scale, (max_y-min_y)*scale
    parts_svg = []
    for ref, name, x, y, w, h in sorted(items):
        px, py = (x-min_x)*scale, (max_y-y-h)*scale
        parts_svg.append(
            f'<rect x="{px:.3f}" y="{py:.3f}" width="{w*scale:.3f}" '
            f'height="{h*scale:.3f}" fill="none" stroke="#172554" stroke-width="1.4"/>'
        )
        parts_svg.append(
            f'<text x="{px+4:.3f}" y="{py+14:.3f}" font-size="10" '
            f'fill="#172554">{html.escape(ref)} — {html.escape(name)}</text>'
        )
    title = html.escape(project.name)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}" '
        f'height="{height:.3f}" viewBox="0 0 {width:.3f} {height:.3f}">'
        f'<title>{title} — top-view geometry proposal</title>'
        '<rect width="100%" height="100%" fill="white"/>'
        f'<text x="8" y="16" font-size="12" fill="#991b1b">'
        'MERLIN DRAFT VIEW — NOT FOR MANUFACTURE</text>'
        + "".join(parts_svg) + "</svg>"
    )
