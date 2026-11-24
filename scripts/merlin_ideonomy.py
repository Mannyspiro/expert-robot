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
    semantic=min(1.0,len(words & terms)/max(1,len(terms)))
    testability={"classify":0.82,"construct":0.78,"prove":0.88,"disprove":0.92,"bound":0.86,"optimize":0.82,"predict":0.78,"measure":0.9,"simulate":0.8,"formalize":0.9}.get(item["question"],0.65)
    formal_lenses={"algebraic","logical","combinatorial","categorical","computational"}
    formalizability=0.88 if item["lens"] in formal_lenses else 0.68
    costly={"continuize":0.52,"dualize":0.82,"discretize":0.76,"add_invariant":0.9,"decompose":0.94,"compose":0.84}.get(item["operation"],0.72)
    score=0.35*semantic+0.25*testability+0.22*formalizability+0.18*costly
    return {"priority_score":round(score,3),"semantic_fit":round(semantic,3),
      "testability":testability,"formalizability_prior":formalizability,"feasibility_prior":costly}
def enumerate_space(problem, limit=64):
    rows=[]
    for lens,op,rel,q in itertools.product(DIMENSIONS["object_lenses"],DIMENSIONS["operations"],DIMENSIONS["relations"],DIMENSIONS["question_moves"]):
        item={"lens":lens,"operation":op,"relation":rel,"question":q}
        canonical=json.dumps(item,sort_keys=True)
        item["idea_id"]=hashlib.sha256(canonical.encode()).hexdigest()[:12]
        metrics=score(item,problem)
        item.update(metrics)
        item["score_basis"]="transparent heuristic first-pass; require evidence-based reranking"
        item["novelty_review"]="Novelty is not inferred from this score; compare against the literature and existing knowledge graph."
        item["hypothesis_seed"]=f"Re-express the problem through {lens}; {op} the object; test whether {rel} is present; then {q} the resulting formulation."
        item["disconfirmation"]="Find a counterexample, failed structure-preservation condition, or a result that does not map back to the original problem."
        rows.append(item)
    rows.sort(key=lambda x:(-x["priority_score"],-x["semantic_fit"],x["idea_id"]))
    return {"dimensions":DIMENSIONS,"total_combinations":len(rows),"returned":min(limit,len(rows)),"ideas":rows[:limit],
      "coverage_note":"Bounded ranked sample from a declared combinatorial idea space, not a claim that all possible ideas have been enumerated."}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--problem",required=True); p.add_argument("--limit",type=int,default=64); a=p.parse_args()
    if a.limit<1 or a.limit>512: p.error("--limit must be 1..512")
    print(json.dumps(enumerate_space(a.problem,a.limit),indent=2))
if __name__=="__main__": main()
