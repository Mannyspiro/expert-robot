#!/usr/bin/env python3
"""Offline exact-rational stoichiometric invariants; not an empirical CACE run."""
import argparse
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

def dot(a,b):
    if len(a)!=len(b): raise ValueError("dimension mismatch")
    return sum((x*y for x,y in zip(a,b)),Q(0))

def left_nullspace(columns,species):
    """Exact RREF of stoichiometry transpose: ker(S^T)."""
    if species<1 or not columns or any(len(c)!=species for c in columns):
        raise ValueError("nonempty rectangular network required")
    rows=[[Q(x) for x in c] for c in columns]
    pivots=[]; rank=0
    for j in range(species):
        pivot=next((i for i in range(rank,len(rows)) if rows[i][j]),None)
        if pivot is None: continue
        rows[rank],rows[pivot]=rows[pivot],rows[rank]
        denominator=rows[rank][j]
        rows[rank]=[v/denominator for v in rows[rank]]
        for i in range(len(rows)):
            if i!=rank:
                factor=rows[i][j]
                rows[i]=[v-factor*w for v,w in zip(rows[i],rows[rank])]
        pivots.append(j);rank+=1
        if rank==len(rows): break
    basis=[]
    for free in range(species):
        if free in pivots: continue
        w=[Q(0)]*species
        w[free]=Q(1)
        for k,pivot in enumerate(pivots):w[pivot]=-rows[k][free]
        assert all(dot(w,col)==0 for col in columns)
        basis.append(w)
    assert len(basis)==species-rank
    return basis,rank

def update(state,cols,flux,dt,boundary):
    if len(cols)!=len(flux) or len(state)!=len(boundary) or any(
       len(col)!=len(state) for col in cols):
        raise ValueError("invalid reaction or source shape")
    return [state[i]+dt*(sum((col[i]*f for col,f in zip(cols,flux)),Q(0))
                              +boundary[i]) for i in range(len(state))]

def witness(columns,state,flux,dt,boundary):
    cols=[[Q(z) for z in col] for col in columns]
    state=list(map(Q,state)); flux=list(map(Q,flux))
    boundary=list(map(Q,boundary));dt=Q(dt)
    basis,rank=left_nullspace(cols,len(state))
    after=update(state,cols,flux,dt,boundary)
    checks=[]
    for w in basis:
        observed=dot(w,after)-dot(w,state)
        predicted=dt*dot(w,boundary)
        assert observed==predicted
        checks.append({"weight":[str(q) for q in w],
                       "observed_change":str(observed),
                       "expected_boundary_change":str(predicted),
                       "exact_residual":"0"})
    return {"species":len(state),"reactions":len(cols),
            "rank":rank,"left_nullity":len(basis),"invariants":checks}

def require_amount_units(units):
    if not units or any(unit!="amount_mol" for unit in units):
        raise ValueError("amount/concentration conversion needs explicit units and compartment volume")

def experiment():
    cases=[
      ("enzyme_closed",[[-1,-1,1,0],[1,1,-1,0],[1,0,-1,1]],
       [2,3,0,0],[Q(1,2),Q(1,4),Q(1,8)],Q(1,16),[0,0,0,0]),
      ("chain_closed",[[-1,1,0],[0,-1,1]],
       [3,1,0],[Q(1,4),Q(1,8)],Q(1,4),[0,0,0]),
      ("parallel_closed",[[-1,1,0,0],[0,0,-1,1]],
       [1,2,3,4],[Q(1,4),Q(1,6)],Q(1,2),[0,0,0,0]),
      ("open_boundary",[[-1,1,0],[0,-1,1]],
       [2,1,0],[Q(1,5),Q(1,10)],Q(1,2),[Q(1,3),0,Q(-1,7)])
    ]
    outputs=[]
    for name,cols,state,flux,dt,boundary in cases:
        require_amount_units(["amount_mol"]*len(state))
        result=witness(cols,state,flux,dt,boundary);result["case"]=name
        outputs.append(result)
    # Mutation: lost first reactant breaks closed-network total amount balance.
    bad=[[0,1,0],[0,-1,1]]
    mass_defect=sum(update(list(map(Q,[3,1,0])),
                           [[Q(q) for q in c] for c in bad],
                           [Q(1,3),Q(1,5)],Q(1),[Q(0)]*3))-4
    assert mass_defect==Q(1,3)
    assert any(v["expected_boundary_change"]!="0"
               for v in outputs[-1]["invariants"])
    try:require_amount_units(["amount_mol","concentration_mol_per_L"])
    except ValueError: pass
    else:raise AssertionError("unit mismatch not detected")
    return {
      "schema_version":1,"experiment":"general_exact_reaction_conservation_v1",
      "cases":outputs,"left_nullspace_algorithm":"exact-fraction-rref",
      "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      "missing_reactant_mass_defect":str(mass_defect),
      "missing_reactant_mutant_detected":True,
      "open_boundary_accounted":True,"mixed_unit_mutant_rejected":True,
      "formal_lean_network_theorem_pending_ci":True,
      "cace_backend_executed":False,"empirical_kinetics_validated":False,
      "runtime_speedup_measured":False,"promotion_authorized":False,
      "authority_expanded":False
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("-o",required=True)
    args=ap.parse_args();result=experiment()
    Path(args.o).write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"cases":len(result["cases"]),
         "nullities":[case["left_nullity"] for case in result["cases"]],
         "formal_verified":False}))
