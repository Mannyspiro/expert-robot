#!/usr/bin/env python3
"""Research Object Foundry truss FEM numerical regression tests."""
import copy
import importlib.util
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "truss", ROOT/"scripts"/"evaluate_research_object_truss.py"
)
truss=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(truss)

demo=json.loads((ROOT/"config"/"examples"/"research_object_demo.json").read_text())
load=json.loads((ROOT/"config"/"examples"/"research_object_truss_load_case.json").read_text())
out=truss.evaluate(demo,load)
assert out["geometrically_feasible_count"]>0
assert out["truss_solved_count"]>0
assert out["ranked_truss_results"]
ring=next((x for x in out["ranked_truss_results"] if x["candidate_id"]=="ring"),None)
assert ring is not None
assert ring["max_displacement_m"]>0
assert ring["max_abs_axial_stress_pa"]>0
assert ring["max_free_dof_residual_n"]<1e-5
assert ring["passes_declared_truss_limits"] is True
assert abs(sum(ring["sum_applied_force_n"][i]+ring["sum_support_reaction_n"][i]
               for i in (0,1)))<1e-5
assert ring["compliance_j"]>=0
assert math.isclose(2*ring["strain_energy_j"],ring["compliance_j"],rel_tol=1e-12)
assert out["evidence_ceiling"]=="simplified_pin_joint_2d_fem_not_full_3d_cace_certificate"

# Canonical one-bar 2D axial test: extension FL/(EA), stress F/A, balanced reactions.
length,force,youngs,diameter=1.0,100.0,200e9,0.01
bar={
  "candidate_id":"single_bar",
  "feasible_geometric_graph":True,
  "node_positions_m":{"a":[0,0,0],"b":[length,0,0]},
  "edges":[["a","b"]],
}
case={
    "analysis_plane":"xy",
    "supports":[{"point_id":"a","fixed":["x","y"]},
                {"point_id":"b","fixed":["y"]}],
    "loads":[{"point_id":"b","force_n":[force,0]}],
}
res=truss.analyze(bar,case,{"youngs_modulus_pa":youngs},diameter)
area=math.pi*(diameter/2)**2
expected=force*length/(youngs*area)
assert math.isclose(res["node_displacements_m"]["b"]["ux"],expected,rel_tol=1e-10)
assert math.isclose(res["max_abs_axial_stress_pa"],force/area,rel_tol=1e-10)
assert math.isclose(res["sum_support_reaction_n"][0],-force,rel_tol=1e-10)
assert res["max_free_dof_residual_n"]<1e-10

# An unconstrained rigid translation must be reported as singular.
unfixed={
    "analysis_plane":"xy",
    "supports":[{"point_id":"a","fixed":["y"]}],
    "loads":[{"point_id":"b","force_n":[force,0]}],
}
try:
    truss.analyze(bar,unfixed,{"youngs_modulus_pa":youngs},diameter)
except ValueError as exc:
    assert "singular" in str(exc)
else:
    raise AssertionError("singular truss accepted")

# Missing E is rejected rather than silently assigning a material.
try:
    truss.analyze(bar,case,{},diameter)
except ValueError as exc:
    assert "Young's modulus" in str(exc)
else:
    raise AssertionError("unidentified material accepted")

# Deliberately too-low allowable stress is flagged (not silently passed).
over=copy.deepcopy(case)
over["allowable_stress_pa"]=1e3
fail=truss.analyze(bar,over,{"youngs_modulus_pa":youngs},diameter)
assert "allowable_axial_stress" in fail["constraint_violations"]
assert fail["passes_declared_truss_limits"] is False

print("research object 2D truss FEM: PASS")
