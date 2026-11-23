#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mine_experiment_math.py"
FIXTURE = ROOT / "config" / "examples" / "math_discovery_smoke.json"

spec = importlib.util.spec_from_file_location("mine_experiment_math", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
result = module.mine(payload)

assert result["epistemic_status"] == "hypothesis_generation_only_not_proof"
assert result["candidate_count"] == 3

by_id = {c["candidate_id"].split("::")[-1]: c for c in result["candidates"]}

m = by_id["error-monotone"]
assert m["pattern_class"] == "monotonicity"
assert m["empirical_support"]["fit_score"] == 1.0
assert m["status"] == "INSPIRED"

s = by_id["quadratic-scale"]
assert s["pattern_class"] == "scaling_law"
assert s["empirical_support"]["fit_score"] > 0.999999999
assert "k≈2" in s["informal_statement"]
assert s["proof_ref"] is None

i = by_id["orientation-invariance"]
assert i["pattern_class"] == "invariance"
assert i["empirical_support"]["counterexamples_found"] == 0
assert i["empirical_support"]["max_observed_residual"] == 0.0

print("experiment math miner: PASS")
