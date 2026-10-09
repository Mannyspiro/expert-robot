#!/usr/bin/env python3
"""Exact rational stoichiometric conservation and negative-control tests.

Tests general reaction-network linear invariants, not chemistry calibration.
This is a baseline oracle; actual CACE execution and Lean kernel verification
are independent, later checks. No network access or added authority.
"""
from fractions import Fraction as F
from itertools import product
import argparse
import json


def transpose(matrix):
    return list(zip(*matrix))


def matmul(matrix, vector):
    return [sum((F(a) * F(x) for a,x in zip(row,vector)),F(0))
            for row in matrix]


def rank_and_nullspace(matrix):
    if not matrix:
        raise ValueError("non-empty matrix required")
    nr,nc=len(matrix),len(matrix[0])
    if any(len(row)!=nc for row in matrix):
        raise ValueError("rectangular matrix required")
    a=[[F(x) for x in row] for row in matrix]
    pivots=[]
    rank=0
    for col in range(nc):
        pivot=next((k for k in range(rank,nr) if a[k][col]),None)
        if pivot is None:
            continue
        a[rank],a[pivot]=a[pivot],a[rank]
        scale=a[rank][col]
        a[rank]=[x/scale for x in a[rank]]
        for row in range(nr):
            if row==rank:
                continue
            scale=a[row][col]
            a[row]=[x-scale*y for x,y in zip(a[row],a[rank])]
        pivots.append(col)
        rank+=1
        if rank==nr:
            break
    free=[j for j in range(nc) if j not in pivots]
    nullspace=[]
    for col in free:
        v=[F(0)]*nc
        v[col]=F(1)
        for row,pivot in enumerate(pivots):
            v[pivot]=-a[row][col]
        assert all(x==0 for x in matmul(matrix,v))
        nullspace.append(v)
    return rank,nullspace


def dot(a,b):
    return sum((x*y for x,y in zip(a,b)),F(0))


def update(S,state,flux,dt):
    change=matmul(S,flux)
    return [x+dt*y for x,y in zip(state,change)]


def verify_network(name,columns):
    species,reactions=len(columns[0]),len(columns)
    if any(len(c)!=species for c in columns):
        raise ValueError("incompatible reaction columns")
    S=transpose(columns)
    rank,laws=rank_and_nullspace(columns)
    assert len(laws)==species-rank
    assert all(dot(law,c)==0 for law in laws for c in columns)
    states=[tuple(F(i+j) for i in range(species)) for j in (1,3,5,7)]
    fluxes=[tuple(F(i+j,2) for i in range(reactions)) for j in (-2,0,2,4)]
    steps=[F(0),F(1,32),F(1,4),F(-1,2)]
    count=0
    for state,flux,dt in product(states,fluxes,steps):
        new=update(S,state,flux,dt)
        for law in laws:
            assert dot(law,new)==dot(law,state)
        count+=1
    assert count==64
    return {"name":name,"species":species,"reactions":reactions,
            "rank":rank,"nullity":len(laws),"exact_witness_steps":count,
            "left_nullspace_basis":[[str(x) for x in l] for l in laws]}


def experiment():
    networks=[
      ("enzyme_binding",[(-1,-1,1,0),(1,1,-1,0),(1,0,-1,1)]),
      ("sequential_transfer",[(-1,1,0),(0,-1,1)]),
      ("three_compartment_diffusion",[(-1,1,0),(0,-1,1)]),
      ("reversible_two_species",[(-1,1),(1,-1)]),
      ("branching_with_sink",[(-1,1,0,0),(-1,0,1,0),(0,-1,0,1)]),
    ]
    reports=[verify_network(name,columns) for name,columns in networks]
    assert sum(x["exact_witness_steps"] for x in reports)==320
    # Add an unbalanced leak: no nonzero left-nullspace conservation law
    # survives. The incorrect assumption of mass conservation is falsified.
    leak=[(-1,1,0),(0,-1,1),(-1,0,0)]
    rank,laws=rank_and_nullspace(leak)
    assert rank==3 and laws==[]
    initial=[F(1)]*3
    bad=update(transpose(leak),initial,[F(0),F(0),F(1)],F(1,5))
    assert sum(initial)!=sum(bad)
    return {
      "schema_version":1,
      "experiment":"general_stoichiometric_invariant_oracle_v1",
      "networks":reports,
      "exact_witness_steps":320,
      "conserved_when_left_nullspace_condition_holds":True,
      "leak_counterexample_confirmed":True,
      "arbitrary_flux_does_not_imply_state_nonnegativity":True,
      "real_biomodel_validated":False,
      "cace_runtime_invoked":False,
      "independent_lean_kernel_verification":False,
      "authority_expanded":False,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("-o","--output",required=True)
    args=parser.parse_args()
    report=experiment()
    with open(args.output,"w",encoding="utf-8") as f:
        json.dump(report,f,indent=2)
        f.write("\n")
    print(json.dumps(report))


if __name__=="__main__":
    main()
