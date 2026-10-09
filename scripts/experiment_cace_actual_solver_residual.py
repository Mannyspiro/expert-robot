#!/usr/bin/env python3
"""Genuine CACE FEM solver/residual/estimator against exact 1D Poisson oracle.

Model: -u''=1 on [0,1], u(0)=u(1)=0; exact u=x(1-x)/2.
P1 mesh nodal solution matches exact nodal values. Exact squared energy error
for the piecewise-linear interpolant is sum(h^3/12).

Scope: read-only CACE FEM core at immutable SHA; bounded deterministic meshes.
This fixture is NOT a general posteriori PDE certification theorem.
"""
import argparse,hashlib,json,math,sys
from fractions import Fraction as F
from pathlib import Path

CACE_SHA="66b22a71ff52b3110269f5994a5fd0716a2054c1"
FEM_SHA256="73742096c73386f83727841ac7eb6efacfebef11ce8ab24b3f4a03bf682a74c1"

def schedules():
    fixed=[("uniform_"+str(n),[F(i,n-1) for i in range(n)])
           for n in (2,3,5,9,17,33)]
    fixed += [
        ("graded_8",[F(0),F(1,32),F(1,16),F(1,8),F(1,4),F(1,2),F(3,4),F(1)]),
        ("irregular_5",[F(0),F(1,8),F(1,3),F(3,4),F(1)]),
    ]
    return fixed

def exact_oracle(xs):
    n=len(xs);inter=list(range(1,n-1))
    h=[xs[i+1]-xs[i] for i in range(n-1)]
    A=[]; b=[]
    for i in inter:
        row=[]
        for j in inter:
            v=(F(1,h[i-1])+F(1,h[i])) if i==j else (
                -F(1,h[i-1]) if j==i-1 else (-F(1,h[i]) if j==i+1 else F(0)))
            row.append(v)
        A.append(row)
        b.append((h[i-1]+h[i])/2)
    nodal=[x*(1-x)/2 for x in xs]
    interior=[nodal[i] for i in inter]
    for row,bi in zip(A,b):
        assert sum((a*u for a,u in zip(row,interior)),F(0))==bi
    exact_energy_sq=sum((step**3/F(12) for step in h),F(0))
    return A,b,nodal,exact_energy_sq

def verification_states(records):
    result=[]
    for record in records:
        value=getattr(record,"state",None)
        if value is None:
            raise AssertionError("unknown CACE verification-record schema")
        s=str(value).upper()
        if "PASS" in s:
            result.append("PASS")
        elif "FAIL" in s:
            result.append("FAIL")
        else:
            raise AssertionError("unknown verification state: "+repr(value))
    return result

def run(cace_repo):
    import numpy as np
    p=cace_repo/"cace_studio/modules/fem.py"
    if hashlib.sha256(p.read_bytes()).hexdigest()!=FEM_SHA256:
        raise ValueError("actual FEM source differs from pinned contract")
    sys.path.insert(0,str(cace_repo))
    from cace_studio.modules.fem import (
        ArbitraryMesh1D,P1ShapeFunctions,PoissonAssembly1D,
        LinearPDESolver,AlgebraicResidual,AposterioriEstimator1D,
        _dense_from_csr,
    )
    trials=[]
    for name,xs in schedules():
        args={"vertices":",".join(str(float(x)) for x in xs)}
        mesh=ArbitraryMesh1D.execute(None,{},args,None)["mesh"]
        assert len(mesh["vertices"])==len(xs)
        assert all(abs(y-float(x))<1e-15 for y,x in zip(mesh["vertices"],xs))
        space=P1ShapeFunctions.execute(None,{"mesh":mesh},{},None)
        model=PoissonAssembly1D.execute(None,{"mesh":mesh},{},None)["system"]
        solution=LinearPDESolver.execute(None,{"system":model},{},None)["solution"]
        residual=AlgebraicResidual.execute(None,{"system":model,"solution":solution},{},None)
        estimator=AposterioriEstimator1D.execute(None,{"mesh":mesh,"solution":solution},{},None)["estimator"]
        A,b,nodal,energy2=exact_oracle(xs)
        Ad=np.asarray(_dense_from_csr(model["matrix"]),float)
        assert Ad.shape==(len(A),len(A))
        for i in range(len(A)):
            assert abs(float(b[i])-float(model["rhs"][i]))<1e-12
            assert all(abs(float(A[i][j])-float(Ad[i,j]))<3e-12
                       for j in range(len(A)))
        values=solution["values"]
        assert len(values)==len(xs)
        nodal_error=max(abs(float(z)-float(exact)) for z,exact in zip(values,nodal))
        assert nodal_error<=1e-10, (name,"nodal error",nodal_error)
        assert float(residual["residual_inf"])<=2e-11
        assert all(math.isfinite(float(z)) and z>=0 for z in values)
        assert verification_states(ArbitraryMesh1D.verify(
            None,{},args,{"mesh":mesh},None))==["PASS"]
        assert verification_states(P1ShapeFunctions.verify(
            None,{"mesh":mesh},{},space,None))==["PASS"]
        assert verification_states(PoissonAssembly1D.verify(
            None,{"mesh":mesh},{},{"system":model},None))==["PASS"]
        assert verification_states(LinearPDESolver.verify(
            None,{"system":model},{},{"solution":solution},None))==["PASS"]
        assert verification_states(AlgebraicResidual.verify(
            None,{"system":model,"solution":solution},{},residual,None))==["PASS"]
        assert verification_states(AposterioriEstimator1D.verify(
            None,{"mesh":mesh,"solution":solution},{},{"estimator":estimator},None))==["PASS"]
        exact_energy=math.sqrt(float(energy2))
        eta=float(estimator["eta"])
        assert math.isfinite(eta) and eta>=exact_energy-1e-11
        trials.append({"mesh":name,"vertices":len(xs),"interior_dofs":len(A),
                       "mesh_nodes_exact":[str(z) for z in xs],
                       "cace_mesh_vertices":[float(z) for z in mesh["vertices"]],
                       "cace_stiffness":Ad.tolist(),
                       "cace_load_vector":[float(z) for z in model["rhs"]],
                       "cace_solution_values":[float(z) for z in values],
                       "cace_estimator_local":[float(z) for z in estimator["element_eta"]],
                       "energy_error_squared_exact":str(energy2),
                       "energy_error_known":exact_energy,
                       "estimated_eta":eta,
                       "residual_inf":float(residual["residual_inf"]),
                       "max_nodal_error":nodal_error,
                       "cace_verifiers_pass":True})
    # Critically, the AlgebraicResidual verifier accepts a *finite* but
    # nonzero residual. Our external numerical gate must reject it.
    xs=[F(i,8) for i in range(9)]
    mesh=ArbitraryMesh1D.execute(None,{},{"vertices":",".join(str(float(x)) for x in xs)},None)["mesh"]
    system=PoissonAssembly1D.execute(None,{"mesh":mesh},{},None)["system"]
    sol=LinearPDESolver.execute(None,{"system":system},{},None)["solution"]
    badsol={"values":list(sol["values"]),"interior":list(sol["interior"])}
    badsol["interior"][0]+=0.25
    badsol["values"][1]+=0.25
    badres=AlgebraicResidual.execute(None,{"system":system,"solution":badsol},{},None)
    assert badres["residual_inf"]>1e-3
    assert verification_states(AlgebraicResidual.verify(
        None,{"system":system,"solution":badsol},{},badres,None))==["PASS"]
    assert verification_states(LinearPDESolver.verify(
        None,{"system":system},{},{"solution":badsol},None))==["FAIL"]
    # Estimator verifier checks only nonnegativity/finiteness and accepts
    # a tampered zero estimator; independent known energy-error oracle
    # must reject that false certificate.
    fake={"estimator":{"eta":0.0,"element_eta":[0.0]*8}}
    assert verification_states(AposterioriEstimator1D.verify(
        None,{"mesh":mesh,"solution":sol},{},fake,None))==["PASS"]
    assert math.sqrt(float(exact_oracle(xs)[-1]))>0
    # Strong source consistency check: RHS corruption may preserve
    # a solver's own algebraic residual but violates the true PDE fixture.
    badmodel=dict(system);badmodel["rhs"]=list(system["rhs"])
    badmodel["rhs"][0]+=0.5
    wrongsol=LinearPDESolver.execute(None,{"system":badmodel},{},None)["solution"]
    assert verification_states(LinearPDESolver.verify(
        None,{"system":badmodel},{},{"solution":wrongsol},None))==["PASS"]
    assert abs(wrongsol["values"][1]-float(xs[1]*(1-xs[1])/2))>1e-4
    errors={x["mesh"]:x["energy_error_known"] for x in trials}
    for n in (5,9,17):
        ratio=errors["uniform_"+str(n)]/errors["uniform_"+str(2*n-1)]
        assert abs(ratio-2.0)<1e-12, (n,ratio)
    return {
       "schema_version":1,
       "experiment":"cace-genuine-fem-poisson-solver-residual-v1",
       "cace_sha":CACE_SHA,
       "fem_source_sha256":FEM_SHA256,
       "source_exact_problem":"-u''=1 on (0,1), u(0)=u(1)=0",
       "analytic_solution":"u(x)=x(1-x)/2",
       "meshes":trials,
       "passed_meshed_cases":len(trials),
       "uniform_energy_error_refinement_ratio":2.0,
       "exact_energy_error_squared_formula":"sum(h^3/12)",
       "real_cace_mesh_shape_assembly_solver_residual_estimator_invoked":True,
       "finite_nonzero_residual_accepted_by_cace_residual_finite_check":True,
       "corrupted_solution_rejected_by_cace_solver_tolerance_check":True,
       "tampered_zero_estimator_accepted_by_cace_wellformed_check":True,
       "externally_detected_fake_estimator":True,
       "externally_detected_changed_rhs":True,
       "general_pde_a_posteriori_bound_qualified":False,
       "proof_that_arbitrary_chemical_reaction_is_conservative":False,
       "published_biological_model_reproduced":False,
       "production_promoted":False,
       "authority_expanded":False
    }

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--cace-repo",type=Path,required=True)
    parser.add_argument("-o","--output",type=Path,required=True)
    args=parser.parse_args()
    report=run(args.cace_repo.resolve())
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="meshes"}))
