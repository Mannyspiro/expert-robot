#!/usr/bin/env python3
"""Exact 1D equilibrated-flux error bound for piecewise constant loads, with
read-only real CACE stiffness + linear solver execution.

For -u''=f on [0,1], u(0)=u(1)=0, f constant per mesh element, reconstruct
p=u'=C-int_0^x f(s) ds with C=int_0^1 (1-s)f(s) ds. Thus -p'=f and int p=0.

For any continuous P1 uh with homogeneous boundaries:
  ||u-uh||_energy² = sum_i int_element (p-uh')²
                   = sum_i f_i²*h_i³/12
                      + sum_i (delta_{i+1}-delta_i)²/h_i,
delta = reported nodal uh minus the exact source-integrated u at mesh nodes.
All integrals/identities are computed in fractions.Fraction. Interval upper
and lower endpoints are outward-rounded using integer isqrt; no quadrature.

This bound covers this exactly specified 1D piecewise-constant-load model
only. It is NOT a general variable-coefficient/multidimensional PDE theorem.
"""
import argparse,hashlib,json,math,sys
from fractions import Fraction as F
from pathlib import Path

CACE_SHA="66b22a71ff52b3110269f5994a5fd0716a2054c1"
FEM_SHA="73742096c73386f83727841ac7eb6efacfebef11ce8ab24b3f4a03bf682a74c1"

def fixtures():
    return [
      ("one_element_large_load",[F(0),F(1)],[F(10)]),
      ("zero_forcing",[F(i,4) for i in range(5)],[F(0)]*4),
      ("uniform_mixed",[F(i,4) for i in range(5)],[F(1),F(0),F(-2),F(3)]),
      ("alternating_rational",[F(i,8) for i in range(9)],
          [F(3,2) if i%2 else F(-7,3) for i in range(8)]),
      ("graded_nonuniform",[F(0),F(1,32),F(1,16),F(1,8),F(1,4),F(1,2),F(3,4),F(1)],
          [F(1),F(2),F(-3),F(0),F(5,2),F(-1),F(7,4)]),
      ("refined_nonconstant",[F(i,16) for i in range(17)],
          [F((i*7)%11-5,3) for i in range(16)])
    ]

def exact_oracle(mesh,f):
    xs=[F.from_float(float(v)) for v in mesh]
    h=[xs[i+1]-xs[i] for i in range(len(xs)-1)]
    assert xs[0]==0 and xs[-1]==1 and all(v>0 for v in h)
    assert len(f)==len(h)
    n=len(xs)
    # Exact weak-form P1 assembly for -u''=f piecewise constant.
    full=[[F(0) for _ in range(n)] for _ in range(n)]
    load=[F(0)]*n
    for i,(step,fi) in enumerate(zip(h,f)):
        for a,b,v in ((i,i,1/step),(i+1,i+1,1/step),
                      (i,i+1,-1/step),(i+1,i,-1/step)):
            full[a][b]+=v
        load[i]+=fi*step/2
        load[i+1]+=fi*step/2
    A=[row[1:-1] for row in full[1:-1]]
    b=load[1:-1]
    # Boundary value selects integration constant of the exact flux.
    C=sum((fi*step*(1-(xs[i]+xs[i+1])/2)
            for i,(step,fi) in enumerate(zip(h,f))),F(0))
    prefix=F(0)
    exact_u=[F(0)]
    for fi,step in zip(f,h):
        exact_u.append(exact_u[-1]+(C-prefix)*step-fi*step**2/2)
        prefix+=fi*step
    assert exact_u[-1]==0
    assert all(sum((A[i][j]*exact_u[j+1] for j in range(n-2)),F(0))==b[i]
               for i in range(n-2))
    return xs,h,A,b,exact_u,C

def flux_energy(xs,h,forces,values,reference,C):
    d=[y-ref for y,ref in zip(values,reference)]
    energy_via_interpolation=sum((fi**2*step**3/12 for step,fi in zip(h,forces)),F(0))
    energy_via_interpolation+=sum(((d[i+1]-d[i])**2/step
                                   for i,step in enumerate(h)),F(0))
    # Completely separate exact local flux reconstruction check.
    prefix=F(0)
    energy_via_flux=F(0)
    for i,(step,fi) in enumerate(zip(h,forces)):
        slope=(values[i+1]-values[i])/step
        q=C-prefix-slope
        energy_via_flux+=step*q*q - fi*step*step*q + fi*fi*step**3/3
        prefix+=fi*step
    assert energy_via_interpolation==energy_via_flux
    return energy_via_flux

def tight_interval(energy2):
    if energy2<0:raise ValueError("negative exact energy")
    if energy2==0:return 0.,0.
    scale=10**12
    k=math.isqrt((energy2.numerator*scale*scale)//energy2.denominator)
    lo=0. if k==0 else math.nextafter(float(F(k,scale)),-math.inf)
    hi=math.nextafter(float(F(k+1,scale)),math.inf)
    assert F.from_float(lo)**2<=energy2<=F.from_float(hi)**2
    assert 0<=hi-lo<=1e-10
    return lo,hi

def run(cace_repo):
    import numpy as np
    p=cace_repo/"cace_studio/modules/fem.py"
    if hashlib.sha256(p.read_bytes()).hexdigest()!=FEM_SHA:
        raise ValueError("unpinned FEM assembly/solver source")
    sys.path.insert(0,str(cace_repo))
    from cace_studio.modules.fem import ArbitraryMesh1D,PoissonAssembly1D,LinearPDESolver,AlgebraicResidual,AposterioriEstimator1D,_dense_from_csr
    rows=[]
    lower_bound_failure_detected=False
    for name,rational_nodes,f in fixtures():
        args={"vertices":",".join(map(str,map(float,rational_nodes)))}
        mesh=ArbitraryMesh1D.execute(None,{},args,None)["mesh"]
        xs,h,A,b,u_exact,C=exact_oracle(mesh,f)
        cace_sys=PoissonAssembly1D.execute(None,{"mesh":mesh},{},None)["system"]
        numeric_A=np.asarray(_dense_from_csr(cace_sys["matrix"]),float)
        assert numeric_A.shape==(len(A),len(A))
        for i,row in enumerate(A):
            for j,exact in enumerate(row):
                assert abs(numeric_A[i,j]-float(exact))<1e-10
        # Same CACE stiffness; exact independently reassembled load for f.
        system=dict(cace_sys)
        system["rhs"]=[float(z) for z in b]
        sol=LinearPDESolver.execute(None,{"system":system},{},None)["solution"]
        report=LinearPDESolver.verify(None,{"system":system},{},{"solution":sol},None)
        assert len(report)==1 and "PASS" in str(report[0].state)
        residual=AlgebraicResidual.execute(None,{"system":system,"solution":sol},{},None)
        assert residual["residual_inf"]<1e-10
        assert len(sol["values"])==len(xs)
        assert max(abs(float(u_exact[i])-sol["values"][i]) for i in range(len(xs)))<2e-10
        observed=[F.from_float(float(z)) for z in sol["values"]]
        assert observed[0]==0 and observed[-1]==0
        energy2=flux_energy(xs,h,f,observed,u_exact,C)
        lo,hi=tight_interval(energy2)
        if lo*lo>float(energy2) or hi*hi<float(energy2):
            raise AssertionError("incorrect outward interval")
        # Show why CACE's original f=1 estimator cannot certify general f.
        eta=AposterioriEstimator1D.execute(None,{"mesh":mesh,"solution":sol},{},None)["estimator"]["eta"]
        if float(eta)**2 < float(energy2)-1e-9:
            lower_bound_failure_detected=True
        rows.append({"network":name,"vertices":len(xs),
          "element_loads_exact":[str(x) for x in f],
          "model_boundary_conditions":"homogeneous Dirichlet 0,1",
          "exact_source_integrated_solution_nodes":[str(x) for x in u_exact],
          "reported_solver_values":[float(z) for z in sol["values"]],
          "energy_error_squared_exact":str(energy2),
          "outward_energy_error_interval":[lo,hi],
          "native_f1_estimator":float(eta),
          "native_estimator_proven_reliable":False,
          "recomputed_algebraic_residual_inf":float(residual["residual_inf"]),
          "cace_solver_verified":True})
    assert len(rows)==6 and lower_bound_failure_detected
    return {"schema_version":1,"experiment":"cace-piecewise-constant-1d-equilibrated-flux-v1",
      "cace_source_commit":CACE_SHA,"fem_source_sha256":FEM_SHA,
      "real_cace_linear_solver_executed":True,"piecewise_source_cases":len(rows),
      "independent_rational_assembly_and_flux_oracle":True,
      "both_exact_energy_identities_agree":True,
      "narrow_outward_rational_intervals":True,
      "native_f1_estimator_underestimate_observed":lower_bound_failure_detected,
      "source_specificity":"1D -u''=f, f elementwise constant, homogeneous Dirichlet",
      "general_multidimensional_a_posteriori_certified":False,
      "published_biological_model_validated":False,
      "remote_cace_repository_modified":False,"authority_expanded":False,
      "cases":rows}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--cace-repo",type=Path,required=True)
    p.add_argument("-o","--output",type=Path,required=True)
    args=p.parse_args()
    receipt=run(args.cace_repo.resolve())
    args.output.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in receipt.items() if k!="cases"}))
