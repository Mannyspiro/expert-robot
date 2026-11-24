#!/usr/bin/env python3
"""Bounded fuzzy, finite n-valued and compositional logic exploration for Merlin."""
import argparse, itertools, json, math

FRAMEWORKS=[
 ("fuzzy_membership","graded truth, partial membership and vague predicates"),
 ("finite_n_valued","multiple discrete truth states, gaps and conflicts"),
 ("paraconsistent","inconsistent evidence without explosion"),
 ("intuitionistic","constructive proof and proof-relevant truth"),
 ("modal_temporal","necessity, possibility, time and changing truth"),
 ("probabilistic","uncertainty as probability rather than truth degree"),
 ("rough_approximation","indiscernibility and lower/upper approximations"),
 ("many_sorted_type","different kinds of objects and typed relations"),
 ("algebraic_logic","operators and algebraic structures"),
 ("topological_logic","continuity, neighborhoods and local truth"),
 ("category_semantics","compositional mappings between semantic systems"),
 ("information_logic","information gain, entropy and evidence update"),
 ("game_semantics","strategic interaction and adversarial interpretation"),
 ("quantum_logic","non-classical event structure in quantum theory")]
MATH_SYSTEMS=["algebra","geometry","topology","category_theory","combinatorics","dynamical_systems","probability_statistics","optimization","information_theory","linear_algebra","graph_networks","computation","measure_analysis","differential_equations","number_theory"]
COMPOSITION_MODES=[
 ("semantic_structure","use the logic as the semantics of the mathematical object","Do not impose a semantic layer if the object already has a precise, adequate semantics."),
 ("graded_membership","model partial membership, vague sets or graded predicates","Avoid if the question is crisp and graded membership adds no explanatory value."),
 ("constraint_logic","encode constraints, incompatibility, partial information or inconsistent inputs","Avoid if constraints are already complete, consistent and classically decidable."),
 ("proof_system","organize derivations, constructive witnesses or proof obligations","Avoid if the proposed calculus changes the target theorem or proof assumptions."),
 ("categorical_semantics","map objects and morphisms into a compositional semantic category","Require functorial laws; diagrams alone do not prove structure preservation."),
 ("state_transition","model temporal, modal or evolving truth across states","Avoid when the system has no meaningful state or temporal dimension."),
 ("optimization_objective","define graded objectives, robust constraints or multi-criteria choices","Do not optimize a truth score that lacks a calibrated interpretation."),
 ("probabilistic_inference","combine uncertain evidence with explicit probability semantics","Keep probability distinct from fuzzy membership and logical entailment."),
 ("topological_locality","represent local truth, continuity, neighborhoods or boundary behavior","Avoid when no topology or locality is intrinsic to the problem."),
 ("information_update","model evidence revision, entropy or information-preserving transformations","Require a defined information measure and update rule."),
 ("game_payoff","represent strategic interaction, adversarial choices or game semantics","Avoid without agents, strategies or meaningful interaction."),
 ("visualization_encoding","create a visual or geometric encoding of truth structures","A visualization is exploratory, not a proof of equivalence."),
 ("duality_representation","seek dual objects, order reversals or alternative representations","Require an explicit duality map and preserved invariants."),
 ("model_checking","turn finite structures into bounded, mechanically checkable state spaces","State the finite bound and what the model check cannot establish.")]
COMPAT={
 "fuzzy_membership":{"optimization":0.25,"probability_statistics":0.15,"measure_analysis":0.12,"geometry":0.08},
 "finite_n_valued":{"algebra":0.2,"computation":0.2,"graph_networks":0.12,"logic":0.2},
 "paraconsistent":{"constraint_logic":0.25,"graph_networks":0.1,"computation":0.1},
 "intuitionistic":{"proof_system":0.3,"category_theory":0.18,"topology":0.1},
 "modal_temporal":{"dynamical_systems":0.25,"differential_equations":0.12,"computation":0.1},
 "probabilistic":{"probability_statistics":0.3,"measure_analysis":0.2,"optimization":0.1},
 "rough_approximation":{"combinatorics":0.12,"graph_networks":0.12,"topology":0.1},
 "many_sorted_type":{"algebra":0.1,"category_theory":0.18,"computation":0.12},
 "algebraic_logic":{"algebra":0.3,"linear_algebra":0.1,"number_theory":0.1},
 "topological_logic":{"topology":0.3,"geometry":0.15,"dynamical_systems":0.1},
 "category_semantics":{"category_theory":0.35,"algebra":0.1,"geometry":0.1},
 "information_logic":{"information_theory":0.35,"probability_statistics":0.12,"computation":0.1},
 "game_semantics":{"optimization":0.15,"computation":0.1,"probability_statistics":0.1},
 "quantum_logic":{"linear_algebra":0.2,"geometry":0.12,"probability_statistics":0.1}}
def fuzzy_ops(a,b):
    return {"godel_and":min(a,b),"product_and":a*b,"lukasiewicz_and":max(0.0,a+b-1.0),
      "godel_or":max(a,b),"probabilistic_or":a+b-a*b,"lukasiewicz_or":min(1.0,a+b),
      "godel_implication":1.0 if a<=b else b,"lukasiewicz_implication":min(1.0,1.0-a+b),
      "product_implication":1.0 if a<=b else b/a if a>0 else 1.0}
def finite_table(n,arity=2,max_rows=4096):
    if not isinstance(n,int) or n<2: raise ValueError("n must be >= 2")
    if not isinstance(arity,int) or arity<1: raise ValueError("arity must be >= 1")
    count=n**arity
    if count>max_rows: raise ValueError(f"table has {count} rows; cap is {max_rows}")
    rows=[]
    for args in itertools.product(range(n),repeat=arity):
        rows.append({"inputs":list(args),"and_min":min(args),"or_max":max(args),
          "sum_mod_n":sum(args)%n,"product_mod_n":math.prod(args)%n,"negation_cycle":n-1-args[0]})
    return {"truth_values":list(range(n)),"arity":arity,"row_count":count,"rows":rows,
      "warning":"Example connectives only: select and justify semantics for the target problem."}
def rank_candidates(problem):
    p=(problem or "").lower()
    ranked=[]
    for name,desc in FRAMEWORKS:
        tokens=[w for w in desc.replace(","," ").split() if len(w)>3]
        hits=sum(w in p for w in tokens)
        score=min(1.0,0.2+0.16*hits)
        ranked.append({"framework":name,"description":desc,"relevance_score":round(score,3),
          "usefulness_band":"candidate" if score>=0.36 else "low_priority",
          "score_status":"heuristic lexical prior; re-rank after semantic analysis",
          "not_useful_when":"The framework adds no explanatory, predictive, computational or proof-theoretic value."})
    return sorted(ranked,key=lambda x:(-x["relevance_score"],x["framework"]))
def compose_candidates(problem,limit=64):
    if limit<1 or limit>512: raise ValueError("limit must be 1..512")
    p=(problem or "").lower()
    rows=[]
    for (logic,description),(system),(mode,utility,avoid) in itertools.product(FRAMEWORKS,MATH_SYSTEMS,COMPOSITION_MODES):
        compatibility=COMPAT.get(logic,{}).get(system,0.0)
        words=set((logic+" "+system+" "+mode+" "+description).replace("_"," ").split())
        overlap=sum(w in p for w in words if len(w)>3)
        semantic=min(0.25,0.04*overlap)
        score=round(min(1.0,0.28+compatibility+semantic),3)
        rows.append({"logic":logic,"mathematical_system":system,"composition_mode":mode,
          "potential_utility":utility,"not_useful_if":avoid,"compatibility_prior":compatibility,
          "semantic_match_prior":round(semantic,3),"rank_score":score,
          "rank_status":"heuristic candidate priority, not measured utility",
          "validation_obligation":"Define the composed structure and prove required laws or test the model against the original problem."})
    rows.sort(key=lambda x:(-x["rank_score"],x["logic"],x["mathematical_system"],x["composition_mode"]))
    return {"declared_space":{"logic_frameworks":len(FRAMEWORKS),"mathematical_systems":len(MATH_SYSTEMS),"composition_modes":len(COMPOSITION_MODES)},
      "total_combinations":len(rows),"returned":min(limit,len(rows)),"ranked_compositions":rows[:limit],
      "selection_rule":"Re-rank with domain semantics, invariant preservation, expressive adequacy, compositionality, proof support, decidability/complexity, calibration and cost. Permit an explicit not-useful conclusion."}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--n",type=int,default=3); p.add_argument("--arity",type=int,default=2); p.add_argument("--max-rows",type=int,default=4096); p.add_argument("--problem",default=""); p.add_argument("--limit",type=int,default=64); a=p.parse_args()
    print(json.dumps({"finite_logic":finite_table(a.n,a.arity,a.max_rows),
      "fuzzy_sample":[{"a":x/4,"b":y/4,"operators":fuzzy_ops(x/4,y/4)} for x,y in itertools.product(range(5),repeat=2)],
      "candidate_frameworks":rank_candidates(a.problem),"ranked_compositions":compose_candidates(a.problem,a.limit)},indent=2))
if __name__=="__main__": main()
