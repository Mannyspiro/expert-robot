#!/usr/bin/env python3
"""Evidence-based molecular/material manufacturing readiness, fail closed.

Never mark physical or commercial release based on computed coordinates.
External gates require independent artifact identifiers, hashes and reviewers.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path


def evaluate(proposal, policy):
    if proposal.get("schema_version") != 1:
        raise ValueError("readiness proposal must declare schema_version=1")
    if proposal.get("design_route") not in policy["supported_design_routes"]:
        raise ValueError("unregistered matter design route")
    evidence=proposal.get("evidence",{})
    if not isinstance(evidence,dict):
        raise ValueError("evidence must be a mapping")
    requirements=policy["minimum_external_evidence_fields"]
    external=set(policy["external_required"])
    gates={}
    for stage in policy["stages"]:
        missing=[]
        for name in stage["required_evidence"]:
            v=evidence.get(name)
            if name in external:
                if not isinstance(v,dict) or any(not v.get(k) for k in requirements):
                    missing.append(name)
                    continue
                if v["source"].strip().lower() in (
                    "self", "generated", "modeler", "synthetic", "simulated"
                ) or v["independent_reviewer"].strip().lower() in (
                    "self", "modeler", "ai", "generated"
                ):
                    missing.append(name)
                    continue
                if not re.fullmatch("[a-fA-F0-9]{64}",str(v["sha256"])):
                    missing.append(name)
            elif v is not True:
                missing.append(name)
        gates[stage["id"]]={
            "complete":not missing,
            "missing":missing,
            "description":stage["description"]
        }
    # An evidence envelope is not itself proof of independent authenticity.
    # No trusted lab/manufacturing signing verifier is wired into this repo.
    # Thus this component may report DOCUMENT COMPLETENESS only for external
    # gates; real production-grade authorization always remains false.
    maximum="unqualified"
    for stage in policy["stages"]:
        if any(name in external for name in stage["required_evidence"]):
            break
        if gates[stage["id"]]["complete"]:
            maximum=stage["id"]
        else:
            break
    return {
        "schema_version":1,
        "matter_id":proposal.get("matter_id"),
        "max_supported_stage":maximum,
        "production_evidence_document_complete":gates["production_grade"]["complete"],
        "production_grade":False,
        "external_evidence_authenticated":False,
        "physical_synthesis_executed":False,
        "gates":gates,
        "interpretation":"Document/evidence gate only; does not authenticate external evidence or constitute manufacturing certification."
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("proposal",type=Path)
    p.add_argument("--policy",type=Path,
                   default=Path("config/matter_manufacturing_readiness_policy.json"))
    p.add_argument("-o","--output",type=Path)
    a=p.parse_args()
    output=evaluate(json.loads(a.proposal.read_text(encoding="utf-8")),
                    json.loads(a.policy.read_text(encoding="utf-8")))
    text=json.dumps(output,indent=2,sort_keys=True)+"\n"
    if a.output:
        a.output.write_text(text,encoding="utf-8")
    else:
        print(text,end="")


if __name__=="__main__":
    main()
