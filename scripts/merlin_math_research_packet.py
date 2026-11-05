#!/usr/bin/env python3
"""Assemble math research packet: representations, logic lenses, ideonomy and Lean obligations."""
import argparse, importlib.util, json, sys
from pathlib import Path
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/"scripts"/path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def build(problem,limit=48,n=3,arity=2):
 fuzzy=load("fuzzy","merlin_logic_lenses.py")
 ideas=load("ideas","merlin_ideonomy.py")
 reframe=load("reframe","merlin_problem_reframing.py")
 return {
  "schema_version":1,"problem":problem,
  "mandatory_methods":["decompose","multi_representation","fuzzy_logic_lenses","finite_n_valued_logic_lenses","ideonomy_enumeration","hypothesis_generation","Lean_formalization"],
  "problem_representation":reframe.template("math-research"),
  "logic_lenses":{"fuzzy_operators":["godel_and","product_and","lukasiewicz_and","godel_or","probabilistic_or","lukasiewicz_or","godel_implication","lukasiewicz_implication","product_implication"],
   "finite_logic":fuzzy.finite_table(n,arity),"ranked_candidates":fuzzy.rank_candidates(problem),
   "selection_rule":"Rank by semantic fit, assumptions, expressive adequacy, compositionality, decidability/complexity, proof support and empirical calibration; do not conflate fuzzy degree with probability."},
  "ideonomy":ideas.enumerate_space(problem,limit),
  "lean_bridge":{"status":"candidate_generation_only","obligations":[
    "Define the underlying object and each representation in Lean.",
    "State maps between representations with explicit domains and codomains.",
    "Prove preservation of the invariants needed by the target theorem.",
    "State hypotheses and boundary conditions; prove equivalence or embedding lemmas.",
    "Formalize each candidate hypothesis as a theorem or conjecture with exact assumptions.",
    "Run Lean and record toolchain, mathlib revision, imports, axioms and build result.",
    "Reject any proof transfer that relies only on analogy or heuristic similarity."],
   "axiom_policy":"No new axioms, sorry, admit or unsafe escape hatches; report dependencies and keep unverified statements as conjectures."},
  "engineering_plan":plan,
  "resource_policy":{"max_ideas":limit,"max_truth_table_rows":4096,"expand_on_demand":True},
  "promotion":"No generated idea or candidate theorem becomes canonical or trusted without independent evidence and verification."
 }
def main():
 p=argparse.ArgumentParser(); p.add_argument("--problem",required=True); p.add_argument("--limit",type=int,default=48); p.add_argument("--n",type=int,default=3); p.add_argument("--arity",type=int,default=2); p.add_argument("--out",type=Path); a=p.parse_args()
 if not 1<=a.limit<=512: p.error("limit must be 1..512")
 result=build(a.problem,a.limit,a.n,a.arity)
 validator=load("validator","merlin_engineering_plan.py")
 errors=validator.validate(result["engineering_plan"])
 if errors: raise SystemExit("generated plan invalid: "+"; ".join(errors))
 rendered=json.dumps(result,indent=2)
 if a.out: a.out.write_text(json.dumps(result["engineering_plan"],indent=2)+"\\n",encoding="utf-8")
 print(rendered)
if __name__=="__main__": main()
