#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
suite_path=ROOT/"config/benchmarks/progression_math_v4.json"
baseline_path=ROOT/"config/benchmarks/g3_progression_v4_baseline.json"
blind_path=ROOT/"config/blind_evaluation_policy.json"

suite_bytes=suite_path.read_bytes()
suite=json.loads(suite_bytes)
baseline=json.loads(baseline_path.read_text(encoding="utf-8"))
blind=json.loads(blind_path.read_text(encoding="utf-8"))

def is_progression_case(case):
    tags=set(case.get("tags", []))
    return "progression" in tags or any(tag.startswith("hard_v") for tag in tags)

assert suite["suite_id"]=="progression-math-v4"
assert baseline["source_candidate_sha"]=="0b4c9b29e50890785fbe36d4a849e297f480bcd1"
blob=b"blob "+str(len(suite_bytes)).encode("ascii")+b"\0"+suite_bytes
assert baseline["suite_git_blob_sha"]==hashlib.sha1(blob).hexdigest()

validation=sorted(c["case_id"] for c in suite["cases"] if c["split"]=="validation" and is_progression_case(c))
holdout=sorted(c["case_id"] for c in suite["cases"] if c["split"]=="holdout" and is_progression_case(c))
sentinels=sorted(c["case_id"] for c in suite["cases"] if c["split"] in {"validation","holdout"} and not is_progression_case(c))
ids=baseline["evaluation_case_ids"]
assert ids["progression_validation"]==validation
assert ids["progression_holdout"]==holdout
assert ids["required_verified_sentinels"]==sentinels
assert validation and holdout and sentinels

hidden=set(blind["hidden_identifiers"])
by_id={c["case_id"]:c for c in suite["cases"]}
for case_id in validation+holdout:
    assert case_id in hidden
    assert by_id[case_id]["declaration_name"] in hidden
    assert by_id[case_id]["knowledge_mode"]=="blind_generalization"
    assert by_id[case_id]["focus_theorem"]==""

variants={v["variant_id"] for v in suite["variants"]}
assert set(baseline["variants"])==variants
rates=[]
for variant in variants:
    val=float(baseline["variants"][variant]["validation"]["verified_rate"])
    hold=float(baseline["variants"][variant]["holdout"]["verified_rate"])
    assert 0.0 <= val <= 1.0
    assert 0.0 <= hold <= 1.0
    rates.append(val)
    ev=baseline["case_evidence"][variant]
    for case_id in sentinels:
        assert ev[case_id] is True
assert min(rates)<1.0, "post-G3 v4 validation is saturated"

print("progression v4 baseline integrity: PASS")
