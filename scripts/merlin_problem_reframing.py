#!/usr/bin/env python3
"""Build and validate decomposition and multi-representation plans for Merlin problems."""
import argparse, json
from pathlib import Path

EXACTNESS={"exact_isomorphism","mathematical_equivalence","embedding","structural_analogy","heuristic_reframing"}
SYSTEMS={"symbolic_equations","geometry","linear_algebra","graph_network","combinatorics","logic_type_theory","category_functor","dynamical_system","probability_statistics","optimization","topology","information_theory","algorithmic","physical_model","custom"}

def validate(spec):
    errors=[]
    if not isinstance(spec,dict): return ["spec must be a JSON object"]
    for k in ("problem_id","original_problem","decomposition","representations","reframe_triggers","selection_criteria"):
        if k not in spec: errors.append("missing "+k)
    dec=spec.get("decomposition",{})
    if not isinstance(dec.get("needed"),bool): errors.append("decomposition.needed must be boolean")
    if dec.get("needed") is False and not dec.get("not_needed_rationale"):
        errors.append("decomposition.not_needed_rationale required when decomposition is not needed")
    parts=dec.get("subproblems",[])
    if dec.get("needed") and (not isinstance(parts,list) or len(parts)<2):
        errors.append("a decomposed problem needs at least two subproblems")
    ids=[x.get("id") for x in parts if isinstance(x,dict)]
    if len(ids)!=len(parts) or len(set(ids))!=len(ids) or any(not x for x in ids):
        errors.append("subproblems need unique non-empty ids")
    part_ids=set(ids)
    for p in parts:
        if not isinstance(p,dict): continue
        for k in ("objective","acceptance","interface"):
            if not p.get(k): errors.append("subproblem "+str(p.get("id"))+" missing "+k)
        for dep in p.get("depends_on",[]):
            if dep not in part_ids: errors.append("unknown dependency "+str(dep)+" in "+str(p.get("id")))
    reps=spec.get("representations",[])
    if not isinstance(reps,list) or not reps: errors.append("at least one representation is required")
    elif len(reps)<2 and spec.get("multiple_representations_useful") is not False:
        errors.append("provide at least two representations or explicitly state multiple representations are not useful")
    rep_ids=[r.get("id") for r in reps if isinstance(r,dict)]
    if len(rep_ids)!=len(reps) or len(set(rep_ids))!=len(rep_ids) or any(not x for x in rep_ids):
        errors.append("representations need unique non-empty ids")
    for r in reps:
        if not isinstance(r,dict): continue
        for k in ("name","system","encoding","relationship","mapping","preserved_invariants","lost_information","validity_conditions","validation_method"):
            if k not in r: errors.append("representation "+str(r.get("id"))+" missing "+k)
        if r.get("relationship") not in EXACTNESS: errors.append("representation "+str(r.get("id"))+" has invalid relationship class")
        if r.get("system") not in SYSTEMS: errors.append("representation "+str(r.get("id"))+" has unknown system; use custom with explanation")
        if r.get("relationship") in ("structural_analogy","heuristic_reframing") and not r.get("non_transferable_properties"):
            errors.append("analogy/heuristic "+str(r.get("id"))+" must state non-transferable properties")
    if not spec.get("reframe_triggers"): errors.append("reframe_triggers must be explicit")
    if not spec.get("selection_criteria"): errors.append("selection_criteria must be explicit")
    return errors

def template(problem_id):
    return {
      "schema_version":1,"problem_id":problem_id,"original_problem":"",
      "decomposition":{"needed":True,"not_needed_rationale":"","subproblems":[
        {"id":"P1","objective":"","depends_on":[],"interface":"","acceptance":""},
        {"id":"P2","objective":"","depends_on":["P1"],"interface":"","acceptance":""}]},
      "multiple_representations_useful":True,
      "representations":[
        {"id":"R1","name":"Native formulation","system":"symbolic_equations","encoding":"","relationship":"exact_isomorphism","mapping":"","preserved_invariants":[],"lost_information":[],"validity_conditions":[],"non_transferable_properties":[],"validation_method":""},
        {"id":"R2","name":"Structural alternative","system":"graph_network","encoding":"","relationship":"structural_analogy","mapping":"","preserved_invariants":[],"lost_information":[],"validity_conditions":[],"non_transferable_properties":["List what does not transfer."],"validation_method":""}],
      "reframe_triggers":["proof/search stagnates","contradiction or hidden assumption found","representation is too large or opaque","a new invariant or simpler model appears","independent formulation disagrees"],
      "selection_criteria":["preservation of target invariants","proof or computation tractability","information loss","assumption burden","independent verifiability","resource cost"],
      "transfer_rules":{"proof_transfer":"Only transfer a theorem through a proved map preserving all required structure and hypotheses.","analogy":"Use to generate conjectures and search directions only; never treat as proof.","round_trip":"Where possible map results back and verify in the original formulation."},
      "uncertainty":"Mark each correspondence as proved, conjectural or heuristic; retain counterexamples and failed mappings."
    }

def main():
    p=argparse.ArgumentParser(); p.add_argument("--template"); p.add_argument("--validate",type=Path); a=p.parse_args()
    if a.template: print(json.dumps(template(a.template),indent=2)); return 0
    if not a.validate: p.error("provide --template or --validate")
    spec=json.loads(a.validate.read_text(encoding="utf-8")); errors=validate(spec)
    print(json.dumps({"ok":not errors,"errors":errors,"problem_id":spec.get("problem_id")},indent=2))
    return 0 if not errors else 2
if __name__=="__main__": raise SystemExit(main())
