#!/usr/bin/env python3
"""RI planner: scope, credit budget, independence, holdout and Pareto tests."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "verified_rsi_planner",ROOT/"scripts"/"plan_verified_rsi.py"
)
planner=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(planner)

catalog=json.loads((ROOT/"config"/"verified_rsi_integration_catalog.json").read_text())
scope=json.loads((ROOT/"config"/"auto_promotion_scope.json").read_text())
policy=json.loads((ROOT/"config"/"experiment_policy.json").read_text())
assert len(catalog["candidate_routes"])==8
assert all(x["reuse"] in ("ideas_only","concept_only")
           for x in catalog["sources"])
assert catalog["verified_evaluator_boundary"]["holdout_mutable_by_candidate"] is False
assert catalog["evidence_rules"]["never_execute_from_planner"] is True
assert catalog["evidence_rules"]["never_promote_from_planner"] is True

no_budget=planner.plan(catalog,scope,policy,remaining_credits=0)
assert no_budget["modelled_max_credit_reservation"]==0
assert all(x["planned_runs"]==0 for x in no_budget["diversity_selected_plans"])
assert no_budget["candidate_code_executed"] is False
assert no_budget["automatic_promotion_authorized"] is False
assert no_budget["lineages_promoted"]==0
assert no_budget["account_wide_remaining_credits_verified"] is False
assert len(set(x["diversity_group"] for x in
    no_budget["diversity_selected_plans"]))>=3
assert no_budget["pareto_route_ids"]
assert no_budget["epistemic_status"]=="planning_priors_not_measured_capability_improvements"

plan=planner.plan(catalog,scope,policy,remaining_credits=240)
assert plan["modelled_max_credit_reservation"]<=240
assert plan["credits_unallocated"]>=0
assert any(x["planned_runs"]>=2 for x in plan["diversity_selected_plans"])
assert all(not x["execution_authorized"] for x in plan["diversity_selected_plans"])
assert all(not x["empirical_gain_verified"] for x in plan["ranked_routes"])
assert all(x["promotion_status"]=="NOT_AUTHORIZED" for x in plan["ranked_routes"])
assert next(x for x in plan["ranked_routes"] if x["route_id"]=="browser-visual-acquisition")[
    "auto_scope_paths_plausible"
] is False
assert next(x for x in plan["ranked_routes"] if x["route_id"]=="solver-sparse-operator")["target_repository"]=="morganaspim/Cace-app"
assert next(x for x in plan["ranked_routes"] if x["route_id"]=="solver-sparse-operator")["auto_scope_paths_plausible"] is False
assert next(x for x in plan["ranked_routes"] if x["route_id"]=="solver-sparse-operator")["external_repository_qualification_required"] is True
assert next(x for x in plan["ranked_routes"] if x["route_id"]=="lean-lemma-factory")["target_repository"]=="Mannyspiro/expert-robot"
assert next(x for x in plan["ranked_routes"] if x["route_id"]=="lean-lemma-factory")[
    "auto_scope_paths_plausible"
] is True

def feedback(route,group,delta,sha="a"*64):
    return {
        "route_id":route,"independence_group":group,
        "artifact_sha256":sha,"validation_delta":delta,
        "holdout_sealed":True,
        "feedback":"Synthetic test trace, not real benchmark evidence.",
    }

repeated=planner.plan(catalog,scope,policy,240,[
    feedback("solver-sparse-operator","cace-mesh-a",0.2),
    feedback("solver-sparse-operator","cace-mesh-a",0.8),
])
unique=planner.plan(catalog,scope,policy,240,[
    feedback("solver-sparse-operator","cace-mesh-a",0.2),
])
by_id=lambda x:{row["route_id"]:row for row in x["ranked_routes"]}
assert by_id(repeated)["solver-sparse-operator"]["expected_gain"]==by_id(unique)["solver-sparse-operator"]["expected_gain"]
assert by_id(repeated)["solver-sparse-operator"]["independent_feedback_groups"]==1
assert len(repeated["ranked_routes"])==8

def rejects(records, **kwargs):
    try:
        planner.plan(catalog,scope,policy,feedback=records,**kwargs)
    except ValueError:
        return
    raise AssertionError("unsafe/unqualified input was accepted")

rejects([feedback("unknown","group",0.1)])
rejects([{**feedback("solver-sparse-operator","g",0.1),"holdout_sealed":False}])
rejects([{**feedback("solver-sparse-operator","g",0.1),"artifact_sha256":"bad"}])
rejects([
    feedback("solver-sparse-operator","g",0.1,sha="a"*64),
    feedback("solver-sparse-operator","g",0.2,sha="b"*64),
])
rejects([],remaining_credits=1501)
rejects([],remaining_credits=-1)

malicious=copy.deepcopy(catalog)
malicious["release_mode"]="auto"
try:
    planner.plan(malicious,scope,policy)
except ValueError:
    pass
else:
    raise AssertionError("planner gained execution authority")

assert planner.legal_auto_scope([".github/workflows/ci.yml"],scope) is False
assert planner.legal_auto_scope(["scripts/check_avrea_halfmonth_budget.py"],scope) is False
assert planner.legal_auto_scope(["cpp/src/proof_search.cpp"],scope) is True
assert planner.legal_auto_scope(["../../etc/passwd"],scope) is False

print("verified cross-domain RSI planner: PASS")
