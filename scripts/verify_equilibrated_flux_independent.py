#!/usr/bin/env python3
"""Independent midpoint-quadrature verifier of source-bound 1D flux receipts.

Do not import the certificate producer; recompute using a different exact
per-element identity:
 ∫_a^b (sigma(x)-v'(x))² dx
 = h * (sigma(midpoint)-v')² + (sigma_slope)²*h³/12.

The original producer integrates expanded endpoint polynomials instead.
Only a separately pinned CACE source file supplies the vertex values.
"""
import argparse,copy,hashlib,json,math
from fractions import Fraction as Q
from pathlib import Path

PIN="2ceee478a30e556685e81589f918764d7b4dd4d2830aa5357493a0a64cfd027f"
CACE_SHA="66b22a71ff52b3110269f5994a5fd0716a2054c1"
FEM_SHA="73742096c73386f83727841ac7eb6efacfebef11ce8ab24b3f4a03bf682a74c1"

def parse(s):
    if type(s) is not str or len(s)>400 or not s or any(c not in "0123456789-/" for c in s) or s.count("/")>1:
        raise ValueError("unsafe/unbounded/nonrational receipt coefficient")
    q=Q(s)
    if str(q)!=s or max(q.numerator.bit_length(),q.denominator.bit_length())>2048:
        raise ValueError("noncanonical or excessive exact rational")
    return q

def num(x):
    if type(x) not in (int,float) or not math.isfinite(float(x)):
        raise ValueError("invalid binary64 field")
    return Q.from_float(float(x))

def families(n):
    return [
      ("constant",[Q(1)]*n),
      ("alternating",[Q(1) if i%2==0 else Q(2) for i in range(n)]),
      ("signed",[Q(1) if i%2==0 else Q(-1) for i in range(n)]),
      ("graded",[Q(i+1,n) for i in range(n)])]

def majorant2(xs,ys,ff,left,slopes):
    n=len(xs)-1
    if len(ff)!=n or len(left)!=n or len(slopes)!=n or len(ys)!=n+1:
        raise ValueError("wrong mesh or flux shapes")
    if xs[0]!=0 or xs[-1]!=1 or ys[0]!=0 or ys[-1]!=0 or any(
        xs[i+1]<=xs[i] for i in range(n)):
        raise ValueError("not a valid Dirichlet P1 mesh")
    summand=Q(0)
    for i in range(n):
        h=xs[i+1]-xs[i]
        if slopes[i]!=-ff[i]:
            raise ValueError("not equilibrated with the forcing")
        if i and left[i]!=left[i-1]+slopes[i-1]*(xs[i]-xs[i-1]):
            raise ValueError("normal flux discontinuity")
        midpoint_flux=left[i]+slopes[i]*h/2
        gradient=(ys[i+1]-ys[i])/h
        summand+=h*(midpoint_flux-gradient)**2 + slopes[i]**2*h**3/12
    return summand

def verify(source_path,receipt):
    raw=source_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:
        raise ValueError("untrusted external CACE evidence")
    data=json.loads(raw.decode("utf-8"))
    if data.get("cace_sha")!=CACE_SHA or data.get("fem_source_sha256")!=FEM_SHA:
        raise ValueError("underlying CACE source revision not pinned")
    scope={"schema":"cace-equilibrated-flux-1d-v1",
           "externally_pinned_cace_evidence_sha256":PIN,
           "cace_source_commit":CACE_SHA,
           "validated_exact_cases":160,"forcing_profiles":4,
           "real_cace_meshes":8,"forcing_profiles_cace_simulated":1,
           "qualifying_assumptions":"1D Dirichlet Poisson, piecewise-constant f, conforming P1 v, continuous equilibrated piecewise-affine sigma",
           "independent_continuous_hypercircle_proof_in_lean":False,
           "full_general_pde_bound_qualified":False,
           "remote_cace_modified":False,
           "authority_expanded":False}
    if not isinstance(receipt,dict) or set(receipt)!=set(scope)|{"certificates","negative_controls_rejected"}:
        raise ValueError("unrecognized or incomplete receipt fields")
    for k,v in scope.items():
        if type(receipt[k]) is not type(v) or receipt[k]!=v:
            raise ValueError("unqualified metadata "+k)
    if type(receipt["negative_controls_rejected"]) is not int or receipt["negative_controls_rejected"]!=18:
        raise ValueError("unqualified falsification tests")
    entries=receipt["certificates"]
    if not isinstance(entries,list) or len(entries)!=160 or len(data.get("meshes",[]))!=8:
        raise ValueError("missing/duplicate certificates")
    count=0;max_slack=0.
    for row in data["meshes"]:
        xs=[num(x) for x in row["cace_mesh_vertices"]]
        ys=[num(y) for y in row["cace_solution_values"]]
        for name,ff in families(len(xs)-1):
            prefix=Q(0);weighted=Q(0)
            for i,f in enumerate(ff):
                h=xs[i+1]-xs[i]
                weighted+=prefix*h+f*h*h/2
                prefix+=f*h
            cstar=weighted
            # Reference exact solution derivative for this 1D Dirichlet
            # forcing is cstar-integral_0^x(f).
            true_left=[];true_slope=[];prefix=Q(0)
            for i,f in enumerate(ff):
                true_left.append(cstar-prefix)
                true_slope.append(-f)
                prefix+=f*(xs[i+1]-xs[i])
            ref_error2=majorant2(xs,ys,ff,true_left,true_slope)
            for C in (Q(0),Q(1,4),Q(1,2),cstar,cstar+Q(1,3)):
                item=entries[count];count+=1
                expected_fields={"mesh","forcing","flux_constant","flux_left","flux_slope",
                    "majorant_squared","independent_energy_error_squared",
                    "hypercircle_gap_squared","outward_upper_float"}
                if not isinstance(item,dict) or set(item)!=expected_fields:
                    raise ValueError("unsupported flux receipt schema")
                if item["mesh"]!=row["mesh"] or item["forcing"]!=name or parse(item["flux_constant"])!=C:
                    raise ValueError("wrong mesh/forcing/constant")
                if not isinstance(item["flux_left"],list) or not isinstance(item["flux_slope"],list):
                    raise ValueError("missing flux witnesses")
                left=[parse(z) for z in item["flux_left"]]
                slope=[parse(z) for z in item["flux_slope"]]
                if len(left)!=len(ff) or left[0]!=C:
                    raise ValueError("source-bound flux does not start at promised constant")
                M=majorant2(xs,ys,ff,left,slope)
                if parse(item["majorant_squared"])!=M:
                    raise ValueError("incorrect squared majorant")
                if parse(item["independent_energy_error_squared"])!=ref_error2:
                    raise ValueError("incorrect reference energy error")
                if parse(item["hypercircle_gap_squared"])!=(C-cstar)**2 or M-ref_error2!=(C-cstar)**2:
                    raise ValueError("false exact hypercircle gap")
                top=num(item["outward_upper_float"])
                if top<0 or top**2<M:
                    raise ValueError("upper bound rounded below rigorous exact value")
                # This is a narrow rational-to-binary64 enclosure, not
                # a vacuous bound that could pass with a huge upper number.
                scale=10**14
                k=math.isqrt((M.numerator*scale*scale)//M.denominator)
                high=Q(k+1,scale)
                if top<high or top-high>Q(1,10**10):
                    raise ValueError("bound too loose or does not enclose sqrt")
                max_slack=max(max_slack,float(top-high))
    return {"schema":"cace-equilibrated-flux-independent-replay-v1",
            "source_sha256":PIN,"exact_certificate_rows_replayed":count,
            "all_fluxes_continuous_and_divergence_correct":True,
            "all_rational_majorants_independently_matched":True,
            "maximum_float_enclosure_slack":max_slack,
            "general_pde_bound_qualified":False,"lean_continuum_proof":False,
            "authority_expanded":False}

def mutation_replay(source,valid):
    mutations=[
      ("wrong_slope",lambda d:d["certificates"][0]["flux_slope"].__setitem__(0,"0")),
      ("jump",lambda d:d["certificates"][20]["flux_left"].__setitem__(1,"2")),
      ("wrong_majorant",lambda d:d["certificates"][11].update(majorant_squared="0")),
      ("tiny_upper",lambda d:d["certificates"][7].update(outward_upper_float=0.)),
      ("vacuous_upper",lambda d:d["certificates"][7].update(outward_upper_float=1000.)),
      ("nan",lambda d:d["certificates"][9].update(outward_upper_float=float("nan"))),
      ("wrong_source",lambda d:d.update(externally_pinned_cace_evidence_sha256="0"*64)),
      ("fake_lean",lambda d:d.update(independent_continuous_hypercircle_proof_in_lean=True)),
      ("fake_general",lambda d:d.update(full_general_pde_bound_qualified=True)),
      ("fake_more_cace",lambda d:d.update(forcing_profiles_cace_simulated=4)),
      ("wrong_gap",lambda d:d["certificates"][4].update(hypercircle_gap_squared="-1")),
      ("fake_true_error",lambda d:d["certificates"][0].update(independent_energy_error_squared="0")),
      ("missing",lambda d:d["certificates"].pop()),
      ("wrong_methods",lambda d:d.update(qualifying_assumptions="unrestricted")),
      ("authority",lambda d:d.update(authority_expanded=True))
    ]
    rejected=0
    for label,fn in mutations:
        broken=copy.deepcopy(valid);fn(broken)
        try:verify(source,broken)
        except (ValueError,TypeError,KeyError,OverflowError):
            rejected+=1;continue
        raise AssertionError("independent verifier accepted "+label)
    return rejected

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source-evidence",type=Path,required=True)
    p.add_argument("--certificate",type=Path,required=True)
    args=p.parse_args()
    receipt=json.loads(args.certificate.read_text(encoding="utf-8"),
        parse_constant=lambda v:(_ for _ in ()).throw(ValueError("nonfinite JSON")))
    out=verify(args.source_evidence,receipt)
    out["independent_mutations_rejected"]=mutation_replay(args.source_evidence,receipt)
    print(json.dumps(out))
