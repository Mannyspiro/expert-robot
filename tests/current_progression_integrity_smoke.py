#!/usr/bin/env python3
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
suite_path=ROOT/"config/benchmarks/current_progression_suite.json"
baseline_path=ROOT/"config/benchmarks/current_progression_baseline.json"
blind_path=ROOT/"config/blind_evaluation_policy.json"

suite_bytes=suite_path.read_bytes()
suite=json.loads(suite_bytes)
baseline=json.loads(baseline_path.read_text(encoding="utf-8"))
blind=json.loads(blind_path.read_text(encoding="utf-8"))

assert suite["suite_id"].startswith("progression-math-v")
assert baseline["suite_id"]==suite["suite_id"]
assert re.fullmatch(r"[0-9a-f]{40}", baseline["source_candidate_sha"])
blob=b"blob "+str(len(suite_bytes)).encode("ascii")+b"\0"+suite_bytes
assert baseline["suite_git_blob_sha"]==hashlib.sha1(blob).hexdigest()

progression_validation=sorted(
    c["case_id"] for c in suite["cases"]
    if c["split"]=="validation" and "progression" in c.get("tags",[])
)
progression_holdout=sorted(
    c["case_id"] for c in suite["cases"]
    if c["split"]=="holdout" and "progression" in c.get("tags",[])
)
sentinels=sorted(
    c["case_id"] for c in suite["cases"]
    if c["split"] in {"validation","holdout"} and "progression" not in c.get("tags",[])
)
ids=baseline["evaluation_case_ids"]
assert ids["progression_validation"]==progression_validation
assert ids["progression_holdout"]==progression_holdout
assert ids["required_verified_sentinels"]==sentinels
assert progression_validation and progression_holdout and sentinels

hidden=set(blind["hidden_identifiers"])
by_id={c["case_id"]:c for c in suite["cases"]}
for case_id in progression_validation+progression_holdout:
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
    evidence=baseline["case_evidence"][variant]
    for case_id in sentinels:
        assert evidence[case_id] is True

assert min(rates)<1.0, "current progression validation is saturated"
print("current progression integrity: PASS")
