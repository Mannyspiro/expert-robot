"""Deterministic SVG drafting views derived from Merlin's engineering IR.

This creates editable vector drawings from declared geometry. It is a
schematic visualization aid, not a dimensioned manufacturing drawing or
proof of fit, tolerance, electrical safety, or standards compliance.
"""
from __future__ import annotations

import html
import math
from typing import Any

from merlin.engineering_ir import EngineeringProject, validate_project


def export_top_view_svg(project: EngineeringProject, assembly: Any,
                        scale: float = 4.0, margin_mm: float = 12.0,
                        route_output: dict[str, Any] | None = None) -> str:
    if not math.isfinite(scale) or scale <= 0 or not math.isfinite(margin_mm) or margin_mm < 0:
        raise ValueError("scale must be finite and positive; margin must be finite and nonnegative")
    errors = [issue for issue in validate_project(project) if issue.severity == "error"]
    if errors:
        raise ValueError("cannot draft an invalid engineering project")
    from merlin.cad_assembly import validate_assembly, Transform3D
    from merlin.coordinate_frames import compose, resolve_frames
    from merlin.physical_connectivity import physical_netlist
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
    physical = physical_netlist(project, assembly)
    pin_positions = {
        endpoint["endpoint"]: endpoint["position_mm"]
        for net in physical["nets"] for endpoint in net["endpoints"]
        if endpoint.get("position_mm") is not None
    }
    route_paths = []
    if route_output is not None:
        if (route_output.get("format") != "merlin-wire-route-proposals-v0.1"
                or route_output.get("units") != "mm"):
            raise ValueError("unsupported route proposal format or units")
        if route_output.get("project") != project.name or route_output.get("assembly") != assembly.name:
            raise ValueError("route proposal project/assembly identity mismatch")
        route_nets = route_output.get("nets")
        if not isinstance(route_nets, list):
            raise ValueError("route proposal nets must be a list")
        for route_net in route_nets:
            if not isinstance(route_net, dict):
                continue
            routes = route_net.get("routes", [])
            if not isinstance(routes, list):
                raise ValueError("route net routes must be a list")
            for route in routes:
                if not isinstance(route, dict):
                    continue
                if route.get("status") != "candidate_geometry_not_manufacturing_qualified":
                    continue
                raw = route.get("polyline_mm")
                if not isinstance(raw, list) or len(raw) < 2:
                    continue
                points = []
                for point in raw:
                    if (not isinstance(point, (list, tuple)) or len(point) != 3
                            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                                   or not math.isfinite(v) for v in point)):
                        raise ValueError("route polyline coordinates must be finite 3D points")
                    points.append(tuple(float(v) for v in point))
                route_paths.append((route_net.get("name", "unnamed"), route, points))
    all_x = [item[2] for item in items] + [item[2] + item[4] for item in items]
    all_y = [item[3] for item in items] + [item[3] + item[5] for item in items]
    all_x.extend(point[0] for point in pin_positions.values())
    all_y.extend(point[1] for point in pin_positions.values())
    for _net_name, _route, points in route_paths:
        all_x.extend(point[0] for point in points)
        all_y.extend(point[1] for point in points)
    min_x = min(all_x) - margin_mm
    min_y = min(all_y) - margin_mm
    max_x = max(all_x) + margin_mm
    max_y = max(all_y) + margin_mm
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
    wire_svg = []
    if route_output is None:
        for net in sorted(project.nets, key=lambda item: item.name):
            endpoints = sorted(net.endpoints)
            if len(endpoints) < 2 or endpoints[0] not in pin_positions:
                continue
            origin = pin_positions[endpoints[0]]
            for endpoint in endpoints[1:]:
                target = pin_positions.get(endpoint)
                if target is None:
                    continue
                x1, y1 = (origin[0]-min_x)*scale, (max_y-origin[1])*scale
                x2, y2 = (target[0]-min_x)*scale, (max_y-target[1])*scale
                wire_svg.append(
                    f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" '
                    'stroke="#b45309" stroke-width="1.2" stroke-dasharray="4 3"/>'
                )
                for px, py in ((x1, y1), (x2, y2)):
                    wire_svg.append(
                        f'<circle cx="{px:.3f}" cy="{py:.3f}" r="2.4" fill="#b45309"/>'
                    )
        overlay_label = "LOGICAL STRAIGHT-LINE NET OVERLAY — NOT ROUTED — NOT FOR MANUFACTURE"
    else:
        for net_name, route, points in route_paths:
            xy = " ".join(
                f"{(point[0]-min_x)*scale:.3f},{(max_y-point[1])*scale:.3f}"
                for point in points
            )
            z_profile = ",".join(f"{point[2]:.3f}" for point in points)
            execution = route_output.get("execution")
            lease_id = execution.get("mcfc_lease_id", "") if isinstance(execution, dict) else ""
            wire_svg.append(
                f'<polyline points="{xy}" fill="none" stroke="#0f766e" stroke-width="2" '
                'stroke-dasharray="3 2" '
                f'data-net="{html.escape(str(net_name), quote=True)}" '
                f'data-route-method="{html.escape(str(route.get("method", "unknown")), quote=True)}" '
                f'data-z-profile="{z_profile}" data-mcfc-lease="{html.escape(str(lease_id), quote=True)}">'
                f'<title>{html.escape(str(net_name))} route; Z profile {z_profile} mm</title></polyline>'
            )
            for point in (points[0], points[-1]):
                px, py = (point[0]-min_x)*scale, (max_y-point[1])*scale
                wire_svg.append(f'<circle cx="{px:.3f}" cy="{py:.3f}" r="2.8" fill="#0f766e"/>')
        overlay_label = (
            "3D ROUTE PROPOSALS — XY PROJECTION (Z COLLAPSED) — NOT FOR MANUFACTURE"
            if route_paths else "NO CANDIDATE ROUTES — NOT FOR MANUFACTURE"
        )
    title = html.escape(project.name)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}" '
        f'height="{height:.3f}" viewBox="0 0 {width:.3f} {height:.3f}">'
        f'<title>{title} — top-view geometry proposal</title>'
        '<rect width="100%" height="100%" fill="white"/>'
        f'<text x="8" y="16" font-size="12" fill="#991b1b">'
        f'MERLIN DRAFT VIEW — {overlay_label}</text>'
        + "".join(wire_svg) + "".join(parts_svg) + "</svg>"
    )


def export_route_elevation_svg(
    route_output: dict[str, Any],
    net_name: str,
    *,
    scale: float = 4.0,
    margin_mm: float = 8.0,
) -> str:
    """Export cumulative centerline distance versus Z for candidate routes."""
    if not math.isfinite(scale) or scale <= 0 or not math.isfinite(margin_mm) or margin_mm < 0:
        raise ValueError("scale must be finite and positive; margin must be finite and nonnegative")
    if not isinstance(route_output, dict) or route_output.get("format") != "merlin-wire-route-proposals-v0.1":
        raise ValueError("unsupported route proposal format")
    if route_output.get("units") != "mm":
        raise ValueError("route proposal units must be mm")
    net = next((item for item in route_output.get("nets", [])
                if isinstance(item, dict) and item.get("name") == net_name), None)
    if net is None:
        raise ValueError(f"route net not found: {net_name}")
    profiles = []
    routes = net.get("routes", [])
    if not isinstance(routes, list):
        raise ValueError("route net routes must be a list")
    for route in routes:
        if not isinstance(route, dict):
            continue
        if route.get("status") != "candidate_geometry_not_manufacturing_qualified":
            continue
        raw = route.get("polyline_mm")
        if not isinstance(raw, list) or len(raw) < 2:
            continue
        points = []
        for point in raw:
            if (not isinstance(point, (list, tuple)) or len(point) != 3
                    or any(isinstance(v, bool) or not isinstance(v, (int, float))
                           or not math.isfinite(v) for v in point)):
                raise ValueError("route polyline coordinates must be finite 3D points")
            points.append(tuple(float(v) for v in point))
        distance = 0.0
        profile = [(distance, points[0][2])]
        for start, end in zip(points, points[1:]):
            distance += math.sqrt(sum((start[i] - end[i]) ** 2 for i in range(3)))
            profile.append((distance, end[2]))
        profiles.append((route, profile))
    if not profiles:
        raise ValueError(f"net has no candidate route geometry: {net_name}")
    max_distance = max(profile[-1][0] for _route, profile in profiles)
    min_z = min(z for _route, profile in profiles for _distance_mm, z in profile)
    max_z = max(z for _route, profile in profiles for _distance_mm, z in profile)
    width = (max_distance + 2*margin_mm) * scale
    height = (max_z - min_z + 2*margin_mm) * scale
    if width <= 0 or height <= 0:
        raise ValueError("route profile has degenerate dimensions")
    palette = ("#0f766e", "#b45309", "#1d4ed8", "#7c3aed")
    drawings = []
    for index, (route, profile) in enumerate(profiles):
        points = " ".join(
            f"{(distance+margin_mm)*scale:.3f},{(max_z+margin_mm-z)*scale:.3f}"
            for distance, z in profile
        )
        method = html.escape(str(route.get("method", "unknown")), quote=True)
        drawings.append(
            f'<polyline points="{points}" fill="none" stroke="{palette[index % len(palette)]}" '
            f'stroke-width="2" data-route-method="{method}">'
            f'<title>{html.escape(net_name)} — {method}</title></polyline>'
        )
    title = html.escape(net_name)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}" '
        f'height="{height:.3f}" viewBox="0 0 {width:.3f} {height:.3f}">'
        f'<title>{title} — route elevation profile</title>'
        '<rect width="100%" height="100%" fill="white"/>'
        f'<text x="8" y="16" font-size="12">MERLIN ROUTE PROFILE — NOT A MANUFACTURING DRAWING</text>'
        f'<text x="8" y="{height-4:.3f}" font-size="10">CUMULATIVE CENTERLINE DISTANCE (mm)</text>'
        f'<text x="8" y="32" font-size="10">Z ELEVATION (mm): {min_z:.3f} to {max_z:.3f}</text>'
        + "".join(drawings) + "</svg>"
    )
