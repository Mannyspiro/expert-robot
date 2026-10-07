#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

miner = load_module("miner", ROOT / "scripts" / "mine_experiment_math.py")
selector = load_module("selector", ROOT / "scripts" / "select_math_candidates.py")

fixture = json.loads(
    (ROOT / "config" / "examples" / "math_discovery_smoke.json").read_text()
)
policy = json.loads(
    (ROOT / "config" / "math_discovery_policy.json").read_text()
)

mined = miner.mine(fixture)
queue = selector.select(mined, policy)

assert queue["epistemic_status"] == "selected_for_testing_not_proven"
assert queue["selected_count"] == 3
assert queue["rejected_count"] == 0
assert all(x["next_stage"] == "COUNTEREXAMPLE_SEARCH" for x in queue["selected"])

# A single empirical counterexample must block proof-search selection.
bad = json.loads(json.dumps(mined))
bad["candidates"][0]["empirical_support"]["counterexamples_found"] = 1
queue2 = selector.select(bad, policy)
assert queue2["selected_count"] == 2
assert queue2["rejected_count"] == 1
assert "observed_counterexample" in queue2["rejected"][0]["reasons"]

print("math discovery promotion policy: PASS")
