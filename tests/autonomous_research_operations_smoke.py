#!/usr/bin/env python3
"""Negative controls for the bounded research observer; no network access."""
import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "bounded_research_observer",ROOT/"scripts"/"run_autonomous_research_cycle.py")
ops=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)
policy=json.loads((ROOT/"config"/"autonomous_research_policy.json").read_text())
COMMIT="662dbb5dab5b317c83f801ae3ad7c891f7983fd1"

def rejected(fn):
    try:fn()
    except (ValueError,AssertionError):return
    raise AssertionError("invalid input crossed a trust gate")

ops.check_policy(policy)
assert tuple(x[0] for x in ops.ROUTES)==tuple(policy["fixed_route_ids"])
rejected(lambda:ops.check_policy({**policy,"automatic_promotion_authorized":True}))
rejected(lambda:ops.check_policy({**policy,"max_experiments_per_episode":2}))
rejected(lambda:ops.check_policy({**policy,"network_access_authorized":True}))
rejected(lambda:ops.check_policy({**policy,"fixed_route_ids":["attacker-task"]}))
rejected(lambda:ops.episode(dt.date(2026,10,11),"bad-sha",policy))

# This one uses the real in-repository exact rational reaction experiment.
first=ops.episode(dt.date(2026,10,11),COMMIT,policy)
assert first["selected_route"]=="reaction-conservation"
assert first["research_evidence"]["exact_balance_residual"]=="0"
assert first["promotion_authorized"] is False
assert first["external_network_used"] is False
assert first["avrea_credits_reserved"]==0
assert first==ops.episode(dt.date(2026,10,11),COMMIT,policy)
assert len(ops.encode(first))<65536
assert ops.select_route(dt.date(2026,10,12),first["selected_route"])[0]=="crnt-assumption-search"
assert ops.check_previous(first,dt.date(2026,10,12),ops.digest(policy))=="reaction-conservation"

rejected(lambda:ops.check_previous({**first,"promotion_authorized":True},dt.date(2026,10,12),ops.digest(policy)))
rejected(lambda:ops.check_previous({**first,"selected_route":"run-shell"},dt.date(2026,10,12),ops.digest(policy)))
rejected(lambda:ops.check_previous({**first,"result_sha256":"wrong"},dt.date(2026,10,12),ops.digest(policy)))
rejected(lambda:ops.check_previous({**first,"repository":"other/repo"},dt.date(2026,10,12),ops.digest(policy)))
rejected(lambda:ops.check_previous(first,dt.date(2026,10,11),ops.digest(policy)))
rejected(lambda:ops.check_previous(first,dt.date(2026,12,1),ops.digest(policy)))


# Low-trust previous-episode receipts are routing hints, never qualification.
# Accept only an exact bounded schema, consistent hashes, and fixed authority.
prior_gate_mutants=[
 ("authority_expanded",True),("external_network_used",True),
 ("scientific_truth_or_formal_verification_claimed",True),
 ("avrea_credits_reserved",1),("avrea_credits_reserved",False),
 ("conclusion","formally_verified"),("episode_id","0"*64),
 ("experiment","unregistered"),("prior_receipt_used","false"),
 ("next_route_recommendation","parser-contract-search"),
 ("result_sha256","1"*64),("source_commit","a"*40),
 ("research_evidence",{}),
]
for key,value in prior_gate_mutants:
    rejected(lambda k=key,v=value:ops.check_previous(
        {**first,k:v},dt.date(2026,10,12),ops.digest(policy)))
bad=copy.deepcopy(first)
bad["candidate"]["promotion_authorized"]=True
rejected(lambda:ops.check_previous(bad,dt.date(2026,10,12),ops.digest(policy)))
bad=copy.deepcopy(first)
bad["candidate"]["lean_gate"]="pretend_verified"
rejected(lambda:ops.check_previous(bad,dt.date(2026,10,12),ops.digest(policy)))
bad=copy.deepcopy(first)
bad["candidate"]["result_sha256"]="2"*64
rejected(lambda:ops.check_previous(bad,dt.date(2026,10,12),ops.digest(policy)))
bad=copy.deepcopy(first)
bad["candidate"]["module_sha256"]="not-a-sha"
rejected(lambda:ops.check_previous(bad,dt.date(2026,10,12),ops.digest(policy)))
bad=copy.deepcopy(first)
bad["candidate"]["cace_gate"]="already_certified"
rejected(lambda:ops.check_previous(bad,dt.date(2026,10,12),ops.digest(policy)))
rejected(lambda:ops.check_previous(
    {**first,"new_untrusted_key":"extra"},dt.date(2026,10,12),ops.digest(policy)))
rejected(lambda:ops.check_previous(
    {k:v for k,v in first.items() if k!="authority_expanded"},
    dt.date(2026,10,12),ops.digest(policy)))
rejected(lambda:ops.check_previous(
    {**first,"research_evidence":{"bomb":"X"*70000}},
    dt.date(2026,10,12),ops.digest(policy)))
# Even a self-consistent-looking forged proof flag cannot advance the route.
assert first["scientific_truth_or_formal_verification_claimed"] is False

# Synthetic producer fixtures validate the remaining three screening paths.
fixtures=[
("crnt-assumption-search",{
 "closed_irreversible":{"deficiency":0,"weakly_reversible":False},
 "reversible_catalysis_variant":{"weakly_reversible":True},
 "zero_deficiency_is_not_sufficient_for_positive_equilibrium":True}),
("enzyme-equilibrium-search",{
 "positive_parameter_grid_evaluations":6400,"positive_parameter_grid_equilibria":0,
 "dropped_equation_mutant_detected":True,
 "necessary_hypotheses_boundary_witnesses":{"a":1,"b":2,"c":3,"d":4}}),
("parser-contract-search",{
 "input_count":5660,"original_mismatches":3,"repair_violations":0,
 "mutation_failure_counts":{"identity":3,"raw_prefix":4}})
]
for route,fixture in fixtures:
    facts,source_sha=ops.screen(route,fixture)
    assert facts and len(source_sha)==64
    rejected(lambda:ops.screen(route,{**fixture,"authority_expanded":True}))
    bad=copy.deepcopy(fixture)
    if route=="crnt-assumption-search":
        bad["closed_irreversible"]["weakly_reversible"]=True
    elif route=="enzyme-equilibrium-search":
        bad["positive_parameter_grid_equilibria"]=1
    else:
        bad["repair_violations"]=1
    rejected(lambda:ops.screen(route,bad))
print("bounded offline research operations: PASS")
