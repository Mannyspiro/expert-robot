#!/usr/bin/env python3
"""Prespecified modeler-derived load/material coverage; no blind-study claim."""
import copy
import hashlib
import json
import math
from evaluate_research_object_beam import beam_geometry, finite, solve


def run_holdouts(template, manifest, backend):
    if manifest.get("schema_version") != "0.1" or manifest.get("protocol") != "prespecified-regression-coverage-not-statistically-blind":
        raise ValueError("unknown coverage protocol")
    provenance = manifest.get("material_provenance")
    cases = manifest.get("cases")
    if not isinstance(provenance,str) or not provenance.strip() or not isinstance(cases,list) or not 1 <= len(cases) <= 8:
        raise ValueError("bounded cases and material provenance required")
    # Validate the full manifest before the first solve.
    seen = set()
    for case in cases:
        ident = case.get("id")
        if not isinstance(ident,str) or not ident or ident in seen:
            raise ValueError("unique case IDs required")
        seen.add(ident)
        for key in ("length_m","diameter_m","youngs_modulus_pa"):
            finite(case[key],key,True)
        for key in ("angle_deg","q_n_m","tip_force_n","tip_moment_nm"):
            finite(case[key],key)
        meshes = case.get("meshes")
        if not isinstance(meshes,list) or not 3 <= len(meshes) <= 5 or any(type(n) is not int or not 1 <= n <= 16 for n in meshes) or meshes != sorted(set(meshes)):
            raise ValueError("require 3–5 increasing meshes, at most 16 elements")
        if case["q_n_m"] and any(b != 2*a for a,b in zip(meshes,meshes[1:])):
            raise ValueError("distributed-load convergence meshes must double")
    records = []
    for case in cases:
        spec = copy.deepcopy(template)
        length, diameter = case["length_m"], case["diameter_m"]
        angle = math.radians(case["angle_deg"])
        tip = [length*math.cos(angle),length*math.sin(angle),0.0]
        root_id, tip_id = spec["beam_benchmark"]["root_point_id"], spec["beam_benchmark"]["tip_point_id"]
        spec["geometry_catalog"]["points"] = [{"id":root_id,"xyz_m":[0,0,0]},{"id":tip_id,"xyz_m":tip}]
        spec["design_space"]["bounds"] = {"min":[min(0,x)-diameter for x in tip],"max":[max(0,x)+diameter for x in tip]}
        spec["constraints"]["minimum_feature_m"] = diameter
        material_id = spec["beam_benchmark"]["material_id"]
        spec["materials"] = [{"id":material_id,"youngs_modulus_pa":case["youngs_modulus_pa"],"density_kg_m3":2700,"provenance":provenance}]
        candidate, length, diameter, youngs, _ = beam_geometry(spec)
        q, force, moment = case["q_n_m"], case["tip_force_n"], case["tip_moment_nm"]
        rows = [solve(length,youngs,diameter,q,force,moment,n,backend) for n in case["meshes"]]
        ei = youngs*math.pi*diameter**4/64
        # References follow continuum force/moment balance, not the assembly.
        expected = {"tip_displacement_m":(q*length**4/8+force*length**3/3+moment*length**2/2)/ei,
                    "tip_rotation_rad":(q*length**3/6+force*length**2/2+moment*length)/ei,
                    "root_reaction_n":-(q*length+force),
                    "root_reaction_moment_nm":-(q*length**2/2+force*length+moment)}
        agreement = all(math.isclose(row[key],value,rel_tol=1e-7,abs_tol=1e-11) for row in rows for key,value in expected.items())
        if q:
            interior = all(15.5 < a["displacement_l2_error_m_sqrt_m"]/b["displacement_l2_error_m_sqrt_m"] < 16.5
                and 3.95 < a["curvature_l2_error_per_sqrt_m"]/b["curvature_l2_error_per_sqrt_m"] < 4.05 for a,b in zip(rows,rows[1:]))
        else:
            interior = all(r["relative_displacement_l2_error"] <= 1e-7 and r["relative_curvature_l2_error"] <= 1e-7 for r in rows)
        records.append({"case_id":case["id"],"passed":agreement and interior,"parameters":case,
                        "topology_sha256":candidate["topology_sha256"],"analytic":expected,
                        "tip_and_reaction_agreement_passed":agreement,"interior_check_passed":interior,"meshes":rows})
    return {"schema_version":"0.1","protocol":manifest["protocol"],"statistically_blind":False,
            "promotion_authority":False,"material_provenance":provenance,
            "manifest_sha256":hashlib.sha256(json.dumps(manifest,sort_keys=True,allow_nan=False).encode()).hexdigest(),
            "passed":all(r["passed"] for r in records),"cases":records}
