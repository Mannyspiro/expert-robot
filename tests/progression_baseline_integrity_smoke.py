#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
suite_path = ROOT / "config/benchmarks/progression_math_v2.json"
baseline_path = ROOT / "config/benchmarks/g2_progression_v2_baseline.json"

suite_bytes = suite_path.read_bytes()
suite = json.loads(suite_bytes)
baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
g0 = json.loads((ROOT / "config/benchmarks/g0_baseline.json").read_text(encoding="utf-8"))
blind = json.loads((ROOT / "config/blind_evaluation_policy.json").read_text(encoding="utf-8"))

assert suite["suite_id"] == "progression-math-v2"
assert baseline["source_candidate_sha"] == "16f11bf67995c7ad054da9111c0f50dd79d5ba44"
assert baseline["suite_sha256"] == hashlib.sha256(suite_bytes).hexdigest()

expected_validation = {"hard2-validation-001", "hard2-validation-003"}
expected_holdout = {"hard2-holdout-003", "hard2-holdout-006", "hard2-holdout-007"}
expected_sentinels = set(g0["evaluation_case_ids"]["validation"]) | set(
    g0["evaluation_case_ids"]["holdout_overlap"]
)

ids = baseline["evaluation_case_ids"]
assert set(ids["progression_validation"]) == expected_validation
assert set(ids["progression_holdout"]) == expected_holdout
assert set(ids["required_verified_sentinels"]) == expected_sentinels

suite_cases = {case["case_id"]: case for case in suite["cases"]}
expected_suite_ids = (
    {"train-algebra-add-zero"}
    | expected_validation
    | expected_holdout
    | expected_sentinels
)
assert set(suite_cases) == expected_suite_ids

for case_id in expected_validation | expected_holdout | expected_sentinels:
    case = suite_cases[case_id]
    assert case["knowledge_mode"] == "blind_generalization"
    assert case["focus_theorem"] == ""

assert suite_cases["train-algebra-add-zero"]["knowledge_mode"] == "known_theorem_retrieval"

hidden = set(blind["hidden_identifiers"])
for case_id in expected_validation | expected_holdout:
    assert case_id in hidden
    assert suite_cases[case_id]["declaration_name"] in hidden

variants = {v["variant_id"] for v in suite["variants"]}
assert set(baseline["variants"]) == variants
for variant in variants:
    assert 0.0 <= baseline["variants"][variant]["validation"]["verified_rate"] < 1.0
    assert 0.0 <= baseline["variants"][variant]["holdout"]["verified_rate"] <= 1.0

print("progression baseline integrity: PASS")
