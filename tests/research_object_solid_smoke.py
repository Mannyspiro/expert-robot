#!/usr/bin/env python3
"""Watertight voxel solid smoke / negative regression tests."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"scripts"/"solidify_research_object.py"
spec=importlib.util.spec_from_file_location("solid",p)
solid=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(solid)

fixture=json.loads(
    (ROOT/"config"/"examples"/"research_object_demo.json").read_text()
)
a=solid.build(fixture,candidate="ring")
assert a["watertight"] is True
assert a["six_connected"] is True
assert a["oriented_manifold"] is True
assert a["bounds_and_keepouts_checked"] is True
assert a["preserve_points_contained"] is True
assert a["occupied_voxels"]>100
assert a["signed_volume_m3"]>0
assert a["mass_kg"]>0
assert a["vertex_count"]>8
assert a["triangle_count"]>12
assert a["obj"].count("\nf ")==a["triangle_count"]
assert solid.build(fixture,candidate="ring")["sha256_obj"]==a["sha256_obj"]
assert a["evidence_ceiling"]=="watertight_voxel_proxy_not_load_or_manufacturing_certified"

# A filled-in or punctured mesh must be rejected by the independent checker.
assert solid.check_surface(
    [(0,0,0),(1,0,0),(0,1,0),(0,0,1)],
    [(0,2,1),(0,1,3),(0,3,2),(1,2,3)]
)["surface_closed_and_oriented"] is True
try:
    solid.check_surface(
        [(0,0,0),(1,0,0),(0,1,0),(0,0,1)],
        [(0,2,1),(0,1,3),(0,3,2)]
    )
except ValueError:
    pass
else:
    raise AssertionError("open boundary accepted")

# Independent full-solid check rejects extra box that passes through the ring.
modeler=solid.load_modeler()
model=modeler.generate(fixture)
candidate=next(c for c in model["ranked_survivors"] if c["candidate_id"]=="ring")
voxels,origin=solid.rasterize(
    candidate,fixture["design_space"]["bounds"],0.0015,0.001
)
intrusive=copy.deepcopy(fixture)
intrusive["geometry_catalog"]["obstacle_boxes"].append({
    "id":"new_violation","min_xyz_m":[0.075,-0.01,-0.01],
    "max_xyz_m":[0.085,0.01,0.01]
})
intrusive["obstacle_geometry"].append({
    "id":"n","geometry_ref":"new_violation","clearance_m":0.001
})
try:
    solid.validate_cells(voxels,origin,0.001,intrusive,candidate)
except ValueError as exc:
    assert "obstacle" in str(exc)
else:
    raise AssertionError("solid obstacle infringement accepted")

try:
    solid.build(fixture,candidate="ring",pitch=0.003)
except ValueError:
    pass
else:
    raise AssertionError("coarse voxel solid accepted")

print("research object watertight voxel solid: PASS")
