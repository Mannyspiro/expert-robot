#!/usr/bin/env python3
"""Fail-closed review of independently measured Merlin on-device model candidates.

No credential retrieval, CI signing, merging or automatic release permissions.
Only claims supported by exact baseline/candidate cases can pass model gate.
Android/native/license gates are explicitly separate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

REQUIRED_KINDS=("tool","answer","no_tool")

def _checked_cases(blob, key):
    if not isinstance(blob,dict) or "metrics" not in blob or "cases" not in blob:
        raise ValueError("Incomplete or malformed evaluation: "+key)
    cases=blob["cases"]
    if not isinstance(cases,list) or len(cases)<14:
        raise ValueError("At least 14 held-out cases required for exploratory model review")
    ids=[r.get("id") for r in cases if isinstance(r,dict)]
    if len(ids)!=len(cases) or len(set(ids))!=len(ids):
        raise ValueError("Missing or duplicate held-out identities")
    if any(type(r.get("pass")) is not bool for r in cases):
        raise ValueError("Unscored held-out cases")
    if {r.get("kind") for r in cases}!=set(REQUIRED_KINDS):
        raise ValueError("Held-out task categories are incomplete")
    counted=sum(r["pass"] for r in cases)
    if counted!=blob["metrics"].get("passed") or len(cases)!=blob["metrics"].get("total"):
        raise ValueError("Metric mismatch: "+key)
    for kind in REQUIRED_KINDS:
        samples=[r for r in cases if r["kind"]==kind]
        declared=blob["metrics"].get("by_kind",{}).get(kind,{})
        if declared.get("total")!=len(samples) or declared.get("correct")!=sum(x["pass"] for x in samples):
            raise ValueError("Per-category metric mismatch: "+kind)
    return cases

def evaluate(report):
    if report.get("schema")=="merlin-local-model-training-report/1":
        results=report.get("results",{})
        before=results.get("baseline")
        after=results.get("trained")
        if report.get("status")!="completed" or report.get("weights_created") is not True:
            return {"candidate":"LoRA","gate":"blocked","reason":"real weight training incomplete"}
        key="LoRA"
    elif report.get("schema")=="merlin-heretic-capability-ab/1":
        before=report.get("baseline")
        after=report.get("modified")
        key="Heretic"
    else:
        return {"candidate":"unknown","gate":"blocked","reason":"unrecognized evidence schema"}
    try:
        baseline=_checked_cases(before,"baseline")
        candidate=_checked_cases(after,"candidate")
        if [(x["id"],x["kind"]) for x in baseline]!=[(x["id"],x["kind"]) for x in candidate]:
            raise ValueError("Baseline and candidate used different cases")
        if any(x.get("expected")!=y.get("expected") for x,y in zip(baseline,candidate)):
            raise ValueError("Expected references changed between models")
        by_kind={
            k:{"baseline":sum(x["pass"] for x in baseline if x["kind"]==k),
               "candidate":sum(x["pass"] for x in candidate if x["kind"]==k)}
            for k in REQUIRED_KINDS}
        no_regression=all(row["candidate"]>=row["baseline"] for row in by_kind.values())
        improvement=by_kind["tool"]["candidate"]>by_kind["tool"]["baseline"] and no_regression
        return {"candidate":key,"gate":"exploratory_capability_pass" if improvement else "blocked",
                "by_kind":by_kind,"heldout_cases":len(baseline),
                "reason":"Positive local-tool difference without tested-category regression" if improvement
                  else "No demonstrated local-tool gain or a tested-category regression",
                "apk_release_qualified":False}
    except (ValueError,KeyError,TypeError) as exc:
        return {"candidate":key,"gate":"blocked","reason":str(exc),"apk_release_qualified":False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("evidence",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    try:
        raw=args.evidence.read_bytes()
        report=json.loads(raw)
        decision=evaluate(report)
        decision.update({"source_evidence_sha256":hashlib.sha256(raw).hexdigest(),
                         "release_gates":{"native_android_inference":"not demonstrated by this evaluator",
                                          "license_redistribution":"not demonstrated by this evaluator",
                                          "repeated_independent_seed":"not demonstrated by this evaluator",
                                          "signed_release":"not demonstrated by this evaluator"},
                         "apk_release_qualified":False})
    except (OSError,ValueError,TypeError) as exc:
        decision={"candidate":"unknown","gate":"blocked","reason":type(exc).__name__+": "+str(exc),
                  "apk_release_qualified":False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(decision,indent=2,sort_keys=True)+"\n")
    print(json.dumps(decision,sort_keys=True))
    if decision["gate"]!="exploratory_capability_pass":
        raise SystemExit(1)

if __name__=="__main__":
    main()
