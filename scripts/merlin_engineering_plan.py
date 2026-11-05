#!/usr/bin/env python3
"""Validate the mandatory engineering/research plan gate for Merlin tasks."""
import argparse, json, re, sys
from pathlib import Path

REQUIRED = ("task_id","objective","domain_scope","requirements","assumptions",
            "reasoning_plan","design","resource_budget","verification","rollback")
def validate(plan):
    errors=[]
    if not isinstance(plan,dict): return ["plan must be a JSON object"]
    missing=[k for k in REQUIRED if k not in plan]
    if missing: errors.append("missing required sections: "+", ".join(missing))
    scope=plan.get("domain_scope",{})
    if not scope.get("primary_domain"): errors.append("domain_scope.primary_domain is required")
    if not isinstance(scope.get("subsystems",[]),list): errors.append("domain_scope.subsystems must be a list")
    if not isinstance(scope.get("excluded_domains",[]),list): errors.append("domain_scope.excluded_domains must be a list")
    reqs=plan.get("requirements",[])
    if not isinstance(reqs,list) or not reqs: errors.append("at least one requirement is required")
    else:
        ids=[r.get("id") for r in reqs if isinstance(r,dict)]
        if len(ids)!=len(reqs) or any(not x for x in ids): errors.append("every requirement needs an id")
        if len(set(ids))!=len(ids): errors.append("requirement ids must be unique")
        if any(not r.get("acceptance") for r in reqs if isinstance(r,dict)): errors.append("every requirement needs an acceptance criterion")
    assumptions=plan.get("assumptions",[])
    if not isinstance(assumptions,list): errors.append("assumptions must be a list (use [] when none)")
    reasoning=plan.get("reasoning_plan",{})
    for key in ("inductive","deductive","abductive","disconfirmation"):
        if not reasoning.get(key): errors.append("reasoning_plan."+key+" must be addressed; use 'not applicable' with rationale")
    design=plan.get("design",{})
    for key in ("method","limitations","bias_review"):
        if not design.get(key): errors.append("design."+key+" must be addressed")
    budget=plan.get("resource_budget",{})
    for key in ("max_runtime_seconds","max_memory_mb","max_disk_bytes","max_input_bytes"):
        if not isinstance(budget.get(key),int) or budget[key] <= 0: errors.append("resource_budget."+key+" must be a positive integer")
    verify=plan.get("verification",{})
    if not verify.get("tests") or not verify.get("independent_check"): errors.append("verification needs tests and an independent_check")
    if not plan.get("rollback"): errors.append("rollback strategy is required")
    return errors

def template(task_id):
    return {
      "plan_version":1,"task_id":task_id,"objective":"",
      "domain_scope":{"primary_domain":"","subsystems":[],"secondary_domains":[],"excluded_domains":[],"scope_rationale":""},
      "requirements":[{"id":"REQ-001","statement":"","acceptance":""}],
      "assumptions":[],"constraints":[],"dependencies":[],
      "reasoning_plan":{"inductive":"Not applicable; explain why or describe sample and limits.","deductive":"List premises, rules and derived obligations.","abductive":"Compare at least two plausible explanations/designs.","disconfirmation":"Name counterexamples and failure conditions."},
      "design":{"method":"","alternatives":[],"limitations":"","bias_review":{"possible_biases":[],"possible_fallacies":[],"checks":[]}},
      "resource_budget":{"max_runtime_seconds":300,"max_memory_mb":1024,"max_disk_bytes":10485760,"max_input_bytes":1048576},
      "verification":{"tests":["unit"],"independent_check":"Describe independent verifier or reviewer."},
      "rollback":"Describe how to revert without damaging canonical data."
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--validate",type=Path)
    p.add_argument("--template")
    a=p.parse_args()
    if a.template:
        print(json.dumps(template(a.template),indent=2)); return 0
    if not a.validate: p.error("provide --validate or --template")
    try: plan=json.loads(a.validate.read_text(encoding="utf-8"))
    except Exception as e: print(json.dumps({"ok":False,"error":str(e)})); return 2
    errors=validate(plan)
    print(json.dumps({"ok":not errors,"errors":errors,"task_id":plan.get("task_id")},indent=2))
    return 0 if not errors else 2
if __name__=="__main__": raise SystemExit(main())
