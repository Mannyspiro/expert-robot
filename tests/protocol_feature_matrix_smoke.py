#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_protocol_feature_matrix.py"

spec = importlib.util.spec_from_file_location("analyzer", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

payload = json.loads(
    (ROOT / "config" / "examples" / "protocol_feature_matrix_smoke.json").read_text()
)
result = module.analyze(payload)

assert result["independent_group_count"] == 4
assert result["epistemic_status"] == "historical_inference_not_physical_evidence"

by_id = {x["feature_id"]: x for x in result["features"]}
nested = by_id["nested-boundaries"]
flourish = by_id["decorative-flourish"]

assert nested["best_function_signal"] > flourish["best_function_signal"]
assert nested["research_priority"] > flourish["research_priority"]
assert all("physical efficacy" in x["interpretation_guard"] for x in result["features"])

print("protocol feature matrix analysis: PASS")
