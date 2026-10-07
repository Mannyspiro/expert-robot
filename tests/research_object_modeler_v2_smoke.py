#!/usr/bin/env python3
"""Research Object Modeler v0.2 regression tests (no FEA claims)."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
module_path = ROOT / "scripts" / "generate_research_object_candidates.py"
spec = importlib.util.spec_from_file_location("modeler", module_path)
modeler = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(modeler)

fixture = json.loads(
    (ROOT / "config" / "examples" / "research_object_demo.json").read_text()
)

# Bug regression: segment parallel to Z slab and inside Z but outside Y
# absolutely must not collide with the box.
lo = [-0.03, -0.03, -0.05]
hi = [0.03, 0.03, 0.05]
assert modeler.segment_intersects_box(
    [-0.08, -0.08, 0], [0.08, -0.08, 0], lo, hi
) is False
assert modeler.segment_intersects_box(
    [-0.08, 0, 0], [0.08, 0, 0], lo, hi
) is True
assert modeler.segment_intersects_box(
    [-0.08, 0.03, 0], [0.08, 0.03, 0], lo, hi
) is True
assert modeler.segment_intersects_box(
    [-0.08, 0.031, 0], [0.08, 0.031, 0], lo, hi
) is False

demo = modeler.generate(fixture)
assert demo["survivor_count"] > 0
assert demo["schema_version"] == 2
assert demo["pareto_candidate_ids"]
assert all(
    c["feasible_geometric_graph"] and c["obstacle_violation_count"] == 0
    for c in demo["ranked_survivors"]
)
assert all(
    c["mass_proxy_kg"] is not None and c["mass_proxy_kg"] > 0
    for c in demo["ranked_survivors"]
)
assert any(x["candidate_id"] == "ring" for x in demo["ranked_survivors"])
assert modeler.generate(fixture) == demo

# Two interfaces are separated by a thick full-height optical keep-out.
# All direct connections are illegal; the routing network must use a detour.
blocked_pair = copy.deepcopy(fixture)
blocked_pair["object_id"] = "two-point-detour"
blocked_pair["geometry_catalog"]["points"] = [
    {"id": "a", "xyz_m": [-0.08, 0, 0]},
    {"id": "b", "xyz_m": [0.08, 0, 0]},
]
blocked_pair["preserve_geometry"] = [
    {"id": "mount_a", "geometry_ref": "a", "role": "mount"},
    {"id": "mount_b", "geometry_ref": "b", "role": "mount"},
]
detour_result = modeler.generate(blocked_pair)
by_name = {c["candidate_id"]: c for c in detour_result["candidates"]}
assert by_name["nearest_tree"]["obstacle_violation_count"] == 1
route = by_name["obstacle_aware_tree"]
assert route["feasible_geometric_graph"] is True
assert route["connected"] is True
assert route["obstacle_violation_count"] == 0
assert route["total_strut_length_m"] > 0.16
assert len(route["edges"]) >= 3
assert any(k.startswith("__detour_") for k in route["node_positions_m"])
assert all(
    modeler.blocked(
        route["node_positions_m"][a],
        route["node_positions_m"][b],
        [
            {**blocked_pair["geometry_catalog"]["obstacle_boxes"][0],
             "clearance_m": 0.005 + 0.003 / 2}
        ],
    ) is None
    for a, b in route["edges"]
)

# Preserve-space and fabrication constraints should fail closed, not silently
# accept an impossible candidate.
outside = copy.deepcopy(fixture)
outside["geometry_catalog"]["points"][0]["xyz_m"] = [-0.20, -0.08, 0]
try:
    modeler.generate(outside)
except ValueError as exc:
    assert "outside design bounds" in str(exc)
else:
    raise AssertionError("outside preserve geometry was accepted")

overlap = copy.deepcopy(fixture)
overlap["geometry_catalog"]["points"][0]["xyz_m"] = [0, 0, 0]
try:
    modeler.generate(overlap)
except ValueError as exc:
    assert "keep-out" in str(exc)
else:
    raise AssertionError("preserve interface inside keep-out was accepted")

print("research object modeler v0.2: PASS")
