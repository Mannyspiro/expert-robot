#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
policy = json.loads((ROOT / "config" / "compute_policy.json").read_text(encoding="utf-8"))

assert policy["schema_version"] == 1
assert policy["authority_invariant"] == "Capability grows, authority never expands."

levels = policy["levels"]
assert [level["id"] for level in levels] == ["L0", "L1", "L2", "L3", "L4"]
assert len({level["id"] for level in levels}) == len(levels)

by_id = {level["id"]: level for level in levels}

for level_id in ("L0", "L1", "L2"):
    assert by_id[level_id]["can_qualify"] is False
    assert by_id[level_id]["can_promote"] is False

for level_id in ("L3", "L4"):
    assert by_id[level_id]["can_qualify"] is True
    assert by_id[level_id]["can_promote"] is False

assert by_id["L1"]["resources"]["recommended_build_jobs"] == 1
assert by_id["L2"]["resources"]["recommended_build_jobs"] == 1

preflight = policy["preflight"]
assert preflight["failure_blocks_escalation"] is True
assert preflight["pass_implies_promotion"] is False
assert preflight["railway_is_qualification_authority"] is False

promotion = policy["promotion"]
required = set(promotion["required_evidence"])
assert "lean_verified" in required
assert "repository_ci_passed" in required
assert "authority_contract_unchanged" in required
assert promotion["human_or_policy_gate_required"] is True
assert promotion["railway_preflight_is_advisory_only"] is True

print("compute policy guardrails: PASS")
