#!/usr/bin/env python3
"""Run the CRL->CACE ND bridge against an actual CACE checkout."""

from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

bridge=load("compile_crl_to_cace_nd",ROOT/"scripts"/"compile_crl_to_cace_nd.py")

def run_module(cls, inputs, params, ctx):
    obj=cls()
    validation=None
    if hasattr(obj,"validate"):
        validation=obj.validate(inputs,params)
    outputs=obj.execute(inputs,params,ctx)
    verification=None
    if hasattr(obj,"verify"):
        verification=obj.verify(inputs,params,outputs,ctx)
    return outputs,validation,verification

def main():
    p=argparse.ArgumentParser()
    p.add_argument("cace_root",type=Path)
    p.add_argument("crl",type=Path)
    p.add_argument("-o","--output",type=Path)
    args=p.parse_args()

    sys.path.insert(0,str(args.cace_root))
    from cace_studio.modules.fem_nd import (
        SimplexMeshND,P1SimplexSpaceND,SimplexQuadratureND,
        PoissonAssemblyND,LinearSolverND,AlgebraicResidualND,
        ResidualEstimatorND,AdaptiveRefinement2D,
        ConvergenceStudyND,FEMNDCertificate,
    )
    from cace_studio.modules.fem_cert import (
        CertifiedPoissonAssembly,IntervalAlgebraicResidual,
        DiscreteEnergyErrorCertificate,EstimatorReliabilityGate,
    )

    classes={c.__name__:c for c in [
        SimplexMeshND,P1SimplexSpaceND,SimplexQuadratureND,
        PoissonAssemblyND,LinearSolverND,AlgebraicResidualND,
        ResidualEstimatorND,AdaptiveRefinement2D,
        ConvergenceStudyND,FEMNDCertificate,
        CertifiedPoissonAssembly,IntervalAlgebraicResidual,
        DiscreteEnergyErrorCertificate,EstimatorReliabilityGate,
    ]}

    ir=bridge.crl.parse(args.crl.read_text(encoding="utf-8"),str(args.crl))
    packet=bridge.build(ir,segments=32,source=1.0,theta=0.5)
    ctx={}
    store={}
    report={"schema_version":1,"experiment_id":ir["experiment_id"],"routes":{}}

    for route_name in ("nd_poisson_adaptive","certified_algebraic"):
        route_report=[]
        route_store={}
        for node in packet["routes"][route_name]["nodes"]:
            inputs={}
            for key,ref in node["inputs"].items():
                node_id,output_key=ref.split(".",1)
                source=route_store.get(node_id) or store.get(node_id)
                if source is None:
                    raise KeyError(f"unresolved node reference {ref}")
                inputs[key]=source[output_key]
            outputs,validation,verification=run_module(
                classes[node["module"]],inputs,node["params"],ctx
            )
            route_store[node["id"]]=outputs
            store[node["id"]]=outputs
            route_report.append({
                "id":node["id"],
                "module":node["module"],
                "output_keys":sorted(outputs.keys()),
                "validation":validation,
                "verification":verification,
            })
        report["routes"][route_name]=route_report

    residual=store["residual"]["residual_inf"]
    cert=store["energy_cert"]["algebraic_error_certificate"]
    nd_cert=store["nd_certificate"]["certificate_summary"]
    reliability=store["reliability_gate"]["reliability_status"]
    report["summary"]={
        "residual_inf":residual,
        "energy_certificate_certified":bool(cert.get("certified",False)),
        "energy_error_upper":cert.get("energy_error_upper"),
        "nd_certificate":nd_cert,
        "continuum_reliability_status":reliability,
        "mesh_vertices":len(store["mesh"]["mesh"]["vertices"]),
        "mesh_elements":len(store["mesh"]["mesh"]["elements"]),
        "refined_vertices":len(store["refine"]["refined_mesh"]["vertices"]),
        "refined_elements":len(store["refine"]["refined_mesh"]["elements"]),
        "scope":"actual CACE ND + certified algebraic modules; not continuum portal evidence",
    }

    rendered=json.dumps(report,indent=2,sort_keys=True,default=str)+"\n"
    if args.output:
        args.output.write_text(rendered,encoding="utf-8")
    else:
        print(rendered,end="")

if __name__=="__main__":
    main()
