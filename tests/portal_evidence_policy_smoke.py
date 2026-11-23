#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "portal", ROOT / "scripts" / "evaluate_portal_evidence.py"
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

policy = json.loads(
    (ROOT / "config" / "portal_evidence_policy.json").read_text(encoding="utf-8")
)

# Satisfying only P0 must never allow a P4 interpretation.
p0req = policy["classes"][0]["minimum_required"]
result = module.evaluate({
    "requested_class": "P4_spacetime_connection",
    "satisfied_requirements": p0req,
    "independent_replications": 0,
}, policy)
assert result["highest_supported_class"] == "P0_perceptual"
assert result["requested_class_supported"] is False

# A complete P0 + P1 packet with independent replication may support P1,
# but still cannot skip P2-P4.
req = []
for row in policy["classes"][:2]:
    req.extend(row["minimum_required"])
result2 = module.evaluate({
    "requested_class": "P1_information",
    "satisfied_requirements": req,
    "independent_replications": 1,
}, policy)
assert result2["highest_supported_class"] == "P1_information"
assert result2["requested_class_supported"] is True

print("portal evidence gate: PASS")
