#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
policy = json.loads((ROOT / "config" / "collar_policy.json").read_text())
plan = json.loads((ROOT / "config" / "implementation_plan.json").read_text())

assert policy["user_passkey_required"] is False
assert policy["rsi_start_allowed"] is False
assert policy["encryption"]["required"] is True
assert policy["encryption"]["key_destruction_on_trip"] is True
assert policy["encryption"]["plaintext_destruction_on_trip"] is True
assert policy["sandbox"]["network_default"] == "none"
assert policy["sandbox"]["run_as_root"] is False
assert policy["sandbox"]["capabilities"] == "drop_all"
assert policy["sandbox"]["read_only_root"] is True
assert policy["promotion"]["automatic"] is False
assert policy["promotion"]["forbidden_after_trip"] is True
assert "host/hypervisor" in policy["limitation"]

assert plan["stop_condition"] == "rsi_ready"
assert plan["automation"]["may_start_rsi"] is False
assert plan["automation"]["monetary_budget"] == "zero_spend"
assert plan["phases"][-1]["terminal_state"] == "rsi_ready"

print("collar policy smoke: PASS")
