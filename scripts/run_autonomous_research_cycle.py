#!/usr/bin/env python3
"""Bounded read-only research operator: one offline experiment, then evidence."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO="Mannyspiro/expert-robot"
SHA40=re.compile(r"[0-9a-f]{40}\Z")
SHA64=re.compile(r"[0-9a-f]{64}\Z")
# Never derive executable module, shell command, or permissions from artifacts.
ROUTES=(
 ("reaction-conservation","experiment_general_reaction_conservation","experiment",
  "Derive exact cellwise reaction conservation with explicit boundary sources."),
 ("crnt-assumption-search","experiment_crnt_deficiency","experiment",
  "Find counterexamples to deficiency-zero equilibrium without weak reversibility."),
 ("enzyme-equilibrium-search","experiment_biochemistry_equilibrium","solve",
  "Find positive-equilibrium counterexamples when a rate balance is omitted."),
 ("parser-contract-search","experiment_parser_differential","run",
  "Mine reduced, bounded toy-parser contract counterexamples."),
)
ROUTE_IDS=tuple(x[0] for x in ROUTES)

def encode(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def digest(x):
    return hashlib.sha256(encode(x)).hexdigest()

def check_policy(x):
    if x != {
       "schema_version":1,"mode":"offline_artifact_only","repository":REPO,
       "fixed_route_ids":list(ROUTE_IDS),"max_experiments_per_episode":1,
       "max_artifact_bytes":65536,"avrea_credit_reservation":0,
       "network_access_authorized":False,"candidate_writes_authorized":False,
       "automatic_promotion_authorized":False}:
        raise ValueError("untrusted or expanded research policy")

def check_previous(x,today,policy_sha):
    """Validate low-trust prior routing evidence; this is NOT signed attestation."""
    if x is None:return None
    required={
      "schema_version","experiment","repository","source_commit","date_utc",
      "policy_sha256","episode_id","selected_route","prior_receipt_used",
      "research_evidence","result_sha256","candidate","next_route_recommendation",
      "conclusion","external_network_used","avrea_credits_reserved",
      "scientific_truth_or_formal_verification_claimed","promotion_authorized",
      "authority_expanded"}
    if not isinstance(x,dict) or set(x)!=required or x.get("schema_version")!=1:
        raise ValueError("missing or unexpected prior receipt fields")
    if (x["repository"]!=REPO or x["policy_sha256"]!=policy_sha
        or x["experiment"]!="offline-autonomous-research-episode-v1"):
        raise ValueError("prior repository/policy/experiment mismatch")
    name=x.get("selected_route")
    if name not in ROUTE_IDS:
        raise ValueError("unapproved prior route")
    if (x["promotion_authorized"] is not False or
        x["authority_expanded"] is not False or
        x["external_network_used"] is not False or
        x["scientific_truth_or_formal_verification_claimed"] is not False or
        type(x["avrea_credits_reserved"]) is not int or
        x["avrea_credits_reserved"]!=0 or
        x["conclusion"]!="bounded_offline_experiment_only" or
        type(x["prior_receipt_used"]) is not bool):
        raise ValueError("prior receipt claims forbidden execution or authority")
    if (not SHA64.fullmatch(str(x["result_sha256"]))
        or not SHA40.fullmatch(str(x["source_commit"]))
        or not SHA64.fullmatch(str(x["episode_id"]))):
        raise ValueError("missing prior provenance")
    try:last=dt.date.fromisoformat(x["date_utc"])
    except (ValueError,KeyError,TypeError) as exc:
        raise ValueError("bad prior date") from exc
    if last>=today or last<today-dt.timedelta(days=40):
        raise ValueError("prior receipt stale or nonmonotonic")
    if x["episode_id"]!=digest([
        x["source_commit"],x["date_utc"],name,policy_sha]):
        raise ValueError("prior episode identity mismatch")
    if x["next_route_recommendation"]!=ROUTE_IDS[
        (ROUTE_IDS.index(name)+1)%len(ROUTE_IDS)]:
        raise ValueError("prior route recommendation mismatch")
    c=x["candidate"]
    if not isinstance(c,dict) or set(c)!={
        "question","module_sha256","result_sha256","status",
        "lean_gate","cace_gate","promotion_authorized"}:
        raise ValueError("invalid prior candidate")
    if (c["question"]!=ROUTES[ROUTE_IDS.index(name)][3]
        or c["result_sha256"]!=x["result_sha256"]
        or not SHA64.fullmatch(str(c["module_sha256"]))
        or c["status"]!="conjecture_or_counterexample_not_proof"
        or c["lean_gate"]!="requires_exact_kernel_axiom_audit"
        or c["cace_gate"]!="requires_independent_residual_certificate"
        or c["promotion_authorized"] is not False):
        raise ValueError("candidate provenance or qualification mismatch")
    if not isinstance(x["research_evidence"],dict) or not x["research_evidence"]:
        raise ValueError("empty or invalid prior research evidence")
    if len(encode(x))>65536:
        raise ValueError("oversized prior receipt")
    return name

def select_route(day,previous):
    if previous is not None:
        return ROUTES[(ROUTE_IDS.index(previous)+1)%len(ROUTES)]
    return ROUTES[day.toordinal()%len(ROUTES)]

def load_fixed(route):
    _,module_name,method,_=route
    path=ROOT/"scripts"/(module_name+".py")
    if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:
        raise ValueError("missing/unsafe source module")
    spec=importlib.util.spec_from_file_location(module_name,path)
    if spec is None or spec.loader is None:raise ValueError("module loader failed")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    routine=getattr(module,method)
    if not callable(routine):raise ValueError("missing registered entrypoint")
    return routine,hashlib.sha256(path.read_bytes()).hexdigest()

def screen(name,result):
    if not isinstance(result,dict):raise ValueError("unstructured research output")
    raw=encode(result)
    if len(raw)>1048576:raise ValueError("unbounded research result")
    if name=="reaction-conservation":
        cases=result.get("cases",[])
        if ([c.get("left_nullity") for c in cases]!=[2,1,2,1]
            or result.get("missing_reactant_mutant_detected") is not True
            or not (result.get("open_boundary_accounted") is True or
                    result.get("open_boundary_flux_separately_accounted") is True)
            or not (result.get("mixed_unit_mutant_rejected") is True or
                    result.get("mixed_amount_concentration_mutant_rejected") is True)
            or any(v.get("exact_residual",v.get("residual_exact"))!="0"
                   for c in cases for v in c.get("invariants",[]))):
            raise ValueError("stoichiometric oracle / mutation gate failed")
        facts={"toy_cases":4,"left_nullities":[2,1,2,1],
               "exact_balance_residual":"0","mutants_detected":True}
    elif name=="crnt-assumption-search":
        closed=result.get("closed_irreversible",{})
        rev=result.get("reversible_catalysis_variant",{})
        if (closed.get("deficiency")!=0 or closed.get("weakly_reversible") is not False
            or rev.get("weakly_reversible") is not True
            or result.get("zero_deficiency_is_not_sufficient_for_positive_equilibrium") is not True):
            raise ValueError("CRNT hypothesis/counterexample gate failed")
        facts={"deficiency_zero":True,"irreversible_variant_rejected":True}
    elif name=="enzyme-equilibrium-search":
        if (result.get("positive_parameter_grid_evaluations")!=6400
            or result.get("positive_parameter_grid_equilibria")!=0
            or result.get("dropped_equation_mutant_detected") is not True
            or len(result.get("necessary_hypotheses_boundary_witnesses",{}))!=4):
            raise ValueError("equilibrium mutation gate failed")
        facts={"finite_grid_evaluations":6400,"counterexample_classes":4}
    elif name=="parser-contract-search":
        mutants=result.get("mutation_failure_counts",{})
        if (result.get("repair_violations")!=0
            or result.get("original_mismatches",0)<1
            or not mutants or any(type(n) is not int or n<=0 for n in mutants.values())):
            raise ValueError("parser oracle/counterexample gate failed")
        facts={"inputs":result.get("input_count"),
               "original_witnesses":result.get("original_mismatches"),
               "contract_violations":0,"mutant_detection":mutants}
    else:raise ValueError("unregistered route")
    for claim in ("authority_expanded","promotion_authorized",
                  "production_promotion_authority","promotion_or_authority_expanded"):
        if result.get(claim) is True:raise ValueError("producer attempted authority claim")
    return facts,hashlib.sha256(raw).hexdigest()

def episode(day,commit,policy,previous=None):
    check_policy(policy)
    if not SHA40.fullmatch(commit):raise ValueError("full Git commit required")
    if not isinstance(day,dt.date):raise ValueError("UTC date required")
    pol_sha=digest(policy)
    prev=check_previous(previous,day,pol_sha)
    route=select_route(day,prev)
    producer,module_sha=load_fixed(route)
    facts,result_sha=screen(route[0],producer())
    proposed={
      "question":route[3],"module_sha256":module_sha,"result_sha256":result_sha,
      "status":"conjecture_or_counterexample_not_proof",
      "lean_gate":"requires_exact_kernel_axiom_audit",
      "cace_gate":"requires_independent_residual_certificate",
      "promotion_authorized":False}
    receipt={
      "schema_version":1,"experiment":"offline-autonomous-research-episode-v1",
      "repository":REPO,"source_commit":commit,"date_utc":day.isoformat(),
      "policy_sha256":pol_sha,"episode_id":digest([commit,day.isoformat(),route[0],pol_sha]),
      "selected_route":route[0],"prior_receipt_used":prev is not None,
      "research_evidence":facts,"result_sha256":result_sha,
      "candidate":proposed,
      "next_route_recommendation":ROUTE_IDS[(ROUTE_IDS.index(route[0])+1)%len(ROUTES)],
      "conclusion":"bounded_offline_experiment_only",
      "external_network_used":False,"avrea_credits_reserved":0,
      "scientific_truth_or_formal_verification_claimed":False,
      "promotion_authorized":False,"authority_expanded":False}
    if len(encode(receipt))>policy["max_artifact_bytes"]:
        raise ValueError("output artifact too large")
    return receipt

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--policy",type=Path,default=ROOT/"config"/"autonomous_research_policy.json")
    ap.add_argument("--date",help="UTC date")
    ap.add_argument("--source-commit",required=True)
    ap.add_argument("--previous",type=Path)
    ap.add_argument("-o","--output",type=Path,required=True)
    a=ap.parse_args()
    if a.output.is_symlink() or a.output.is_dir():raise ValueError("unsafe output")
    if a.policy.is_symlink() or a.policy.stat().st_size>8192:raise ValueError("unsafe policy file")
    policy=json.loads(a.policy.read_text(encoding="utf-8"))
    previous=None
    if a.previous:
        if a.previous.is_symlink() or a.previous.stat().st_size>65536:
            raise ValueError("unbounded prior artifact")
        previous=json.loads(a.previous.read_text(encoding="utf-8"))
    date=dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(dt.timezone.utc).date()
    receipt=episode(date,a.source_commit,policy,previous)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:receipt[k] for k in
          ("episode_id","selected_route","next_route_recommendation",
           "conclusion","promotion_authorized")}))

if __name__=="__main__":main()
