#!/usr/bin/env python3
"""Conservative readiness gates never self-promote computational structures."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/"scripts"/"evaluate_matter_readiness.py"
spec=importlib.util.spec_from_file_location("readiness",path)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

policy=json.loads((ROOT/"config"/"matter_manufacturing_readiness_policy.json").read_text())
case=json.loads((ROOT/"config"/"examples"/"matter_readiness_computational_only.json").read_text())
result=m.evaluate(case,policy)
assert result["max_supported_stage"]=="computational_structure"
assert result["gates"]["qualified_model"]["complete"] is False
assert result["production_grade"] is False
assert result["production_evidence_document_complete"] is False
assert result["external_evidence_authenticated"] is False
assert result["physical_synthesis_executed"] is False

# A self-generated or fabricated packet with plausible hashes must *never*
# turn into production release without independent authentication machinery.
for stage in policy["stages"]:
    for evidence_id in stage["required_evidence"]:
        if evidence_id not in case["evidence"]:
            case["evidence"][evidence_id]=True
for key in policy["external_required"]:
    case["evidence"][key]={
       "evidence_id":"hypothetical",
       "source":"external lab (unverified)",
       "date":"2026-10-07",
       "independent_reviewer":"lab inspector (unverified)",
       "sha256":"a"*64,
    }
fabricated=m.evaluate(case,policy)
assert fabricated["production_evidence_document_complete"] is True
assert fabricated["production_grade"] is False
assert fabricated["max_supported_stage"]=="qualified_model"
assert fabricated["external_evidence_authenticated"] is False

case["evidence"]["lab_sample_characterized"]["source"]="self"
bad=m.evaluate(case,policy)
assert bad["gates"]["lab_verified_sample"]["complete"] is False
assert bad["production_grade"] is False

print("matter manufacturing readiness gate: PASS")
