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
assert selection["heavy_lane"] == "L4"
external = selection["external_runner_repo"]
assert external["repository"] == "morganaspim/Cace-app"
assert external["monetary_cost"] == "free"
assert external["authority"] == "qualification-only"
assert external["install_or_dispatch_requires_capability_probe"] is True
assert set(external["discovered_labels"]) == {"self-hosted", "cace", "oci", "aarch64"}
assert external["broker_policy"] == "config/cace_tool_broker.json"
assert external["pinned_commit"] == "0e7aa229d3bb57174e281b883ee8af5445f15f75"
assert external["capability_probe_runner"] == "avrea-ubuntu-latest-1-vcpu"
assert external["capability_probe_cache"] is False
assert external["capability_probe_artifact_retention_days"] == 1
assert external["result_is_evidence_only"] is True
assert external["promotion_authority"] is False

headless = selection["local_headless_reasoner"]
assert headless["role"] == "untrusted-informal-reasoner"
assert headless["network_policy"] == "loopback-only"
assert headless["config"] == "config/cace_headless_local.json"
assert headless["cace_repository"] == "morganaspim/Cace-app"
assert headless["cace_branch"] == "expert-robot/headless-local-llm"
assert headless["cace_revision"] == "0aa3b2e00724f647bb629fe7e4765e41fa245e3b"
assert headless["model"] == "Qwen/Qwen3.5-4B"
assert headless["model_revision"] == "a7b0d22b993d71000cf2eadfb37222a67cee521e"
assert headless["llama_cpp_commit"] == "b29c606e28a01b1bc8c1351026a0fa6e616bf6c4"
assert headless["requires_runtime_admission"] is True
assert headless["model_can_execute_tools"] is False
assert headless["model_can_mark_verified"] is False
assert headless["deterministic_cace_execution_separate"] is True
assert headless["runtime_artifact_hashes_required"] is True
assert headless["can_qualify"] is False
assert headless["can_promote"] is False

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
