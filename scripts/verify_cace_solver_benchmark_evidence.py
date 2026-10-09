#!/usr/bin/env python3
"""Independent, fail-closed replay of one analytically solvable CACE FEM fixture.

This is a strict *benchmark* evidence checker, not a general a posteriori
error theorem or an attestation of provenance from untrusted JSON alone.
GitHub workflow independently binds the CACE source to a pinned SHA.
"""
import argparse,copy,json,math
from fractions import Fraction as F
from pathlib import Path

CACE_SHA="66b22a71ff52b3110269f5994a5fd0716a2054c1"
FEM_SHA="73742096c73386f83727841ac7eb6efacfebef11ce8ab24b3f4a03bf682a74c1"

def cases():
    out=[("uniform_"+str(n),[F(i,n-1) for i in range(n)])
         for n in (2,3,5,9,17,33)]
    out.extend([
      ("graded_8",[F(0),F(1,32),F(1,16),F(1,8),F(1,4),F(1,2),F(3,4),F(1)]),
      ("irregular_5",[F(0),F(1,8),F(1,3),F(3,4),F(1)])
    ])
    return out

def num(x):
    if type(x) not in (int,float) or not math.isfinite(float(x)):
        raise ValueError("non-finite or untyped numerical value")
    return float(x)

def near(a,b,tol=5e-11):
    if abs(num(a)-float(b))>tol:
        raise ValueError("numeric statement disagrees with independent oracle")

def exact_matrix(xs):
    n=len(xs); matrix=[[F(0) for _ in range(n)] for _ in range(n)]
    loads=[F(0) for _ in range(n)]
    for i in range(n-1):
        h=xs[i+1]-xs[i]
        if h<=0:raise ValueError("nonpositive element")
        for a,b,k in ((i,i,F(1,h)),(i+1,i+1,F(1,h)),(i,i+1,-F(1,h)),(i+1,i,-F(1,h))):
            matrix[a][b]+=k
        loads[i]+=h/2
        loads[i+1]+=h/2
    interior=range(1,n-1)
    return [[matrix[i][j] for j in interior] for i in interior], [loads[i] for i in interior]

def verify(report):
    if not isinstance(report,dict) or report.get("schema_version")!=1:
        raise ValueError("not a known FEM report")
    if report.get("cace_sha")!=CACE_SHA or report.get("fem_source_sha256")!=FEM_SHA:
        raise ValueError("CACE source not pinned")
    flags={
       "real_cace_mesh_shape_assembly_solver_residual_estimator_invoked":True,
       "finite_nonzero_residual_accepted_by_cace_residual_finite_check":True,
       "corrupted_solution_rejected_by_cace_solver_tolerance_check":True,
       "tampered_zero_estimator_accepted_by_cace_wellformed_check":True,
       "externally_detected_fake_estimator":True,
       "externally_detected_changed_rhs":True,
       "untrusted_zero_error_interval_native_summary_passed":True,
       "reversed_error_interval_native_summary_passed":True,
       "independent_interval_validation_required":True,
       "general_pde_a_posteriori_bound_qualified":False,
       "production_promoted":False,
       "authority_expanded":False,
       "published_biological_model_reproduced":False}
    for key,wanted in flags.items():
        if report.get(key) is not wanted:
            raise ValueError("scope/mutation gate "+key)
    expected=cases()
    rows=report.get("meshes")
    if not isinstance(rows,list) or len(rows)!=len(expected) or report.get("passed_meshed_cases")!=8:
        raise ValueError("missing required mesh cases")
    max_residual=0.
    for row,(name,xs) in zip(rows,expected):
        if row.get("mesh")!=name or row.get("vertices")!=len(xs) or row.get("interior_dofs")!=len(xs)-2:
            raise ValueError("unmatched mesh identity")
        if row.get("mesh_nodes_exact")!=[str(x) for x in xs]:
            raise ValueError("exact mesh changed")
        observed_nodes=row.get("cace_mesh_vertices")
        if not isinstance(observed_nodes,list) or len(observed_nodes)!=len(xs):
            raise ValueError("missing CACE nodes")
        for a,b in zip(observed_nodes,xs):near(a,b,1e-15)
        A,b=exact_matrix(xs)
        stored_A=row.get("cace_stiffness")
        stored_b=row.get("cace_load_vector")
        if not isinstance(stored_A,list) or len(stored_A)!=len(A) or not isinstance(stored_b,list) or len(stored_b)!=len(b):
            raise ValueError("missing stiffness or load")
        for exact_row,observed_row in zip(A,stored_A):
            if not isinstance(observed_row,list) or len(observed_row)!=len(A):
                raise ValueError("matrix shape mismatch")
            for v,exact in zip(observed_row,exact_row):near(v,exact,5e-11)
        for v,exact in zip(stored_b,b):near(v,exact,5e-12)
        u=row.get("cace_solution_values")
        if not isinstance(u,list) or len(u)!=len(xs):raise ValueError("solution shape")
        expected_u=[x*(1-x)/2 for x in xs]
        for observed,exact in zip(u,expected_u):near(observed,exact,1e-10)
        residual=max((abs(sum(num(stored_A[i][j])*num(u[j+1]) for j in range(len(A)))-num(stored_b[i]))
                      for i in range(len(A))),default=0.)
        near(row.get("residual_inf"),residual,5e-11)
        if residual>2e-11:raise ValueError("solver residual exceeded strict tolerance")
        near(row.get("max_nodal_error"),max(abs(num(v)-float(ref)) for v,ref in zip(u,expected_u)))
        eta_loc=row.get("cace_estimator_local")
        if not isinstance(eta_loc,list) or len(eta_loc)!=len(xs)-1:
            raise ValueError("estimator shape")
        steps=[float(xs[i+1]-xs[i]) for i in range(len(xs)-1)]
        slopes=[(num(u[i+1])-num(u[i]))/steps[i] for i in range(len(steps))]
        jumps=[0.] * len(xs)
        for i in range(1,len(xs)-1):jumps[i]=slopes[i]-slopes[i-1]
        expected_eta=[]
        for i,h in enumerate(steps):
            expected_eta.append(math.sqrt(h**3+0.5*h*(jumps[i]**2+jumps[i+1]**2)))
        for v,ref in zip(eta_loc,expected_eta):near(v,ref,1e-10)
        eta=math.sqrt(sum(v*v for v in expected_eta))
        near(row.get("estimated_eta"),eta,1e-10)
        true2=sum(((xs[i+1]-xs[i])**3/F(12) for i in range(len(xs)-1)),F(0))
        if row.get("energy_error_squared_exact")!=str(true2):
            raise ValueError("exact energy error mismatch")
        true_error=math.sqrt(float(true2))
        near(row.get("energy_error_known"),true_error,1e-13)
        if eta < true_error-1e-10:
            raise ValueError("estimator smaller than known benchmark energy error")
        if row.get("cace_verifiers_pass") is not True:
            raise ValueError("CACE native checks missing")
        max_residual=max(max_residual,residual)
    for n in (5,9,17):
        p=math.sqrt(float(sum(((F(i+1,n-1)-F(i,n-1))**3/F(12)
                               for i in range(n-1)),F(0))))
        q=math.sqrt(float(sum(((F(i+1,2*n-2)-F(i,2*n-2))**3/F(12)
                               for i in range(2*n-2)),F(0))))
        near(p/q,2.,1e-12)
    near(report.get("uniform_energy_error_refinement_ratio"),2.,1e-12)
    return {"benchmark_consistency":True,
            "meshes":len(rows),"max_independently_recomputed_residual":max_residual,
            "independently_replayed":True,"general_pde_error_certificate":False,
            "production_promoted":False}

def mutation_tests(report):
    verify(report)
    targets=[
      ("stiffness",lambda r:r["meshes"][2]["cace_stiffness"][0].__setitem__(0,99.)),
      ("rhs",lambda r:r["meshes"][3]["cace_load_vector"].__setitem__(0,2.)),
      ("solution",lambda r:r["meshes"][4]["cace_solution_values"].__setitem__(1,100.)),
      ("fake_estimator",lambda r:r["meshes"][3].__setitem__("estimated_eta",0.)),
      ("fake_local",lambda r:r["meshes"][3]["cace_estimator_local"].__setitem__(0,0.)),
      ("false_residual",lambda r:r["meshes"][2].__setitem__("residual_inf",0.9)),
      ("fake_energy",lambda r:r["meshes"][1].__setitem__("energy_error_squared_exact","0")),
      ("source_pin",lambda r:r.__setitem__("fem_source_sha256","0"*64)),
      ("changed_mesh",lambda r:r["meshes"][1]["mesh_nodes_exact"].__setitem__(1,"2/3")),
      ("no_evidence",lambda r:r["meshes"].pop()),
      ("claimed_pde",lambda r:r.__setitem__("general_pde_a_posteriori_bound_qualified",True)),
      ("authority",lambda r:r.__setitem__("authority_expanded",True)),
      ("native_false",lambda r:r["meshes"][0].__setitem__("cace_verifiers_pass",False)),
      ("nonfinite",lambda r:r["meshes"][0]["cace_solution_values"].__setitem__(0,float("nan"))),
      ("false_pipeline_interval",lambda r:r.__setitem__("untrusted_zero_error_interval_native_summary_passed",False)),
      ("false_interval_order",lambda r:r.__setitem__("reversed_error_interval_native_summary_passed",False))
    ]
    for name,change in targets:
        bad=copy.deepcopy(report);change(bad)
        try:verify(bad)
        except (ValueError,TypeError,KeyError,ZeroDivisionError):continue
        raise AssertionError("adversarial evidence mutation passed: "+name)
    return len(targets)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("evidence",type=Path)
    args=p.parse_args()
    evidence=json.loads(args.evidence.read_text(encoding="utf-8"),
                        parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON token")))
    outcome=verify(evidence)
    outcome["adversarial_mutations_rejected"]=mutation_tests(evidence)
    print(json.dumps(outcome))
