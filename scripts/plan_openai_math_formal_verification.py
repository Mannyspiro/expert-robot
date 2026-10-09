#!/usr/bin/env python3
"""Deterministic no-compute batching plan for all 200 pinned OpenAI Lean declarations.

Planning is not proof verification. Actual comparator/kernel runs are separate,
run serially with exact source/toolchain/manifest pins and independent axiom audit.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/"docs/openai-math-catalog-2026-10-09.json"
INDEX=ROOT/"docs/openai-math-all-manuscripts-index-2026-10-09.json"
UPSTREAM="fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb"

def plan(batch_size=4):
    if type(batch_size) is not int or batch_size not in range(1,11):
        raise ValueError("bounded batch_size 1..10")
    data=json.loads(CATALOG.read_text(encoding="utf-8"))
    manuscripts=json.loads(INDEX.read_text(encoding="utf-8"))
    if data["source_commit"]!=UPSTREAM or manuscripts["source_commit"]!=UPSTREAM:
        raise ValueError("mismatched upstream version")
    rows=data["declared_results"]
    if len(rows)!=200 or len({x["declaration"] for x in rows})!=200:
        raise ValueError("unexpected proof target cardinality")
    # Prefer graph/numerical/computational core. This is relevance, not truth.
    scores={
      "TreewidthL1":120,"PlanarL1":115,"CycleDecomposition":110,
      "UniformSparsestCut":105,"CompleteCrouzeix":100,
      "DirectCrouzeix":95,"MatrixMultiplication":90,"MatrixFields":88,
      "WeakHessian":85,"WeakMTW":82,"VlasovMaxwell":78,
      "MaxCut":76,"BinPacking":74
    }
    def key(r):
        hay=r["comparator_config"]+" "+r["module_file"]+" "+r["declaration"]
        score=max((v for k,v in scores.items() if k in hay),default=0)
        return (-score,r["comparator_config"],r["declaration"])
    ordered=sorted(rows,key=key)
    batches=[]
    for start in range(0,len(ordered),batch_size):
        chunk=ordered[start:start+batch_size]
        batches.append({
            "batch_index":len(batches),"planned_results":len(chunk),
            "target_declarations":[x["declaration"] for x in chunk],
            "comparator_configurations":sorted({x["comparator_config"] for x in chunk}),
            "source_modules":sorted({x["module_file"] for x in chunk}),
            "verification_state":"not_run",
            "expected_replay":"upstream pinned Lean + comparator + independent checker",
            "proofs_verified":0,
        })
    seen=[d for b in batches for d in b["target_declarations"]]
    if len(seen)!=200 or len(set(seen))!=200:
        raise AssertionError("dropped or duplicated declaration")
    return {
        "schema_version":1,"experiment":"openai-math-formal-verification-batch-plan-v1",
        "upstream_repo":"openai/math","upstream_sha":UPSTREAM,
        "upstream_lean_toolchain":data["source_toolchain"],
        "mathlib_rev":data["source_mathlib_revision"],
        "upstream_formalization_blob_sha":data["formalization_yaml_blob_sha"],
        "proposed_batch_size":batch_size,"all_declared_results":200,
        "number_of_batches":len(batches),
        "batches":batches,"completed_kernel_checks":0,
        "formalized_claims_outside_catalogue":0,
        "remaining_manuscripts_without_formalized_main_result":
            len(manuscripts["manuscripts"])-len(data["papers"]),
        "resource_policy":"run one finite job at a time; source + toolchain pinned; costs and CI status separately attested",
        "production_or_promotion_authority":False,
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("-o","--output",required=True)
    p.add_argument("--batch-size",type=int,default=4)
    args=p.parse_args()
    out=plan(args.batch_size)
    destination=Path(args.output)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in out.items() if k!="batches"}))
