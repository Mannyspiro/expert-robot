#!/usr/bin/env python3
"""Assemble math research packet: representations, logic lenses, ideonomy and Lean obligations."""
import argparse, importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
def build(problem,limit=48,n=3,arity=2):
    fuzzy=load("fuzzy","merlin_logic_lenses.py")
    ideas=load("ideas","merlin_ideonomy.py")
    planmod=load("engineering","merlin_engineering_plan.py")
    plan=planmod.template("math-research")
    plan["objective"]="Explore a mathematical research problem using decomposition, representation changes, logic lenses and ideonomy; return candidates for formal verification."
    plan["domain_scope"]["primary_domain"]="mathematics"
    plan["domain_scope"]["subsystems"]=["mathematical logic","algebra","geometry","formal methods","research ideonomy"]
    plan["requirements"][0].update(statement="Generate a bounded, ranked idea space and candidate mathematical hypotheses.",acceptance="Each idea includes a test or disconfirmation path.")
    plan["design"]["method"]="Compare mathematically meaningful representations and logic semantics; formalize only selected candidates."
    plan["design"]["limitations"]="Generated ideas and heuristic relevance scores are candidate-only."
    plan["problem_representation"]["original_problem"]=problem
    plan["problem_representation"]["decomposition"]["subproblems"][0].update(objective="Identify objects, definitions, assumptions and invariants",interface="Formal problem specification",acceptance="All symbols and hypotheses are explicit")
    plan["problem_representation"]["decomposition"]["subproblems"][1].update(objective="Compare alternate formulations and derive candidates",interface="Representation graph and candidate list",acceptance="Mappings have explicit preservation and loss conditions")
    plan["problem_representation"]["representations"][0].update(encoding="Original mathematical statement",mapping="Identity",preserved_invariants=["original statement"],lost_information=[],validity_conditions=["same domain"],validation_method="Compare exact definitions")
    plan["problem_representation"]["representations"][1].update(encoding="Typed representation graph",mapping="Objects map to nodes and transformations to typed edges",preserved_invariants=["declared structure"],lost_information=["presentation order"],validity_conditions=["maps are explicitly specified"],non_transferable_properties=["Graph connection alone does not establish equivalence."],validation_method="Prove map and invariant lemmas")
    plan["research_methods"]["ideonomy"].update(enumeration_scope="Lens x transformation x relation x question move",candidate_limit=limit)
    plan["research_methods"]["logic_lenses"].update(n_values=n,truth_table_arity=arity)
    plan["verification"].update(tests=["Validate logic tables and idea-space bounds","Check all candidate hypotheses have disconfirmation paths"],independent_check="Lean kernel checks selected formal claims; independent reviewer checks semantics and assumptions.")
    return {
      "schema_version":1,"problem":problem,
      "mandatory_methods":["decompose","multi_representation","fuzzy_logic_lenses","finite_n_valued_logic_lenses","ideonomy_enumeration","hypothesis_generation","Lean_formalization"],
      "problem_representation":plan["problem_representation"],
      "logic_lenses":{"fuzzy_operators":["godel_and","product_and","lukasiewicz_and","godel_or","probabilistic_or","lukasiewicz_or","godel_implication","lukasiewicz_implication","product_implication"],
       "finite_logic":fuzzy.finite_table(n,arity),"ranked_candidates":fuzzy.rank_candidates(problem),
       "ranked_compositions":fuzzy.compose_candidates(problem,limit),
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
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(result["engineering_plan"],indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
if __name__=="__main__": main()
