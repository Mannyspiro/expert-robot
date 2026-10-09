#!/usr/bin/env python3
"""Exact-rational equilibrated-flux certificate for bounded 1D Poisson cases.

-u'' = f with u(0)=u(1)=0, piecewise constant f, continuous P1 v and
continuous piecewise affine sigma satisfying -sigma'=f.

The Prager-Synge/hypercircle identity implies:
  ||u'-v'||_L2 <= ||sigma-v'||_L2
under these hypotheses. Here each L2 integral is exact Fraction arithmetic.
No general multidimensional PDE guarantee, no kernel-check of the continuous
functional inequality, no production promotion.
"""
import argparse,copy,hashlib,json,math,sys
from fractions import Fraction as Q
from pathlib import Path

SOURCE_SHA="2ceee478a30e556685e81589f918764d7b4dd4d2830aa5357493a0a64cfd027f"
CACE_SHA="66b22a71ff52b3110269f5994a5fd0716a2054c1"
SOURCE_FEM_SHA="73742096c73386f83727841ac7eb6efacfebef11ce8ab24b3f4a03bf682a74c1"

def source_bytes(path):
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=SOURCE_SHA:
        raise ValueError("source evidence differs from independently pinned CACE artifact")
    obj=json.loads(data.decode("utf-8"))
    # Reuse a fully independent Poisson assembly/estimator replay rather
    # than trusting CACE's self-declared PASS or the source hash alone.
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from verify_cace_solver_benchmark_evidence import verify
    if verify(obj)["benchmark_consistency"] is not True:
        raise ValueError("source FEM evidence did not independently verify")
    return obj

def qfloat(z):
    if type(z) not in (int,float) or not math.isfinite(float(z)):
        raise ValueError("nonfinite or untyped binary64 value")
    return Q.from_float(float(z))

def families(n):
    return {
        "constant":[Q(1)]*n,
        "alternating":[Q(1) if k%2==0 else Q(2) for k in range(n)],
        "signed":[Q(1) if k%2==0 else Q(-1) for k in range(n)],
        "graded":[Q(k+1,n) for k in range(n)]}

def flux_rows(xs,forces,C):
    prefix=Q(0); rows=[]
    for k,fi in enumerate(forces):
        rows.append((C-prefix,-fi))
        prefix+=fi*(xs[k+1]-xs[k])
    return rows

def validate_flux(xs,forces,rows):
    if len(xs)<2 or len(forces)!=len(xs)-1 or len(rows)!=len(forces):
        raise ValueError("invalid flux/mesh dimensions")
    if xs[0]!=0 or xs[-1]!=1 or any(xs[k+1]<=xs[k] for k in range(len(xs)-1)):
        raise ValueError("unqualified domain")
    for k,(fi,(left,slope)) in enumerate(zip(forces,rows)):
        if slope != -fi:
            raise ValueError("non-equilibrated divergence")
        if k and rows[k-1][0]+rows[k-1][1]*(xs[k]-xs[k-1]) !=left:
            raise ValueError("flux jump breaks H(div) conformity")
    return True

def norm2(xs,ys,forces,rows):
    if len(ys)!=len(xs) or ys[0]!=0 or ys[-1]!=0:
        raise ValueError("nonhomogeneous Dirichlet boundary or wrong state")
    validate_flux(xs,forces,rows)
    out=Q(0)
    for k,(left,slope) in enumerate(rows):
        h=xs[k+1]-xs[k]
        gradient=(ys[k+1]-ys[k])/h
        alpha=left-gradient
        out+=h*alpha*alpha + slope*h*h*alpha + slope*slope*h*h*h/3
    if out<0:raise AssertionError("negative exact squared flux majorant")
    return out

def exact_upper(q,places=14):
    if q<0:raise ValueError("negative squared bound")
    scale=10**places
    k=math.isqrt((q.numerator*scale*scale)//q.denominator)
    low=Q(k,scale);high=Q(k+1,scale)
    if not low*low<=q<high*high:raise AssertionError("integer sqrt bracket")
    value=math.nextafter(float(high),math.inf)
    if Q.from_float(value)**2<q:raise AssertionError("invalid outward rounding")
    return value

def exact_reference_constant(xs,forces):
    prefix=Q(0);area=Q(0)
    for k,fi in enumerate(forces):
        h=xs[k+1]-xs[k]
        area+=prefix*h+fi*h*h/2
        prefix+=fi*h
    return area

def produce(evidence):
    if evidence.get("cace_sha")!=CACE_SHA or evidence.get("fem_source_sha256")!=SOURCE_FEM_SHA:
        raise ValueError("source provenance missing")
    original=evidence.get("meshes")
    if not isinstance(original,list) or len(original)!=8:
        raise ValueError("wrong number of pinned CACE solutions")
    certs=[]
    for row in original:
        xs=[qfloat(x) for x in row["cace_mesh_vertices"]]
        ys=[qfloat(y) for y in row["cace_solution_values"]]
        for name,forces in families(len(xs)-1).items():
            Cstar=exact_reference_constant(xs,forces)
            error2=norm2(xs,ys,forces,flux_rows(xs,forces,Cstar))
            for C in (Q(0),Q(1,4),Q(1,2),Cstar,Cstar+Q(1,3)):
                sigma=flux_rows(xs,forces,C)
                value=norm2(xs,ys,forces,sigma)
                gap=(C-Cstar)**2
                if value-error2!=gap or error2<0:
                    raise AssertionError("rational hypercircle identity failed")
                hi=exact_upper(value)
                if Q.from_float(hi)**2<value:raise AssertionError("upper bound is not outward")
                if name=="constant" and C==Q(1,2):
                    if abs(float(error2)-float(Q(row["energy_error_squared_exact"])))>2e-13:
                        raise AssertionError("published CACE Poisson benchmark disagrees")
                certs.append({
                    "mesh":row["mesh"],"forcing":name,
                    "flux_constant":str(C),"flux_left":[str(t[0]) for t in sigma],
                    "flux_slope":[str(t[1]) for t in sigma],
                    "majorant_squared":str(value),
                    "independent_energy_error_squared":str(error2),
                    "hypercircle_gap_squared":str(gap),
                    "outward_upper_float":hi})
    if len(certs)!=160:raise AssertionError("missing test receipts")
    return {"schema":"cace-equilibrated-flux-1d-v1",
            "externally_pinned_cace_evidence_sha256":SOURCE_SHA,
            "cace_source_commit":CACE_SHA,
            "certificates":certs,"validated_exact_cases":len(certs),
            "forcing_profiles":4,"real_cace_meshes":8,
            "forcing_profiles_cace_simulated":1,
            "qualifying_assumptions":"1D Dirichlet Poisson, piecewise-constant f, conforming P1 v, continuous equilibrated piecewise-affine sigma",
            "independent_continuous_hypercircle_proof_in_lean":False,
            "full_general_pde_bound_qualified":False,
            "remote_cace_modified":False,
            "authority_expanded":False}

def verify_receipt(evidence,receipt):
    expected=produce(evidence)
    if not isinstance(receipt,dict) or set(receipt)!=set(expected):
        raise ValueError("unknown/incomplete receipt schema")
    for key in expected:
        if key=="certificates":continue
        if receipt[key]!=expected[key]:
            raise ValueError("unqualified receipt field: "+key)
    observed=receipt["certificates"]
    if not isinstance(observed,list) or len(observed)!=len(expected["certificates"]):
        raise ValueError("missing flux certificates")
    for k,(claim,ref) in enumerate(zip(observed,expected["certificates"])):
        if not isinstance(claim,dict) or set(claim)!=set(ref):
            raise ValueError("malformed entry")
        for field in ref:
            if claim[field]!=ref[field]:
                raise ValueError("false numerical/flux certificate "+str(k)+"/"+field)
    return True

def negative_tests(evidence,valid):
    tests=[
      ("changed_flux_slope",lambda r:r["certificates"][0]["flux_slope"].__setitem__(0,"0")),
      ("jump_flux",lambda r:r["certificates"][1]["flux_left"].__setitem__(1,"2")),
      ("forged_upper",lambda r:r["certificates"][8].update(outward_upper_float=0.)),
      ("wrong_source_hash",lambda r:r.update(externally_pinned_cace_evidence_sha256="0"*64)),
      ("wrong_cace_rev",lambda r:r.update(cace_source_commit="unknown")),
      ("fake_hypercircle_lean",lambda r:r.update(independent_continuous_hypercircle_proof_in_lean=True)),
      ("claimed_general",lambda r:r.update(full_general_pde_bound_qualified=True)),
      ("authority",lambda r:r.update(authority_expanded=True)),
      ("missing",lambda r:r["certificates"].pop()),
      ("invalid_majorant",lambda r:r["certificates"][12].update(majorant_squared="0")),
      ("wrong_force",lambda r:r["certificates"][9].update(forcing="constant")),
      ("fake_error",lambda r:r["certificates"][14].update(independent_energy_error_squared="0")),
      ("fake_gap",lambda r:r["certificates"][18].update(hypercircle_gap_squared="-1")),
      ("nonfinite",lambda r:r["certificates"][13].update(outward_upper_float=float("nan"))),
      ("negative_upper",lambda r:r["certificates"][11].update(outward_upper_float=-1.)),
      ("unsupported_flows",lambda r:r.update(forcing_profiles_cace_simulated=4)),
    ]
    count=0
    for name,mut in tests:
        corrupted=copy.deepcopy(valid);mut(corrupted)
        try:verify_receipt(evidence,corrupted)
        except (ValueError,TypeError,KeyError):count+=1;continue
        raise AssertionError("forged certificate accepted: "+name)
    # Validate genuinely non-equilibrated alternatives as well.
    xs=[Q(0),Q(1,2),Q(1)]
    f=[Q(1),Q(2)]
    validrows=flux_rows(xs,f,Q(1,2))
    assert validate_flux(xs,f,validrows)
    invalid=[
       [(validrows[0][0],Q(0)),validrows[1]],
       [validrows[0],(validrows[1][0]+Q(1,8),validrows[1][1])],
    ]
    for bad in invalid:
        try:validate_flux(xs,f,bad)
        except ValueError:count+=1;continue
        raise AssertionError("invalid divergence or flux discontinuity accepted")
    return count

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source-evidence",type=Path,required=True)
    p.add_argument("-o","--output",type=Path,required=True)
    args=p.parse_args()
    source=source_bytes(args.source_evidence)
    receipt=produce(source)
    assert verify_receipt(source,receipt)
    count=negative_tests(source,receipt)
    receipt["negative_controls_rejected"]=count
    args.output.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in receipt.items() if k!="certificates"}))
