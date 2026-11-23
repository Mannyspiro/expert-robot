#!/usr/bin/env python3
"""Exact chemical-reaction-network deficiency/weak-reversibility experiment.

Closed synthetic E+S <-> ES -> E+P. Its deficiency is zero but it is NOT
weakly reversible. A reversible catalysis variant is weakly reversible.
Structural screening does not substitute for a proof or a CACE solver run.
"""
import argparse
from fractions import Fraction as Q
import json

COMPLEXES={
 "free":(1,1,0,0),
 "bound":(0,0,1,0),
 "product":(1,0,0,1),
}
CORE=(("free","bound"),("bound","free"),("bound","product"))
REV=CORE+(("product","bound"),)


def matrix_rank(rows):
    if not rows:return 0
    a=[[Q(x) for x in row] for row in rows]
    rank=0
    for col in range(len(a[0])):
        ix=next((r for r in range(rank,len(a)) if a[r][col]!=0),None)
        if ix is None:continue
        a[rank],a[ix]=a[ix],a[rank]
        pivot=a[rank][col]
        a[rank]=[v/pivot for v in a[rank]]
        for r in range(len(a)):
            if r!=rank:
                f=a[r][col]
                a[r]=[v-f*x for v,x in zip(a[r],a[rank])]
        rank+=1
        if rank==len(a):break
    return rank


def reach(source, edges, reverse=False):
    nxt={source}
    while True:
        grown=nxt|{
           b for a,b in edges if (a if not reverse else b) in nxt
        } if not reverse else nxt|{
           a for a,b in edges if b in nxt
        }
        if grown==nxt:return grown
        nxt=grown


def analyze(edges):
    vertices=set(COMPLEXES)
    assert all(a in vertices and b in vertices and a!=b for a,b in edges)
    adjacency=[(a,b) for a,b in edges]
    seen=set()
    comps=0
    for v in vertices:
        if v not in seen:
            comps+=1
            segment=reach(v,adjacency+[(b,a) for a,b in adjacency])
            seen.update(segment)
    s=matrix_rank([
       [COMPLEXES[b][i]-COMPLEXES[a][i] for i in range(4)]
       for a,b in edges
    ])
    weak=all(a in reach(b,adjacency) for a,b in adjacency)
    n=len(vertices)
    deficiency=n-comps-s
    assert deficiency>=0
    return {"complex_count":n,"linkage_classes":comps,
            "stoichiometric_rank":s,"deficiency":deficiency,
            "weakly_reversible":weak,
            "eligible_for_classical_deficiency_zero_positive_equilibrium":
                deficiency==0 and weak}


def experiment():
    irreversible=analyze(CORE)
    reversible=analyze(REV)
    assert irreversible=={
        "complex_count":3,"linkage_classes":1,"stoichiometric_rank":2,
        "deficiency":0,"weakly_reversible":False,
        "eligible_for_classical_deficiency_zero_positive_equilibrium":False,
    }
    assert reversible["weakly_reversible"] is True
    assert reversible["deficiency"]==0
    missing_reverse=REV[:-1]
    assert analyze(missing_reverse)["weakly_reversible"] is False
    # Disconnected complexes must not silently count as one linkage class.
    disconnected=(("free","bound"),)
    out=analyze(disconnected)
    assert out["linkage_classes"]==2 and out["stoichiometric_rank"]==1
    assert out["deficiency"]==0 and out["weakly_reversible"] is False
    return {
      "experiment":"crnt_deficiency_and_weak_reversibility_v1",
      "rate_assumption":"closed mass-action kinetics, strictly positive rate constants",
      "closed_irreversible":irreversible,"reversible_catalysis_variant":reversible,
      "negative_tests":["delete reverse edge","disconnect reaction component"],
      "zero_deficiency_is_not_sufficient_for_positive_equilibrium":True,
      "external_theorem_applied_only_if_all_hypotheses_verified":True,
      "general_deficiency_zero_theorem_formalized_in_lean":False,
      "cace_runtime_optimized":False,"network_operations":0,
      "production_promotion_authority":False,
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("-o",required=True)
    args=p.parse_args()
    d=experiment()
    with open(args.o,"w",encoding="utf-8") as f:
        json.dump(d,f,indent=2)
        f.write("\n")
    print(json.dumps(d))
