#!/usr/bin/env python3
"""Bounded fuzzy and finite n-valued logic exploration for Merlin."""
import argparse, itertools, json, math

def fuzzy_ops(a,b):
    return {
      "godel_and":min(a,b),
      "product_and":a*b,
      "lukasiewicz_and":max(0.0,a+b-1.0),
      "godel_or":max(a,b),
      "probabilistic_or":a+b-a*b,
      "lukasiewicz_or":min(1.0,a+b),
      "godel_implication":1.0 if a<=b else b,
      "lukasiewicz_implication":min(1.0,1.0-a+b),
      "product_implication":1.0 if a<=b else b/a if a>0 else 1.0
    }

def finite_table(n, arity=2, max_rows=4096):
    if not isinstance(n,int) or n<2: raise ValueError("n must be >= 2")
    if not isinstance(arity,int) or arity<1: raise ValueError("arity must be >= 1")
    count=n**arity
    if count>max_rows: raise ValueError(f"table has {count} rows; cap is {max_rows}")
    vals=list(range(n))
    rows=[]
    for args in itertools.product(vals, repeat=arity):
        rows.append({"inputs":list(args),"and_min":min(args),"or_max":max(args),
          "sum_mod_n":sum(args)%n,"product_mod_n":math.prod(args)%n,
          "negation_cycle":(n-1-args[0])})
    return {"truth_values":vals,"arity":arity,"row_count":count,"rows":rows,
      "warning":"These are example connectives, not a uniquely privileged n-valued logic. Select semantics for the problem."}

def rank_candidates(problem):
    candidates=[
      ("fuzzy_membership","graded truth, uncertain evidence, partial membership"),
      ("finite_n_valued","more than two discrete truth states, gaps or conflicts"),
      ("paraconsistent","reasoning with contradictions without trivializing the system"),
      ("intuitionistic","constructive proof and proof-relevant truth"),
      ("modal_temporal","necessity, possibility, time and changing truth"),
      ("probabilistic","uncertainty as probability rather than truth degree"),
      ("rough_approximation","indiscernibility, lower/upper approximations"),
      ("many_sorted_type","different kinds of objects and typed relations"),
      ("algebraic_logic","operators and algebraic structures"),
      ("topological_logic","continuity, neighborhoods and local truth"),
      ("category_semantics","compositional mappings between semantic systems"),
      ("information_logic","information gain, entropy and evidence update"),
      ("game_semantics","strategic interaction and adversarial interpretation"),
      ("quantum_logic","non-classical event structure in quantum theory"),
    ]
    p=(problem or "").lower()
    ranked=[]
    for name,desc in candidates:
        hits=sum(w in p for w in desc.split(", ") if len(w)>3)
        ranked.append({"framework":name,"description":desc,"relevance_score":min(1.0,0.25+0.18*hits),
          "score_status":"heuristic lexical prior; must be re-ranked after problem analysis"})
    ranked.sort(key=lambda x:(-x["relevance_score"],x["framework"]))
    return ranked

def main():
    p=argparse.ArgumentParser(); p.add_argument("--n",type=int,default=3); p.add_argument("--arity",type=int,default=2); p.add_argument("--max-rows",type=int,default=4096); p.add_argument("--problem",default="")
    a=p.parse_args()
    print(json.dumps({"finite_logic":finite_table(a.n,a.arity,a.max_rows),"fuzzy_sample":[{"a":x/4,"b":y/4,"operators":fuzzy_ops(x/4,y/4)} for x,y in itertools.product(range(5),repeat=2)],"candidate_frameworks":rank_candidates(a.problem)},indent=2))
if __name__=="__main__": main()
