#!/usr/bin/env python3
"""Fail-closed matched input and residual screen; never authorizes promotion."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

HEX=re.compile(r"[0-9a-f]{64}\Z")
def metric(item,key):
    v=item.get(key)
    if type(v) not in (float,int) or not math.isfinite(v) or v<0:
        raise ValueError("invalid finite metric "+key)
    return float(v)

def screen(evidence):
    if evidence.get("schema_version")!=1 or evidence.get("kind")!="cace-matched-benchmark-v1":
        raise ValueError("wrong schema")
    if evidence.get("sealed_before_candidate") is not True:
        raise ValueError("holdouts must be sealed")
    if not HEX.fullmatch(evidence.get("case_manifest_sha256","")):
        raise ValueError("unbound holdout manifest")
    rows=evidence.get("cases")
    if not isinstance(rows,list) or len(rows)<3:
        raise ValueError("at least 3 holdouts required")
    seen=set(); regressions=[]; baseline=candidate=0.
    for row in rows:
        ident=row.get("id")
        if not isinstance(ident,str) or not ident or ident in seen:
            raise ValueError("duplicate/missing case ID")
        seen.add(ident)
        a=row.get("baseline_input_sha256","")
        b=row.get("candidate_input_sha256","")
        if not HEX.fullmatch(a) or a!=b:
            raise ValueError("not an identical pinned input")
        x=metric(row,"baseline_seconds");y=metric(row,"candidate_seconds")
        if x<=0 or y<=0:raise ValueError("nonpositive runtime")
        baseline+=x;candidate+=y
        tolerance=metric(row,"maximum_allowed_residual")
        old=metric(row,"baseline_residual")
        new=metric(row,"candidate_residual")
        if row.get("independent_residual_check") is not True or (
          new>tolerance or new>old+max(1e-12,tolerance*0.001)):
            regressions.append(ident+": numerical residual")
    gain=1-candidate/baseline
    if gain<=0:regressions.append("no matched aggregate speedup")
    return {"schema_version":1,"experiment":"cace-matched-holdout-screen-v1",
       "evidence_sha256":hashlib.sha256(json.dumps(
          evidence,sort_keys=True,separators=(",",":"),allow_nan=False
          ).encode()).hexdigest(),
       "cases":len(rows),"relative_timing_delta":gain,
       "candidate_meets_screen":not regressions,"failures":regressions,
       "independent_runner_attestation":False,
       "lean_assumption_mapping_checked":False,
       "rollback_and_authority_checked":False,
       "production_performance_qualified":False,
       "promotion_authorized":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",type=Path,required=True)
    p.add_argument("-o",type=Path,required=True)
    a=p.parse_args()
    result=screen(json.loads(a.evidence.read_text()))
    a.o.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"cases":result["cases"],
       "screen_passed":result["candidate_meets_screen"],"promotion":False}))
