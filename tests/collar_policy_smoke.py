#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
policy = json.loads((ROOT / "config" / "collar_policy.json").read_text())
plan = json.loads((ROOT / "config" / "implementation_plan.json").read_text())

assert policy["user_passkey_required"] is False
assert policy["rsi_start_allowed"] is True
assert policy["encryption"]["required"] is True
assert policy["encryption"]["key_destruction_on_trip"] is True
assert policy["encryption"]["plaintext_destruction_on_trip"] is True
assert policy["sandbox"]["network_default"] == "none"
assert policy["sandbox"]["outer_boundary_required"] is True
assert policy["sandbox"]["container_image_digest_required"] is True
assert policy["sandbox"]["supervisor_canary_required"] is True
assert "one-use" in policy["encryption"]["generation_key"]
assert policy["sandbox"]["run_as_root"] is False
assert policy["sandbox"]["capabilities"] == "drop_all"
assert policy["sandbox"]["read_only_root"] is True
assert policy["promotion"]["automatic"] is True
assert policy["promotion"]["forbidden_after_trip"] is True
assert policy["recursive_self_modification"]["allowed"] is True
assert policy["recursive_self_modification"]["authority_change"] == "same_or_less"
required = set(policy["promotion"]["requires"])
for gate in (
    "merit_demonstrated",
    "qualification_passed",
    "validation_improved",
    "blind_holdout_non_regression",
    "formal_verification_passed",
    "rollback_verified",
    "authority_contract_unchanged",
    "core_integrity_verified",
    "collar_not_tripped",
):
    assert gate in required
assert "host/hypervisor" in policy["limitation"]

assert plan["stop_condition"] == "rsi_ready"
assert plan["automation"]["may_start_rsi"] is True
assert plan["automation"]["requires_collared_execution"] is True
assert plan["automation"]["may_merge_without_qualification"] is False
assert plan["automation"]["monetary_budget"] == "zero_spend"
assert plan["phases"][-1]["terminal_state"] == "rsi_ready"

print("collar policy smoke: PASS")
