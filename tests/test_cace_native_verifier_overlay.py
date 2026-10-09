#!/usr/bin/env python3
"""Read-only CACE native verifier-hardening regression on an isolated overlay.

Only a pinned analytic 1D Poisson fixture can receive a benchmark interval
PASS, with direct exact rational squared-energy verification. This never
promotes a general a-posteriori PDE theorem.
"""
import argparse,copy,hashlib,json,math,sys
from fractions import Fraction as F
from pathlib import Path

EXPECTED_ORIGINAL_CACE="66b22a71ff52b3110269f5994a5fd0716a2054c1"
SHARED_MODEL="pinned-poisson-1d-f1-dirichlet0-v1"

def state(record):
    out=str(record[0].state).upper()
    if "PASS" in out:return True
    if "FAIL" in out:return False
    raise AssertionError("unknown state")

def need_fail(cl,inputs,params,out,reason):
    records=cl.verify(None,inputs,params,out,None)
    if state(records):
        raise AssertionError("native verifier accepted "+reason)
    return reason

def tightly_bracket_energy(mesh,solution):
    # Treat stored binary64 observations as exact rational values and
    # enclose sqrt of their analytic Poisson energy error by integer sqrt.
    import math
    x=[F.from_float(float(v)) for v in mesh["vertices"]]
    y=[F.from_float(float(v)) for v in solution["values"]]
    h=[x[i+1]-x[i] for i in range(len(x)-1)]
    d=[y[i]-x[i]*(1-x[i])/2 for i in range(len(x))]
    error2=sum((step**3/12 for step in h),F(0))+sum(
        ((d[i+1]-d[i])**2/h[i] for i in range(len(h))),F(0))
    scale=10**12
    k=math.isqrt((error2.numerator*scale*scale)//error2.denominator)
    lo=0.0 if k==0 else math.nextafter(float(F(k,scale)),-math.inf)
    hi=math.nextafter(float(F(k+1,scale)),math.inf)
    assert (F.from_float(lo)**2<=error2<=F.from_float(hi)**2)
    assert 0<=hi-lo<=1e-10
    return [lo,hi]


def run(root):
    import numpy as np
    sys.path.insert(0,str(root))
    from cace_studio.modules.fem import (
        ArbitraryMesh1D,P1ShapeFunctions,PoissonAssembly1D,
        LinearPDESolver,AlgebraicResidual,AposterioriEstimator1D,
        PipelineCertificate)
    schedules=[
        ("two",[F(0),F(1)]),
        ("uniform_3",[F(0),F(1,2),F(1)]),
        ("uniform_5",[F(i,4) for i in range(5)]),
        ("uniform_9",[F(i,8) for i in range(9)]),
        ("uniform_17",[F(i,16) for i in range(17)]),
        ("uniform_33",[F(i,32) for i in range(33)]),
        ("graded",[F(0),F(1,32),F(1,16),F(1,8),F(1,4),F(1,2),F(3,4),F(1)]),
        ("irregular",[F(0),F(1,8),F(1,3),F(3,4),F(1)]),
    ]
    verified=[]
    for name,xs in schedules:
        mesh=ArbitraryMesh1D.execute(None,{},{"vertices":",".join(map(str,map(float,xs)))},None)["mesh"]
        model=PoissonAssembly1D.execute(None,{"mesh":mesh},{},None)["system"]
        solution=LinearPDESolver.execute(None,{"system":model},{},None)["solution"]
        residual=AlgebraicResidual.execute(None,{"system":model,"solution":solution},{},None)
        estimator=AposterioriEstimator1D.execute(None,{"mesh":mesh,"solution":solution},{},None)["estimator"]
        assert state(AlgebraicResidual.verify(None,{"system":model,"solution":solution},{},residual,None))
        assert state(AposterioriEstimator1D.verify(None,{"mesh":mesh,"solution":solution},{},{"estimator":estimator},None))
        params={"residual_tolerance":1e-10}
        inp={"residual_inf":residual["residual_inf"],"error_interval":tightly_bracket_energy(mesh,solution),
             "benchmark_model_id":SHARED_MODEL,"refined_mesh":mesh,
             "solution":solution,"system":model,"estimator":estimator}
        output=PipelineCertificate.execute(None,inp,params,None)
        assert state(PipelineCertificate.verify(None,inp,params,output,None)),name
        verified.append({"name":name,"vertices":len(xs),
            "residual":residual["residual_inf"],"benchmark_pass":True,
            "general_pde_certificate":False})
    # Use the nontrivial uniform-9 fixture for adversarial checks.
    xs=[F(i,8) for i in range(9)]
    mesh=ArbitraryMesh1D.execute(None,{},{"vertices":",".join(map(str,map(float,xs)))},None)["mesh"]
    model=PoissonAssembly1D.execute(None,{"mesh":mesh},{},None)["system"]
    sol=LinearPDESolver.execute(None,{"system":model},{},None)["solution"]
    res=AlgebraicResidual.execute(None,{"system":model,"solution":sol},{},None)
    eta=AposterioriEstimator1D.execute(None,{"mesh":mesh,"solution":sol},{},None)["estimator"]
    params={"residual_tolerance":1e-10}
    source={"residual_inf":res["residual_inf"],"error_interval":tightly_bracket_energy(mesh,sol),
            "benchmark_model_id":SHARED_MODEL,
            "refined_mesh":mesh,"solution":sol,"system":model,"estimator":eta}
    cert=PipelineCertificate.execute(None,source,params,None)
    rejected=[]
    badsol=copy.deepcopy(sol);badsol["values"][1]+=0.25;badsol["interior"][0]+=0.25
    badres=AlgebraicResidual.execute(None,{"system":model,"solution":badsol},{},None)
    rejected.append(need_fail(AlgebraicResidual,{"system":model,"solution":badsol},{},badres,"inaccurate finite residual"))
    wrongr=copy.deepcopy(res);wrongr["residual_inf"]=1.
    rejected.append(need_fail(AlgebraicResidual,{"system":model,"solution":sol},{},wrongr,"forged residual scalar"))
    wrv=copy.deepcopy(res);wrv["residual"][0]=0.5
    rejected.append(need_fail(AlgebraicResidual,{"system":model,"solution":sol},{},wrv,"forged residual vector"))
    empty=copy.deepcopy(eta);empty["eta"]=0.;empty["element_eta"]=[0.]*8
    rejected.append(need_fail(AposterioriEstimator1D,{"mesh":mesh,"solution":sol},{},{"estimator":empty},"forged zero estimator"))
    fake=copy.deepcopy(eta);fake["element_eta"][0]+=0.2
    rejected.append(need_fail(AposterioriEstimator1D,{"mesh":mesh,"solution":sol},{},{"estimator":fake},"corrupted local eta"))
    broken=copy.deepcopy(source);broken["error_interval"]=[0.,0.]
    summary=PipelineCertificate.execute(None,broken,params,None)
    rejected.append(need_fail(PipelineCertificate,broken,params,summary,"fabricated exact-zero error interval"))
    broken=copy.deepcopy(source);broken["error_interval"]=[1.,0.1]
    summary=PipelineCertificate.execute(None,broken,params,None)
    rejected.append(need_fail(PipelineCertificate,broken,params,summary,"reversed interval"))
    broken=copy.deepcopy(source);broken["benchmark_model_id"]="arbitrary-PDE"
    summary=PipelineCertificate.execute(None,broken,params,None)
    rejected.append(need_fail(PipelineCertificate,broken,params,summary,"unqualified PDE identity"))
    broken=copy.deepcopy(source);broken.pop("benchmark_model_id")
    summary=PipelineCertificate.execute(None,broken,params,None)
    rejected.append(need_fail(PipelineCertificate,broken,params,summary,"missing provenance"))
    broken=copy.deepcopy(source);broken["estimator"]=empty
    summary=PipelineCertificate.execute(None,broken,params,None)
    rejected.append(need_fail(PipelineCertificate,broken,params,summary,"forged pipeline estimator"))
    broken=copy.deepcopy(source);broken["residual_inf"]=0.3
    summary=PipelineCertificate.execute(None,broken,params,None)
    rejected.append(need_fail(PipelineCertificate,broken,params,summary,"inaccurate pipeline residual"))
    broken=copy.deepcopy(source);broken["system"]=copy.deepcopy(model)
    broken["system"]["rhs"][0]+=0.3
    summary=PipelineCertificate.execute(None,broken,params,None)
    rejected.append(need_fail(PipelineCertificate,broken,params,summary,"altered Poisson load"))
    broken=copy.deepcopy(source);broken["solution"]=badsol
    summary=PipelineCertificate.execute(None,broken,params,None)
    rejected.append(need_fail(PipelineCertificate,broken,params,summary,"altered FEM solution"))
    forged_output=copy.deepcopy(cert)
    forged_output["certificate_summary"]["benchmark_energy_error_interval"]=[0.,0.]
    rejected.append(need_fail(PipelineCertificate,source,params,forged_output,"altered certificate output"))
    broken=copy.deepcopy(source);broken["error_interval"]=[0.,1.]
    summary=PipelineCertificate.execute(None,broken,params,None)
    rejected.append(need_fail(PipelineCertificate,broken,params,summary,"vacuously broad interval"))
    extreme_params={"residual_tolerance":1.}
    summary=PipelineCertificate.execute(None,source,extreme_params,None)
    rejected.append(need_fail(PipelineCertificate,source,extreme_params,summary,"oversized residual tolerance"))
    return {"schema_version":1,"experiment":"cace-native-gates-local-overlay-v1",
            "cace_source_commit":EXPECTED_ORIGINAL_CACE,
            "local_patched_runtime_exercised":True,
            "verified_benchmark_meshes":len(verified),
            "meshes":verified,"native_adversarial_controls_rejected":len(rejected),
            "mutations":rejected,"source_problem":"exact 1D -u''=1, u(0)=u(1)=0",
            "squared_energy_error_formula":"sum h^3/12 + sum (delta[i+1]-delta[i])^2/h",
            "general_pde_reliability_bound_proven":False,
            "broad_chemical_reaction_model_qualified":False,
            "remote_cace_repository_modified":False,
            "production_promoted":False,
            "authority_expanded":False}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--cace-repo",type=Path,required=True)
    p.add_argument("-o","--output",type=Path,required=True)
    args=p.parse_args()
    result=run(args.cace_repo.resolve())
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("meshes","mutations")}))
