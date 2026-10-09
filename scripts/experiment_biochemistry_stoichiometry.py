#!/usr/bin/env python3
"""Offline exact-rational toy enzyme kinetics and conservation-law experiment.

E + S <-> ES -> E + P. Synthetic constants, no empirical parameter claims.
Nonexperimental, no live CACE backend, and no production optimization.
"""
import argparse
from fractions import Fraction as Q
from itertools import product
import json

SPECIES=("E","S","ES","P")
REACTIONS={"binding":(-1,-1,1,0),
           "unbinding":(1,1,-1,0),
           "catalysis":(1,0,-1,1)}
INVARIANTS={"total_enzyme":(1,0,1,0),"substrate_moiety":(0,1,1,1)}


def dot(a,b):
    return sum(x*y for x,y in zip(a,b))


def rank(columns):
    a=[[Q(c[i]) for c in columns] for i in range(len(SPECIES))]
    row=0
    for j in range(len(columns)):
        pivot=next((i for i in range(row,len(a)) if a[i][j]),None)
        if pivot is None:
            continue
        a[pivot],a[row]=a[row],a[pivot]
        divisor=a[row][j]
        a[row]=[v/divisor for v in a[row]]
        for i in range(len(a)):
            if i!=row:
                f=a[i][j]
                a[i]=[v-f*x for v,x in zip(a[i],a[row])]
        row+=1
        if row==len(a):
            break
    return row


def step(state,k,dt):
    e,s,es,p=state
    forward,reverse,product=k[0]*e*s,k[1]*es,k[2]*es
    rates=(forward,reverse,product)
    regular=tuple(state[i]+dt*sum(REACTIONS[n][i]*v for n,v in zip(REACTIONS,rates))
                  for i in range(4))
    net=forward-reverse
    combined=tuple(state[i]+dt*(REACTIONS["binding"][i]*net+
                                  REACTIONS["catalysis"][i]*product)
                   for i in range(4))
    assert regular==combined, "optimized and original dynamics disagree"
    return regular


def experiment():
    columns=list(REACTIONS.values())
    assert rank(columns)==2
    assert all(dot(v,c)==0 for v in INVARIANTS.values() for c in columns)
    assert any(all(dot(v,c)==0 for c in columns)
               for v in product((-1,0,1),repeat=4) if any(v))
    mutant=(-1,0,1,0)  # omit consumed S from binding
    assert dot(INVARIANTS["substrate_moiety"],mutant)!=0
    assert dot(INVARIANTS["total_enzyme"],mutant)==0
    cases=[
        ((Q(2),Q(3),Q(0),Q(0)),(Q(1),Q(1,2),Q(3,4)),Q(1,128),8),
        ((Q(1),Q(2),Q(1,2),Q(0)),(Q(1,3),Q(1,5),Q(2,3)),Q(1,128),8),
        ((Q(3,2),Q(1),Q(1,4),Q(0)),(Q(1,2),Q(1,4),Q(1,2)),Q(1,256),8),
    ]
    holdouts=[]
    for initial,k,dt,count in cases:
        state=initial
        conserved={name:dot(v,state) for name,v in INVARIANTS.items()}
        for _ in range(count):
            state=step(state,k,dt)
            assert all(v>=0 for v in state), "negative concentrations"
            assert all(dot(v,state)==conserved[name]
                       for name,v in INVARIANTS.items()), "conservation violation"
        holdouts.append({"steps":count,"conservation_residual_exact":0,
                         "negative_concentrations":0,"optimized_matches_baseline":True})
    return {
        "schema_version":1, "experiment":"biochemistry_exact_enzyme_conservation_v1",
        "species":SPECIES,"stoichiometry":REACTIONS,
        "rank":rank(columns),"left_nullity":len(SPECIES)-rank(columns),
        "conservation_laws":INVARIANTS,"holdouts":holdouts,
        "exact_euler_steps":sum(x["steps"] for x in holdouts),
        "mutation_detected":True,
        "candidate_rule":"combine forward and reverse binding reaction columns",
        "candidate_columns_before":3,"candidate_columns_after":2,
        "empirical_biochemical_parameters":False,
        "quantified_runtime_speedup":False,"direct_cace_backend_executed":False,
        "biological_prediction_verified":False,"network_operations":0,
        "promotion_or_authority_expanded":False,
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("-o",required=True)
    args=p.parse_args()
    result=experiment()
    with open(args.o,"w",encoding="utf-8") as f:
        json.dump(result,f,indent=2)
        f.write("\n")
    print(json.dumps(result))
