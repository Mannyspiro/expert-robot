#!/usr/bin/env python3
"""Bounded Euler–Bernoulli cantilever benchmark from a Foundry centerline.

Two bending DOFs per node, cubic Hermite elements, circular cross-section.
Local transverse loads; no axial, shear, buckling, joints or 3D solid claim.
Closed-form continuum fields independently check assembly and interpolation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from evaluate_research_object_truss import modeler_module, solve_dense


def finite(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    value = float(value)
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f"invalid {label}")
    return value


def reference(x, length, ei, q, force, moment):
    """Continuum cantilever solution, independent of the discrete stiffness."""
    w = (q*x*x*(6*length*length-4*length*x+x*x)/24
         + force*x*x*(3*length-x)/6 + moment*x*x/2) / ei
    theta = (q*x*(3*length*length-3*length*x+x*x)/6
             + force*x*(2*length-x)/2 + moment*x) / ei
    curvature = (q*(length-x)**2/2 + force*(length-x) + moment) / ei
    return w, theta, curvature


def solve(length, youngs, diameter, q, force, moment, elements, linear_solver=None):
    length = finite(length, "length", True)
    youngs = finite(youngs, "Young's modulus", True)
    diameter = finite(diameter, "diameter", True)
    q, force, moment = (finite(v, k) for v, k in zip(
        (q, force, moment), ("distributed load", "tip force", "tip moment")))
    if type(elements) is not int or not 1 <= elements <= 32:
        raise ValueError("mesh must have 1–32 elements")
    if length / diameter < 10:
        raise ValueError("centerline must have slenderness L/d >= 10")
    ei = youngs * math.pi * diameter**4 / 64
    if not math.isfinite(ei) or ei <= 0:
        raise ValueError("invalid flexural rigidity")
    # Scale the rotational unknown to length*theta, keeping all unknowns in m.
    h = length / elements
    local = [[12, 6*h, -12, 6*h], [6*h, 4*h*h, -6*h, 2*h*h],
             [-12, -6*h, 12, -6*h], [6*h, 2*h*h, -6*h, 4*h*h]]
    scales = [1, 1/length, 1, 1/length]
    local = [[ei/h**3 * local[i][j]*scales[i]*scales[j]
              for j in range(4)] for i in range(4)]
    load = [q*h/2, q*h*h/(12*length), q*h/2, -q*h*h/(12*length)]
    ndof = 2*(elements+1)
    matrix, rhs = [[0.0]*ndof for _ in range(ndof)], [0.0]*ndof
    for e in range(elements):
        ids = [2*e+i for i in range(4)]
        for i, a in enumerate(ids):
            rhs[a] += load[i]
            for j, b in enumerate(ids):
                matrix[a][b] += local[i][j]
    rhs[-2] += force
    rhs[-1] += moment/length
    reduced_matrix, reduced_rhs = [row[2:] for row in matrix[2:]], rhs[2:]
    reduced, ratio = solve_dense(reduced_matrix, reduced_rhs)
    backend_delta = 0.0
    if linear_solver is not None:
        alternate = list(linear_solver(reduced_matrix, reduced_rhs))
        if len(alternate) != len(reduced) or not all(math.isfinite(x) for x in alternate):
            raise ValueError("backend returned invalid beam DOFs")
        backend_delta = max(abs(a-b) for a, b in zip(alternate, reduced))
        if backend_delta > 1e-6*max(map(abs, reduced)) + 1e-12:
            raise ValueError("backend disagrees with independent stdlib solve")
        reduced = alternate
    if not all(math.isfinite(x) for x in reduced):
        raise ValueError("nonfinite beam solution")
    u = [0.0, 0.0] + reduced
    residual = [sum(a*b for a, b in zip(row, u))-f for row, f in zip(matrix, rhs)]
    if not all(math.isfinite(x) for x in residual):
        raise ValueError("nonfinite beam residual")
    normalized = max(abs(residual[i]) / max(1.0, abs(rhs[i]),
                     sum(abs(a*b) for a, b in zip(matrix[i], u))) for i in range(2, ndof))
    if normalized > 1e-10:
        raise ValueError("algebraic residual exceeds tolerance")
    # Five-point Gauss rule integrates the squared quartic field error exactly.
    gauss = [(-.906179845938664, .236926885056189),
             (-.538469310105683, .478628670499366),
             (0, .568888888888889), (.538469310105683, .478628670499366),
             (.906179845938664, .236926885056189)]
    werr = cerr = wnorm = cnorm = 0.0
    max_w = max_theta = max_curvature = 0.0
    for e in range(elements):
        dofs = [u[2*e], u[2*e+1]/length, u[2*e+2], u[2*e+3]/length]
        def field(t):
            shapes = [1-3*t*t+2*t**3, h*(t-2*t*t+t**3), 3*t*t-2*t**3, h*(-t*t+t**3)]
            slopes = [(-6*t+6*t*t)/h, 1-4*t+3*t*t, (6*t-6*t*t)/h, -2*t+3*t*t]
            curves = [(-6+12*t)/h**2, (-4+6*t)/h, (6-12*t)/h**2, (-2+6*t)/h]
            return tuple(sum(a*b for a, b in zip(shape, dofs)) for shape in (shapes, slopes, curves))
        for z, weight in gauss:
            t = (z+1)/2
            w, theta, curvature = field(t)
            wr, _, cr = reference((e+t)*h, length, ei, q, force, moment)
            factor = weight*h/2
            werr += (w-wr)**2*factor
            cerr += (curvature-cr)**2*factor
            wnorm += wr**2*factor
            cnorm += cr**2*factor
        # Extrema of the cubic field and quadratic slope, including endpoints.
        w0, t0, w1, t1 = dofs
        a, b, c = 2*w0+h*t0-2*w1+h*t1, -3*w0-2*h*t0+3*w1-h*t1, h*t0
        samples = [0.0, 1.0]
        if abs(a) > 0:
            disc = 4*b*b-12*a*c
            if disc >= 0:
                samples.extend(t for t in ((-2*b+math.sqrt(disc))/(6*a), (-2*b-math.sqrt(disc))/(6*a)) if 0 < t < 1)
            if 0 < -b/(3*a) < 1:
                samples.append(-b/(3*a))
        elif b != 0 and 0 < -c/(2*b) < 1:
            samples.append(-c/(2*b))
        for t in samples:
            w, theta, curvature = field(t)
            max_w, max_theta, max_curvature = max(max_w, abs(w)), max(max_theta, abs(theta)), max(max_curvature, abs(curvature))
    if max_w / length > .01 or max_theta > .05:
        raise ValueError("response exceeds bounded small-displacement/rotation envelope")
    return {
        "elements": elements, "free_dofs": ndof-2,
        "tip_displacement_m": u[-2], "tip_rotation_rad": u[-1]/length,
        "root_reaction_n": residual[0], "root_reaction_moment_nm": residual[1]*length,
        "normalized_free_dof_residual": normalized, "pivot_ratio": ratio,
        "backend_max_dof_difference_m": backend_delta,
        "displacement_l2_error_m_sqrt_m": math.sqrt(werr),
        "curvature_l2_error_per_sqrt_m": math.sqrt(cerr),
        "relative_displacement_l2_error": math.sqrt(werr/wnorm) if wnorm else 0,
        "relative_curvature_l2_error": math.sqrt(cerr/cnorm) if cnorm else 0,
        "max_displacement_m": max_w, "max_rotation_rad": max_theta,
        "max_fe_curvature_bending_stress_pa": youngs*diameter/2*max_curvature,
    }


def evaluate(spec, linear_solver=None):
    cfg = spec["beam_benchmark"]
    meshes = cfg["mesh_elements"]
    if not isinstance(meshes, list) or not 3 <= len(meshes) <= 6 or any(
        type(n) is not int or not 1 <= n <= 32 for n in meshes):
        raise ValueError("require 3–6 bounded integer mesh sizes")
    if any(b != 2*a for a, b in zip(meshes, meshes[1:])):
        raise ValueError("convergence meshes must double")
    # Nonzero uniform load produces a quartic reference: tip-only comparisons
    # would misleadingly look exact even on a single cubic element.
    q = finite(cfg["uniform_transverse_load_n_m"], "distributed load")
    if q == 0:
        raise ValueError("convergence benchmark needs a nonzero distributed load")
    material = next((m for m in spec["materials"] if m["id"] == cfg["material_id"]), None)
    if material is None or not isinstance(material.get("provenance"), str) or not material["provenance"].strip():
        raise ValueError("named material and provenance required")
    generated = modeler_module().generate(spec)
    candidate = next((c for c in generated["ranked_survivors"] if c["candidate_id"] == "complete_graph"), None)
    if candidate is None or not candidate["feasible_geometric_graph"] or len(candidate["edges"]) != 1 or len(candidate["node_positions_m"]) != 2:
        raise ValueError("benchmark requires exactly one feasible modeler edge")
    root, tip = cfg["root_point_id"], cfg["tip_point_id"]
    if root == tip or set(candidate["node_positions_m"]) != {root, tip}:
        raise ValueError("root and tip must identify the two centerline endpoints")
    a, b = candidate["node_positions_m"][root], candidate["node_positions_m"][tip]
    if abs(a[2]-b[2]) > 1e-12:
        raise ValueError("beam centerline must lie in XY plane")
    length = math.dist(a, b)
    diameter = generated["assumed_minimum_strut_diameter_m"]
    youngs = finite(material["youngs_modulus_pa"], "Young's modulus", True)
    rows = [solve(length, youngs, diameter, q, 0, 0, n, linear_solver) for n in meshes]
    convergence = all(15.5 < a["displacement_l2_error_m_sqrt_m"]/b["displacement_l2_error_m_sqrt_m"] < 16.5
                      and 3.95 < a["curvature_l2_error_per_sqrt_m"]/b["curvature_l2_error_per_sqrt_m"] < 4.05
                      for a, b in zip(rows, rows[1:]))
    ei = youngs*math.pi*diameter**4/64
    tip_w, tip_t, _ = reference(length, length, ei, q, 0, 0)
    agreement = all(math.isclose(r["tip_displacement_m"], tip_w, rel_tol=1e-7)
                    and math.isclose(r["tip_rotation_rad"], tip_t, rel_tol=1e-7)
                    and math.isclose(r["root_reaction_n"], -q*length, rel_tol=1e-7)
                    and math.isclose(r["root_reaction_moment_nm"], -q*length**2/2, rel_tol=1e-7) for r in rows)
    result = {
        "schema_version": "0.1", "passed": convergence and agreement,
        "evidence_ceiling": "analytic_checked_linear_cantilever_not_cace_continuum_certificate",
        "promotion_authority": False, "candidate_id": candidate["candidate_id"],
        "topology_sha256": candidate["topology_sha256"],
        "input_sha256": hashlib.sha256(json.dumps(spec, sort_keys=True, allow_nan=False).encode()).hexdigest(),
        "length_m": length, "diameter_m": diameter, "material_provenance": material["provenance"],
        "load_frame": "local transverse (-dy/L, dx/L, 0); root clamped, tip free",
        "analytic_tip_displacement_m": tip_w, "analytic_tip_rotation_rad": tip_t,
        "analytic_root_bending_stress_pa": abs(q)*length**2/2 * diameter/2 / (math.pi*diameter**4/64),
        "meshes": rows, "interior_convergence_passed": convergence,
        "tip_and_reaction_agreement_passed": agreement,
        "source_head_sha": os.getenv("RESEARCH_HEAD_SHA"), "execution_sha": os.getenv("GITHUB_SHA"),
        "producer_run_id": os.getenv("GITHUB_RUN_ID"),
        "limits": ["circular homogeneous slender beam", "linear small displacement", "no shear deformation or buckling", "no joints or 3D solid stresses", "no interval certificate or manufacturing qualification"],
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(json.loads(args.spec.read_text()))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": result["passed"], "mesh_elements": [r["elements"] for r in result["meshes"]]}))
    if not result["passed"]:
        raise SystemExit("beam reference or convergence check failed")


if __name__ == "__main__":
    main()
