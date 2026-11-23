#!/usr/bin/env python3
"""Deterministic small-displacement 2D pin-jointed truss FEM for Foundry graphs.

Explicitly limited to linear axial bars in the XY plane. No bending, buckling,
joint mechanics, continuum stresses, out-of-plane stability or interval-certified
CACE error bounds. Uses stdlib linear algebra and independent equilibrium check.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def modeler_module():
    p=ROOT/"scripts"/"generate_research_object_candidates.py"
    spec=importlib.util.spec_from_file_location("research_object_modeler",p)
    module=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def solve_dense(a, b):
    """Scaled pivot selection with fail-closed singular matrix detection."""
    n=len(b)
    if n==0:
        return [], 1.0
    if n>300:
        raise ValueError("too many free DOFs for stdlib reference solver")
    m=[list(map(float,row))+[float(b[i])] for i,row in enumerate(a)]
    norm=max((sum(abs(x) for x in row[:-1]) for row in m),default=0.0)
    if norm<=0:
        raise ValueError("unrestrained zero-stiffness structure")
    pivots=[]
    for j in range(n):
        pivot=max(range(j,n),key=lambda i:abs(m[i][j]))
        value=abs(m[pivot][j])
        if value<=norm*1e-12:
            raise ValueError("singular or nearly singular truss stiffness")
        if pivot!=j:
            m[j],m[pivot]=m[pivot],m[j]
        pivots.append(value)
        for i in range(j+1,n):
            f=m[i][j]/m[j][j]
            m[i][j]=0.0
            for k in range(j+1,n+1):
                m[i][k]-=f*m[j][k]
    result=[0.0]*n
    for i in range(n-1,-1,-1):
        result[i]=(m[i][n]-sum(m[i][j]*result[j] for j in range(i+1,n)))/m[i][i]
    return result, min(pivots)/max(pivots)


def assemble(candidate, youngs, diameter):
    if not candidate.get("feasible_geometric_graph",False):
        raise ValueError("candidate geometry must be feasible")
    if youngs<=0 or diameter<=0 or not all(
        math.isfinite(x) for x in (youngs,diameter)
    ):
        raise ValueError("Young's modulus and diameter must be positive")
    nodes=candidate["node_positions_m"]
    node_ids=sorted(nodes)
    if not node_ids or not candidate["edges"]:
        raise ValueError("empty truss graph")
    ni={node:i for i,node in enumerate(node_ids)}
    dofs=2*len(nodes)
    if dofs>360:
        raise ValueError("too many truss DOFs")
    K=[[0.0]*dofs for _ in range(dofs)]
    area=math.pi*(diameter/2)**2
    bars=[]
    for a,b in candidate["edges"]:
        pa,pb=nodes[a],nodes[b]
        if abs(float(pa[2])-float(pb[2]))>1e-10:
            raise ValueError("truss XY mode does not support out-of-plane struts")
        dx,dy=float(pb[0])-float(pa[0]),float(pb[1])-float(pa[1])
        length=math.hypot(dx,dy)
        if length<=1e-12:
            raise ValueError("zero-length element")
        cx,cy=dx/length,dy/length
        indices=[2*ni[a],2*ni[a]+1,2*ni[b],2*ni[b]+1]
        direction=[-cx,-cy,cx,cy]
        scale=youngs*area/length
        for i in range(4):
            for j in range(4):
                K[indices[i]][indices[j]]+=scale*direction[i]*direction[j]
        bars.append((a,b,length,cx,cy))
    return K,node_ids,area,bars


def analyze(candidate, loadcase, material, diameter):
    if loadcase.get("analysis_plane")!="xy":
        raise ValueError("only XY-plane truss analysis is available")
    youngs=material.get("youngs_modulus_pa")
    if youngs is None:
        raise ValueError("material Young's modulus is required")
    E=float(youngs)
    K, ids, area, bars=assemble(candidate,E,diameter)
    index={k:i for i,k in enumerate(ids)}
    ndof=2*len(ids)
    loads=[0.0]*ndof
    fixed=set()
    supports=loadcase.get("supports",[])
    forces=loadcase.get("loads",[])
    if not supports or not forces:
        raise ValueError("structural analysis requires supports and loads")
    for support in supports:
        name=support["point_id"]
        if name not in index:
            raise ValueError(f"unknown support node {name}")
        axes=support.get("fixed",[])
        if not axes or any(x not in ("x","y") for x in axes):
            raise ValueError("invalid support coordinate")
        for axis in axes:
            fixed.add(index[name]*2+(0 if axis=="x" else 1))
    for load in forces:
        name=load["point_id"]
        if name not in index:
            raise ValueError(f"unknown load node {name}")
        v=load["force_n"]
        if len(v)!=2 or not all(math.isfinite(float(x)) for x in v):
            raise ValueError("XY load requires two finite force components")
        loads[2*index[name]]+=float(v[0])
        loads[2*index[name]+1]+=float(v[1])
    free=[i for i in range(ndof) if i not in fixed]
    if not free:
        raise ValueError("no free displacement DOFs")
    solution,pivot_ratio=solve_dense(
        [[K[i][j] for j in free] for i in free],
        [loads[i] for i in free],
    )
    u=[0.0]*ndof
    for i,value in zip(free,solution):
        u[i]=value
    reactions=[
        sum(K[i][j]*u[j] for j in range(ndof))-loads[i]
        for i in range(ndof)
    ]
    force_scale=max(1.0,max((abs(x) for x in loads),default=0.0))
    residual=max((abs(reactions[i]) for i in free),default=0.0)
    if residual>1e-7*force_scale:
        raise ValueError("structural solve violates free-DOF equilibrium")
    if any(not math.isfinite(x) for x in u+reactions):
        raise ValueError("non-finite structural response")
    bar_outputs=[]
    for a,b,length,cx,cy in bars:
        ia,ib=2*index[a],2*index[b]
        extension=(u[ib]-u[ia])*cx+(u[ib+1]-u[ia+1])*cy
        stress=E*extension/length
        bar_outputs.append({
            "endpoints":[a,b],
            "length_m":length,
            "axial_strain":extension/length,
            "axial_stress_pa":stress,
            "axial_force_n":stress*area,
        })
    max_disp=max(math.hypot(u[2*i],u[2*i+1]) for i in range(len(ids)))
    max_stress=max(abs(b["axial_stress_pa"]) for b in bar_outputs)
    external_work=sum(loads[i]*u[i] for i in range(ndof))
    strain_energy=0.5*external_work
    if strain_energy<-1e-10:
        raise ValueError("negative elastic strain energy")
    allowable=loadcase.get("allowable_stress_pa")
    cap=loadcase.get("maximum_displacement_m")
    failures=[]
    if allowable is not None and max_stress>float(allowable):
        failures.append("allowable_axial_stress")
    if cap is not None and max_disp>float(cap):
        failures.append("maximum_displacement")
    return {
        "candidate_id":candidate["candidate_id"],
        "analysis":"2d_pin_joint_axial_linear_truss",
        "node_displacements_m":{
            k:{"ux":u[2*i],"uy":u[2*i+1]}
            for i,k in enumerate(ids)
        },
        "max_displacement_m":max_disp,
        "max_abs_axial_stress_pa":max_stress,
        "element_results":bar_outputs,
        "compliance_j":external_work,
        "strain_energy_j":strain_energy,
        "max_free_dof_residual_n":residual,
        "min_relative_pivot":pivot_ratio,
        "sum_applied_force_n":[
            sum(loads[2*i+j] for i in range(len(ids))) for j in (0,1)
        ],
        "sum_support_reaction_n":[
            sum(reactions[2*i+j] for i in range(len(ids))) for j in (0,1)
        ],
        "constraint_violations":failures,
        "passes_declared_truss_limits":not failures,
        "assumptions":[
            "small displacements and isotropic linear axial elasticity",
            "zero-moment pin joints with no bending or buckling",
            "XY-plane loads, supports, and coplanar elements",
        ],
        "evidence_ceiling":"2d_axial_truss_fem_proxy_not_cace_interval_certified",
    }


def truss_pareto_ids(rows):
    """Non-dominated declared-limit-passing trusses by mass/compliance/stress."""
    qualified = [r for r in rows if r["passes_declared_truss_limits"]
                 and r.get("mass_proxy_kg") is not None]
    metrics = ("mass_proxy_kg", "compliance_j", "max_abs_axial_stress_pa")
    result = []
    for row in qualified:
        dominated = any(
            all(other[k] <= row[k] + 1e-12 * max(1.0, abs(row[k]))
                for k in metrics)
            and any(other[k] < row[k] - 1e-12 * max(1.0, abs(row[k]))
                    for k in metrics)
            for other in qualified if other is not row
        )
        if not dominated:
            result.append(row["candidate_id"])
    return sorted(result)


def evaluate(spec, loadcase):
    modeler=modeler_module()
    generated=modeler.generate(spec)
    name=loadcase.get("material_id")
    mats=[m for m in spec["materials"] if m["id"]==name]
    if len(mats)!=1:
        raise ValueError("unique named material required")
    diameter=generated["assumed_minimum_strut_diameter_m"]
    if diameter<=0:
        raise ValueError("positive minimum strut diameter required")
    results=[]
    failures=[]
    for candidate in generated["ranked_survivors"]:
        try:
            row=analyze(candidate,loadcase,mats[0],diameter)
            row["mass_proxy_kg"]=candidate["mass_proxy_kg"]
            results.append(row)
        except ValueError as exc:
            failures.append({"candidate_id":candidate["candidate_id"],
                             "rejection_reason":str(exc)})
    results.sort(key=lambda r:(
        not r["passes_declared_truss_limits"],
        r["compliance_j"],
        r["mass_proxy_kg"] if r["mass_proxy_kg"] is not None else math.inf,
        r["candidate_id"],
    ))
    return {
        "schema_version":1,
        "object_id":spec["object_id"],
        "load_case_id":loadcase["load_case_id"],
        "geometrically_feasible_count":generated["survivor_count"],
        "truss_solved_count":len(results),
        "truss_rejected":failures,
        "ranked_truss_results":results,
        "physics_pareto_candidate_ids":truss_pareto_ids(results),
        "physically_qualified_candidate_count":sum(x["passes_declared_truss_limits"] for x in results),
        "evidence_ceiling":"simplified_pin_joint_2d_fem_not_full_3d_cace_certificate",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("spec",type=Path)
    p.add_argument("loadcase",type=Path)
    p.add_argument("-o","--output",type=Path)
    args=p.parse_args()
    result=evaluate(json.loads(args.spec.read_text(encoding="utf-8")),
                    json.loads(args.loadcase.read_text(encoding="utf-8")))
    rendered=json.dumps(result,sort_keys=True,indent=2)+"\n"
    if args.output:
        args.output.write_text(rendered,encoding="utf-8")
    else:
        print(rendered,end="")


if __name__=="__main__":
    main()
