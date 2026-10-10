#!/usr/bin/env python3
"""CACE CSR-backed toy enzyme reaction-diffusion: exact independent oracle.

E + S <-> ES -> E + P, three finite-volume cells, no-flux graph diffusion.
The CACE component used is ONLY the CSR encode/decode from cace_studio.modules.fem.
This is NOT verified CACE PDE assembly, certified FEM, or empirical biochemistry.
"""
import argparse
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path
import sys

S=("E","S","ES","P")
STOICH=((-1,-1,1,0),(1,1,-1,0),(1,0,-1,1))
L=((1,-1,0),(-1,2,-1),(0,-1,1))
W=((1,0,1,0),(0,1,1,1))
K=(F(1,32),F(1,16),F(1,8))
DT=F(1,20)
D=F(1,20)

def inner(x,y):
    return sum((a*b for a,b in zip(x,y)), F(0))

def rates_of(x):
    e,s,es,p=x
    return (K[0]*e*s,K[1]*es,K[2]*es)

def exact_step(x,boundary):
    """State is [species][cell]. Boundary amounts/time are explicit."""
    ncell=3
    out=[[F(0) for _ in range(ncell)] for _ in S]
    for c in range(ncell):
        v=rates_of([x[k][c] for k in range(4)])
        for k in range(4):
            reaction=sum((F(STOICH[j][k])*v[j] for j in range(3)),F(0))
            diffusion=-D*sum((F(L[c][q])*x[k][q]
                              for q in range(ncell)),F(0))
            out[k][c]=x[k][c]+DT*(reaction+diffusion+boundary[k][c])
    return out

def total(x,weights):
    return sum((F(weights[k])*v for k in range(4)
                for v in x[k]),F(0))

def numerical_step(x,boundary,recovered,np):
    result=np.array(x,copy=True,dtype=float)
    for c in range(3):
        e,s,es,p=x[:,c]
        v=(float(K[0])*e*s,float(K[1])*es,float(K[2])*es)
        for k in range(4):
            result[k,c]+=float(DT)*sum(STOICH[j][k]*v[j] for j in range(3))
    # Different numerical order/operator path from the independent rational oracle.
    result+=float(DT)*(-float(D)*(x@recovered.T)+boundary)
    return result

def run(root,cace_sha):
    import numpy as np
    if not root.is_dir():raise ValueError("missing read-only CACE checkout")
    if not isinstance(cace_sha,str) or len(cace_sha)!=40 or any(
       a not in "0123456789abcdef" for a in cace_sha):
        raise ValueError("exact CACE commit SHA required")
    sys.path.insert(0,str(root))
    from cace_studio.modules.fem import _csr_from_dense,_dense_from_csr
    dense=np.array(L,dtype=float)
    sparse=_csr_from_dense(dense,tol=0.)
    recovered=np.asarray(_dense_from_csr(sparse),dtype=float)
    if not np.array_equal(dense,recovered):
        raise AssertionError("CACE CSR codec changed the diffusion operator")
    if not np.array_equal(recovered.sum(axis=0),np.zeros(3)):
        raise AssertionError("not a closed-boundary diffusion matrix")
    for row in W:
        if any(inner(row,col)!=0 for col in STOICH):
            raise AssertionError("stoichiometric invariant broken")
    # Synthetic positive concentrations at each mesh cell.
    starts=(
      ((2,1,3),(3,2,1),(0,0,0),(0,0,0)),
      ((1,2,1),(2,3,1),(F(1,2),F(1,4),F(1,8)),(0,1,0)),
      ((3,2,2),(1,2,3),(F(1,4),F(1,2),F(1,4)),(1,0,2)),
    )
    boundary=tuple(tuple(
       F(1,100) if (k==1 and c==0) else F(0)
       for c in range(3)) for k in range(4))
    trials=[]
    for ix,start in enumerate(starts):
        exact=[[F(v) for v in row] for row in start]
        numeric=np.array([[float(v) for v in row] for row in start])
        sources=np.array([[float(v) for v in row] for row in boundary])
        last=[total(exact,row) for row in W]
        max_error=0.
        for step in range(8):
            exact=exact_step(exact,boundary)
            numeric=numerical_step(numeric,sources,recovered,np)
            for j,row in enumerate(W):
                expected=DT*sum((F(row[k])*boundary[k][c]
                                  for k in range(4) for c in range(3)),F(0))
                observed=total(exact,row)-last[j]
                if observed!=expected:
                    raise AssertionError("rational reaction-diffusion balance failed")
                last[j]=total(exact,row)
            if min(v for row in exact for v in row)<0:
                raise AssertionError("synthetic exact concentrations negative")
            error=max(abs(float(exact[k][c])-numeric[k,c])
                      for k in range(4) for c in range(3))
            max_error=max(max_error,error)
            if not np.isfinite(error) or error>2e-12:
                raise AssertionError("CACE CSR numerical path disagrees with oracle")
        trials.append({"case_id":"case-"+str(ix),
              "steps":8,"exact_balance_residual":"0",
              "numeric_difference_max":max_error,
              "oracle_and_cace_csr_agree":True})
    # Mutation: leaking a boundary cell violates the weighted amount balance.
    wrong=np.array(recovered,copy=True)
    wrong[0,0]+=1.
    if not any(abs(v)>0 for v in wrong.sum(axis=0)):
        raise AssertionError("diffusion leakage mutation undetected")
    # Mutation: consume ES without adding P; breaks substrate-moiety balance.
    bad_catalysis=tuple(STOICH[2][k] if k!=3 else 0 for k in range(4))
    if inner(W[1],bad_catalysis)==0:
        raise AssertionError("missing-product reaction mutation undetected")
    return {
      "schema_version":1,"experiment":"cace-csr-reaction-diffusion-3-cell-v1",
      "cace_repository":"morganaspim/Cace-app",
      "cace_commit_sha":cace_sha,
      "cace_component":"cace_studio.modules.fem CSR encode/decode",
      "oracle":"independent exact Fraction Euler",
      "reaction_network":"E+S<->ES->E+P",
      "invariants":["total_enzyme","substrate_moiety"],
      "boundary_substrate_amount_per_time":"1/100",
      "closed_diffusion_columns_zero":True,
      "matched_cases":trials,"total_steps":24,
      "wrong_boundary_mutant_detected":True,
      "lost_product_mutant_detected":True,
      "actual_cace_csr_codec_executed":True,
      "actual_cace_pde_solver_executed":False,
      "formal_assumption_mapping_qualified":False,
      "biological_data_validated":False,
      "runtime_speedup_measured":False,
      "promotion_authorized":False,
      "authority_expanded":False,
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cace-repo",type=Path,required=True)
    p.add_argument("--cace-sha",required=True)
    p.add_argument("-o",required=True)
    a=p.parse_args()
    result=run(a.cace_repo.resolve(),a.cace_sha)
    Path(a.o).write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"matched_cases":len(result["matched_cases"]),
                      "total_steps":result["total_steps"],
                      "exact_balances_hold":True,
                      "pde_solver_executed":False,
                      "promotion_authorized":False}))
