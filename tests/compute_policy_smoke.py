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


cost = policy["cost_policy"]
assert cost["monetary_budget"] == "zero_spend"
assert cost["existing_github_runners_are_free"] is True
assert cost["avrea_runners_allowed"] is True
assert cost["external_self_hosted_runners_allowed"] is True
assert cost["paid_railway_resources_allowed"] is False
assert cost["paid_cloud_expansion_allowed"] is False

selection = policy["selection_policy"]
assert selection["default_preflight"] == "L1"
assert selection["default_qualification"] == "L3"
assert by_id["L3"]["fallback_runner"] == "ubuntu-latest"
assert by_id["L3"]["can_promote"] is False
assert selection["heavy_lane"] == "L4"
external = selection["external_runner_repo"]
assert external["repository"] == "morganaspim/Cace-app"
assert external["monetary_cost"] == "free"
assert external["authority"] == "qualification-only"
assert external["install_or_dispatch_requires_capability_probe"] is True
assert set(external["discovered_labels"]) == {"self-hosted", "cace", "oci", "aarch64"}

base44 = selection["external_integrations"]["base44"]
assert base44["status"] == "telemetry-only"
assert base44["monetary_cost"] == "zero-spend-only"
assert base44["canonical"] is False
assert base44["can_qualify"] is False
assert base44["can_promote"] is False
assert "store canonical proofs or proof-memory state" in base44["prohibited_actions"]
assert "store credentials, deploy keys, or private key material" in base44["prohibited_actions"]
assert "use paid Builder sandbox or paid resources" in base44["prohibited_actions"]
assert "enable billing or purchase credits" in base44["prohibited_actions"]

promotion = policy["promotion"]
required = set(promotion["required_evidence"])
assert "lean_verified" in required
assert "repository_ci_passed" in required
assert "authority_contract_unchanged" in required
assert promotion["human_or_policy_gate_required"] is True
assert promotion["railway_preflight_is_advisory_only"] is True

print("compute policy guardrails: PASS")

