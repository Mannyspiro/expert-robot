#!/usr/bin/env python3
"""Exact-rational counterexample search for an irreversible toy enzyme system.

Rate model:
  complex' = kon*E*S - koff*ES - kcat*ES
  product' = kcat*ES

A steady state needs BOTH derivatives zero. This enumerator independently
tests the formal claim and generates failures if positivity is weakened.
No real kinetic measurements, wet lab, or CACE runtime involved.
"""
import argparse
from fractions import Fraction as Q
from itertools import product
import json


def derivatives(kon,koff,kcat,e,s,es):
    return (kon*e*s-koff*es-kcat*es,kcat*es)


def solve():
    positive=(Q(1,2),Q(1),Q(3,2),Q(2))
    all_nonnegative=(Q(0),)+positive
    tested=0
    counterexamples=[]
    for kon,koff,kcat,e,s,es in product(positive,all_nonnegative,
                                       positive,positive,positive,
                                       all_nonnegative):
        tested+=1
        if derivatives(kon,koff,kcat,e,s,es)==(0,0):
            counterexamples.append((kon,koff,kcat,e,s,es))
    assert not counterexamples
    cases={
       "zero_binding_rate":(Q(0),Q(1),Q(1),Q(1),Q(1),Q(0)),
       "zero_catalytic_rate":(Q(1),Q(1),Q(0),Q(1),Q(1),Q(1)),
       "zero_free_enzyme":(Q(1),Q(1),Q(1),Q(0),Q(1),Q(0)),
       "zero_substrate":(Q(1),Q(1),Q(1),Q(1),Q(0),Q(0)),
    }
    assert all(derivatives(*values)==(0,0) for values in cases.values())
    bogus_interior=(Q(1),Q(1),Q(1),Q(1),Q(1),Q(1,2))
    assert derivatives(*bogus_interior)[0]==0
    assert derivatives(*bogus_interior)[1]>0
    # If the steady-state checker drops the product equation, it accepts
    # a false interior equilibrium; a concrete counterexample is retained.
    return {
      "schema_version":1,"experiment":"closed-enzyme-equilibrium-obstruction-v1",
      "rate_equations":{"complex":"kon*E*S-koff*ES-kcat*ES","product":"kcat*ES"},
      "positive_parameter_grid_evaluations":tested,
      "positive_parameter_grid_equilibria":len(counterexamples),
      "necessary_hypotheses_boundary_witnesses":{
          k:[str(v) for v in values] for k,values in cases.items()},
      "dropped_product_rate_counterexample":[str(v) for v in bogus_interior],
      "dropped_equation_mutant_detected":True,
      "symbolic_lean_proof_candidate":"MathAI.Bio.no_positive_enzyme_substrate_steady_state",
      "mathematical_generalization_proved_by_this_script":False,
      "empirical_biochemistry_claimed":False,
      "cace_runtime_executed":False,
      "network_operations":0,
      "authority_expanded":False,
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("-o",required=True)
    args=p.parse_args()
    d=solve()
    with open(args.o,"w",encoding="utf-8") as f:
        json.dump(d,f,indent=2)
        f.write("\n")
    print(json.dumps({k:v for k,v in d.items()
                      if k!="necessary_hypotheses_boundary_witnesses"}))
