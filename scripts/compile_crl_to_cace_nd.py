#!/usr/bin/env python3
"""Compile a concentric-circle CRL experiment into CACE ND execution packets.

Exact CRL geometry remains the source of truth. The mesh is an approximation
whose chord error is reported explicitly.
"""

from __future__ import annotations
import argparse, importlib.util, json, math
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

crl=load("compile_crl",ROOT/"scripts"/"compile_crl.py")

def number(x):
    if isinstance(x,(int,float)):
        return float(x)
    return float(Fraction(str(x)))

def concentric_xy_radii(ir):
    circles=[p for p in ir["geometry"]["primitives"] if p["type"]=="circle"]
    if not circles:
        raise ValueError("at least one CIRCLE is required")
    radii=[]
    for c in circles:
        p=c["parameters"]
        if [number(v) for v in p["center"]] != [0.0,0.0,0.0]:
            raise ValueError("current CACE ND circle compiler requires origin-centered circles")
        if [number(v) for v in p["normal"]] != [0.0,0.0,1.0]:
            raise ValueError("current CACE ND circle compiler requires XY-plane circles")
        r=number(p["radius_m"])
        if r<=0:
            raise ValueError("circle radius must be positive")
        radii.append(r)
    return sorted(set(radii))

def mesh_concentric_disks(radii, segments):
    if segments < 8:
        raise ValueError("segments must be >= 8")
    vertices=[[0.0,0.0]]
    rings=[]
    for r in radii:
        ids=[]
        for i in range(segments):
            a=2.0*math.pi*i/segments
            ids.append(len(vertices))
            vertices.append([r*math.cos(a),r*math.sin(a)])
        rings.append(ids)

    elements=[]
    first=rings[0]
    for i in range(segments):
        elements.append([0, first[i], first[(i+1)%segments]])

    for inner,outer in zip(rings,rings[1:]):
        for i in range(segments):
            j=(i+1)%segments
            elements.append([inner[i], outer[i], outer[j]])
            elements.append([inner[i], outer[j], inner[j]])

    max_r=max(radii)
    chord_error=max_r*(1.0-math.cos(math.pi/segments))
    return {
        "vertices":vertices,
        "elements":elements,
        "dimension":2,
        "circle_radii":radii,
        "segments_per_circle":segments,
        "max_radial_chord_error":chord_error
    }

def build(ir, segments=64, source=1.0, theta=0.5, levels=2, residual_tolerance=1e-10, mesh_semantics=None):
    if mesh_semantics != "filled_disk_surrogate":
        raise ValueError(
            "CACE ND routing requires explicit mesh_semantics='filled_disk_surrogate'; "
            "ritual circle curves are not automatically treated as bulk PDE domains"
        )
    radii=concentric_xy_radii(ir)
    mesh=mesh_concentric_disks(radii,segments)
    vertices=mesh["vertices"]
    elements=mesh["elements"]

    nd_nodes=[
      {"id":"mesh","module":"SimplexMeshND","params":{"vertices":vertices,"elements":elements},"inputs":{}},
      {"id":"space","module":"P1SimplexSpaceND","params":{},"inputs":{"mesh":"mesh.mesh"}},
      {"id":"quadrature","module":"SimplexQuadratureND","params":{},"inputs":{"mesh":"mesh.mesh"}},
      {"id":"assembly","module":"PoissonAssemblyND","params":{"source":source},"inputs":{"mesh":"mesh.mesh","space":"space.space"}},
      {"id":"solve","module":"LinearSolverND","params":{},"inputs":{"system":"assembly.system"}},
      {"id":"residual","module":"AlgebraicResidualND","params":{},"inputs":{"system":"assembly.system","solution":"solve.solution"}},
      {"id":"estimator","module":"ResidualEstimatorND","params":{"source":source},"inputs":{"mesh":"mesh.mesh","solution":"solve.solution"}},
      {"id":"refine","module":"AdaptiveRefinement2D","params":{"theta":theta},"inputs":{"mesh":"mesh.mesh","estimator":"estimator.estimator"}},
      {"id":"history","module":"ConvergenceStudyND","params":{"levels":levels,"source":source},"inputs":{"mesh":"mesh.mesh"}},
      {"id":"nd_certificate","module":"FEMNDCertificate","params":{"residual_tolerance":residual_tolerance},"inputs":{"mesh":"mesh.mesh","residual_inf":"residual.residual_inf","estimator":"estimator.estimator","refined_mesh":"refine.refined_mesh","history":"history.history"}}
    ]

    cert_nodes=[
      {"id":"cert_assembly","module":"CertifiedPoissonAssembly","params":{"diffusion":[[1.0,0.0],[0.0,1.0]],"source_constant":source,"source_linear":[0.0,0.0]},"inputs":{"mesh":"mesh.mesh","space":"space.space"}},
      {"id":"cert_solve","module":"LinearSolverND","params":{},"inputs":{"system":"cert_assembly.system"}},
      {"id":"interval_residual","module":"IntervalAlgebraicResidual","params":{},"inputs":{"system":"cert_assembly.system","solution":"cert_solve.solution"}},
      {"id":"energy_cert","module":"DiscreteEnergyErrorCertificate","params":{},"inputs":{"system":"cert_assembly.system","residual_certificate":"interval_residual.residual_certificate"}},
      {"id":"reliability_gate","module":"EstimatorReliabilityGate","params":{"theorem_id":""},"inputs":{"problem":"cert_assembly.problem","estimator":"estimator.estimator"}}
    ]

    return {
      "schema_version":1,
      "experiment_id":ir["experiment_id"],
      "cace_source_commit":"0e7aa229d3bb57174e281b883ee8af5445f15f75",
      "mesh":mesh,
      "geometry_interpretation":{
        "source_geometry":"concentric ritual boundary curves",
        "mesh_semantics":"filled-disk surrogate domain",
        "warning":"The present PDE mesh treats nested circles as a filled 2D domain. It is not yet a thin-line/material-boundary physical model.",
        "max_radial_chord_error":mesh["max_radial_chord_error"]
      },
      "routes":{
        "nd_poisson_adaptive":{"nodes":nd_nodes},
        "certified_algebraic":{"nodes":[nd_nodes[0],*cert_nodes]}
      },
      "unresolved_certification":[
        "continuum reliability theorem binding",
        "shape certificate",
        "thin-boundary/material interpretation of ritual circle lines"
      ],
      "epistemic_status":"cace_execution_plan_not_solver_result"
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("input",type=Path)
    p.add_argument("--segments",type=int,default=64)
    p.add_argument("--source",type=float,default=1.0)
    p.add_argument("--theta",type=float,default=0.5)
    p.add_argument("--mesh-semantics",choices=["filled_disk_surrogate"],required=True)
    p.add_argument("-o","--output",type=Path)
    args=p.parse_args()
    ir=crl.parse(args.input.read_text(encoding="utf-8"),str(args.input))
    result=build(ir,args.segments,args.source,args.theta,mesh_semantics=args.mesh_semantics)
    rendered=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.write_text(rendered,encoding="utf-8")
    else:
        print(rendered,end="")

if __name__=="__main__":
    main()
