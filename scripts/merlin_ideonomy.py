#!/usr/bin/env python3
"""Generate a bounded, ranked ideonomy candidate space with falsifiable hypotheses."""
import argparse, itertools, json, hashlib

DIMENSIONS={
 "object_lenses":["algebraic","geometric","topological","categorical","combinatorial","logical","dynamical","probabilistic","information_theoretic","computational","physical"],
 "operations":["decompose","compose","dualize","generalize","specialize","embed","quotient","discretize","continuize","transform_frame","relax_constraints","add_invariant"],
 "relations":["equivalence","isomorphism","duality","adjunction","symmetry","conservation","causality","approximation","correspondence","obstruction"],
 "question_moves":["classify","construct","prove","disprove","bound","optimize","predict","measure","simulate","formalize"]
}
def score(item, problem):
    words=set((problem or "").lower().replace(","," ").split())
    terms=set((item["lens"]+" "+item["operation"]+" "+item["relation"]+" "+item["question"]).replace("_"," ").split())
    overlap=len(words & terms)
    novelty=len(set(item.values())-{"classify","construct","prove","disprove","bound","optimize","predict","measure","simulate","formalize"})
    return round(min(1.0,0.35+0.12*overlap+0.025*novelty),3)
def enumerate_space(problem, limit=64):
    rows=[]
    for lens,op,rel,q in itertools.product(DIMENSIONS["object_lenses"],DIMENSIONS["operations"],DIMENSIONS["relations"],DIMENSIONS["question_moves"]):
        item={"lens":lens,"operation":op,"relation":rel,"question":q}
        canonical=json.dumps(item,sort_keys=True)
        item["idea_id"]=hashlib.sha256(canonical.encode()).hexdigest()[:12]
        item["priority_score"]=score(item,problem)
        item["score_basis"]="heuristic first-pass; require evidence-based reranking"
        item["hypothesis_seed"]=f"Re-express the problem through {lens}; {op} the object; test whether {rel} is present; then {q} the resulting formulation."
        item["disconfirmation"]="Find a counterexample, failed structure-preservation condition, or a result that does not map back to the original problem."
        rows.append(item)
    rows.sort(key=lambda x:(-x["priority_score"],x["idea_id"]))
    return {"dimensions":DIMENSIONS,"total_combinations":len(rows),"returned":min(limit,len(rows)),"ideas":rows[:limit],
      "coverage_note":"Bounded ranked sample from a declared combinatorial idea space, not a claim that all possible ideas have been enumerated."}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--problem",required=True); p.add_argument("--limit",type=int,default=64); a=p.parse_args()
    if a.limit<1 or a.limit>512: p.error("--limit must be 1..512")
    print(json.dumps(enumerate_space(a.problem,a.limit),indent=2))
if __name__=="__main__": main()
