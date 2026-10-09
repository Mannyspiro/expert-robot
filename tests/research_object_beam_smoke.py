#!/usr/bin/env python3
"""Independent cantilever formulas, convergence, and rejection regressions."""
import copy
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("beam", ROOT / "scripts/evaluate_research_object_beam.py")
beam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(beam)
example = json.loads((ROOT / "config/examples/research_object_beam.json").read_text())
report = beam.evaluate(example)
assert report["passed"] and not report["promotion_authority"]
assert report["candidate_id"] == "complete_graph"
rows = report["meshes"]
ei = 200e9 * math.pi * 0.02**4 / 64
for row in rows:
    assert math.isclose(row["tip_displacement_m"], -1 / (8 * ei), rel_tol=1e-7)
    assert math.isclose(row["tip_rotation_rad"], -1 / (6 * ei), rel_tol=1e-7)
    assert math.isclose(row["root_reaction_n"], 1, rel_tol=1e-7)
    assert math.isclose(row["root_reaction_moment_nm"], 0.5, rel_tol=1e-7)
for coarse, fine in zip(rows, rows[1:]):
    assert 15.5 < coarse["displacement_l2_error_m_sqrt_m"] / fine["displacement_l2_error_m_sqrt_m"] < 16.5
    assert 3.95 < coarse["curvature_l2_error_per_sqrt_m"] / fine["curvature_l2_error_per_sqrt_m"] < 4.05

# Independent point-force and moment references; a cubic Hermite field is exact.
for force, moment in [(2, 0), (0, 3), (2, -3)]:
    row = beam.solve(1, 200e9, .02, 0, force, moment, 3)
    assert math.isclose(row["tip_displacement_m"], force / (3 * ei) + moment / (2 * ei), abs_tol=1e-12)
    assert math.isclose(row["tip_rotation_rad"], force / (2 * ei) + moment / ei, abs_tol=1e-12)
    assert math.isclose(row["root_reaction_n"], -force, abs_tol=1e-8)
    assert math.isclose(row["root_reaction_moment_nm"], -force - moment, abs_tol=1e-8)
    assert row["displacement_l2_error_m_sqrt_m"] < 1e-12

# A rotated centerline preserves the local bending solution.
rotated = copy.deepcopy(example)
rotated["geometry_catalog"]["points"][1]["xyz_m"] = [0, 1, 0]
rotated["design_space"]["bounds"]["max"] = [1.02, 1.02, .02]
assert math.isclose(beam.evaluate(rotated)["meshes"][-1]["tip_displacement_m"], rows[-1]["tip_displacement_m"], rel_tol=1e-10)

def reject(mutator):
    bad = copy.deepcopy(example)
    mutator(bad)
    try:
        beam.evaluate(bad)
    except (ValueError, TypeError):
        return
    raise AssertionError("invalid beam was accepted")

reject(lambda x: x["beam_benchmark"].update(uniform_transverse_load_n_m=float("nan")))
reject(lambda x: x["beam_benchmark"].update(root_point_id="missing"))
reject(lambda x: x["beam_benchmark"].update(mesh_elements=[1, 128]))
reject(lambda x: x["beam_benchmark"].update(mesh_elements=[True, 2, 4]))
reject(lambda x: x["beam_benchmark"].update(uniform_transverse_load_n_m=1e6))
reject(lambda x: x["materials"][0].update(provenance=""))
reject(lambda x: x["materials"][0].update(youngs_modulus_pa=0))
reject(lambda x: x["constraints"].update(minimum_feature_m=.2))
reject(lambda x: x["geometry_catalog"]["points"][1].update(xyz_m=[1, 0, .01]))
print("beam: analytic loads, interior convergence, reactions, rotation and rejection checks passed")
