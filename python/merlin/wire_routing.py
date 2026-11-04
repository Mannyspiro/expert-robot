"""Deterministic 3D candidate routing for Merlin's physical netlist.

This is an abstract orthogonal centerline planner, not a wire-harness
manufacturing router. It proposes geometry from declared pin coordinates and
component AABBs; it does not select wire gauge, insulation, connector ratings,
electrical clearances, impedance, thermal limits, bend radii, or code compliance.
"""
from __future__ import annotations

from itertools import permutations
import math
from typing import Any

from merlin.cad_assembly import CADAssembly, Transform3D, _world_aabb
from merlin.coordinate_frames import compose, resolve_frames
from merlin.engineering_ir import EngineeringProject
from merlin.physical_connectivity import physical_netlist


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def _compress(points: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    result = []
    for point in points:
        if not result or any(abs(point[i] - result[-1][i]) > 1e-10 for i in range(3)):
            result.append(point)
    return result


def _manhattan_path(
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    order: tuple[int, int, int],
) -> list[tuple[float, float, float]]:
    current = list(start)
    points = [start]
    for axis in order:
        current[axis] = end[axis]
        points.append(tuple(current))
    return _compress(points)


def _segment_hits_box(
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    box_min: tuple[float, float, float],
    box_max: tuple[float, float, float],
) -> bool:
    """Interior intersection for an axis-aligned segment and open AABB."""
    changed = [axis for axis in range(3) if abs(end[axis] - start[axis]) > 1e-10]
    if len(changed) == 0:
        return False
    if len(changed) != 1:
        raise ValueError("candidate route segments must be axis-aligned")
    axis = changed[0]
    for other in range(3):
        if other != axis and not (box_min[other] < start[other] < box_max[other]):
            return False
    low = max(min(start[axis], end[axis]), box_min[axis])
    high = min(max(start[axis], end[axis]), box_max[axis])
    return high - low > 1e-10


def _path_is_clear(
    path: list[tuple[float, float, float]],
    obstacles: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
) -> bool:
    return not any(
        _segment_hits_box(a, b, lo, hi)
        for a, b in zip(path, path[1:])
        for lo, hi in obstacles
    )


def _component_obstacles(
    project: EngineeringProject,
    assembly: CADAssembly,
    excluded_refs: set[str],
    clearance_mm: float,
):
    parts = {part.ref: part for part in project.parts}
    frames = resolve_frames(assembly.frames)
    obstacles = []
    for component in assembly.components:
        if component.part_ref in excluded_refs:
            continue
        part = parts[component.part_ref]
        world = component.transform
        if component.frame_id is not None:
            world = compose(frames[component.frame_id], world)
        world = compose(world, Transform3D(translation_mm=part.position_mm))
        lo, hi = _world_aabb(part.size_mm, world)
        margin = clearance_mm
        obstacles.append((
            tuple(lo[i] - margin for i in range(3)),
            tuple(hi[i] + margin for i in range(3)),
        ))
    return obstacles


def _candidate_paths(start, end, obstacles, clearance_mm):
    candidates = []
    for order in permutations((0, 1, 2)):
        candidates.append(("axis_order_" + "".join(str(axis) for axis in order),
                           _manhattan_path(start, end, order)))
    if obstacles:
        top = max(hi[2] for _lo, hi in obstacles)
        overpass_z = max(start[2], end[2], top) + max(clearance_mm, 0.5) + 0.5
        candidates.append(("global_z_overpass", _compress([
            start,
            (start[0], start[1], overpass_z),
            (end[0], start[1], overpass_z),
            (end[0], end[1], overpass_z),
            end,
        ])))
    return candidates


def route_physical_netlist(
    project: EngineeringProject,
    assembly: CADAssembly,
    *,
    clearance_mm: float = 1.0,
) -> dict[str, Any]:
    """Propose deterministic orthogonal routes for declared physical net pins.

    Multi-terminal nets use a deterministic star rooted at the lexicographically
    first endpoint. Obstacles are conservative transformed component AABBs.
    Source and destination components are excluded from each pair's obstacle
    set so the route can enter/leave their declared pin locations.
    """
    if not math.isfinite(clearance_mm) or clearance_mm < 0:
        raise ValueError("clearance_mm must be finite and nonnegative")
    netlist = physical_netlist(project, assembly)
    all_routes = []
    routed_nets = []
    for net in netlist["nets"]:
        endpoints = net["endpoints"]
        if len(endpoints) < 2:
            routed_nets.append({
                "name": net["name"], "status": "not_routable_insufficient_endpoints",
                "routes": [],
            })
            continue
        root = endpoints[0]
        pair_routes = []
        for target in endpoints[1:]:
            if root.get("position_mm") is None or target.get("position_mm") is None:
                pair_routes.append({
                    "from": root["endpoint"], "to": target["endpoint"],
                    "status": "unroutable_missing_endpoint_geometry",
                    "polyline_mm": None, "length_mm": None,
                })
                continue
            start = tuple(float(v) for v in root["position_mm"])
            end = tuple(float(v) for v in target["position_mm"])
            excluded = {root["part_ref"], target["part_ref"]}
            obstacles = _component_obstacles(project, assembly, excluded, clearance_mm)
            clear = []
            for method, path in _candidate_paths(start, end, obstacles, clearance_mm):
                if _path_is_clear(path, obstacles):
                    length = sum(_distance(a, b) for a, b in zip(path, path[1:]))
                    clear.append((length, method, path))
            if not clear:
                pair_routes.append({
                    "from": root["endpoint"], "to": target["endpoint"],
                    "status": "blocked_no_candidate_path",
                    "polyline_mm": None, "length_mm": None,
                })
                continue
            length, method, path = min(clear, key=lambda item: (item[0], item[1]))
            pair_routes.append({
                "from": root["endpoint"], "to": target["endpoint"],
                "status": "candidate_geometry_not_manufacturing_qualified",
                "method": method,
                "polyline_mm": [list(point) for point in path],
                "length_mm": length,
                "segment_count": max(0, len(path) - 1),
                "clearance_assumption_mm": clearance_mm,
            })
        statuses = {item["status"] for item in pair_routes}
        status = ("candidate_geometry_not_manufacturing_qualified"
                  if statuses == {"candidate_geometry_not_manufacturing_qualified"}
                  else "partial_or_unroutable")
        routed_nets.append({"name": net["name"], "status": status, "routes": pair_routes})
    return {
        "format": "merlin-wire-route-proposals-v0.1",
        "units": "mm",
        "project": project.name,
        "assembly": assembly.name,
        "routing_model": "orthogonal_3d_centerline_over_conservative_component_aabbs",
        "clearance_assumption_mm": clearance_mm,
        "nets": routed_nets,
        "status": "GEOMETRY_PROPOSAL_ONLY_NOT_ELECTRICAL_OR_MANUFACTURING_APPROVAL",
        "limitations": [
            "Uses only declared pin coordinates and simplified component bounding boxes.",
            "No conductor gauge, ampacity, insulation, creepage, clearance, impedance, thermal, EMI, bend-radius, strain-relief, connector, or regulatory analysis.",
            "No exact solid collision test; AABBs are conservative approximations.",
            "A candidate path is not a fabrication-ready harness or proof of electrical safety.",
            "Multi-terminal nets use a star proposal, not a globally optimized tree.",
        ],
    }
