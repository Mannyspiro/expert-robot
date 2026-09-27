#!/usr/bin/env python3
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "cace_tool_broker.json"
VALIDATOR = ROOT / "scripts" / "validate_cace_tool_result.py"
PIN = "0e7aa229d3bb57174e281b883ee8af5445f15f75"
SOURCE = "f" * 40
HEX_A = "a" * 64
HEX_B = "b" * 64
CAPABILITY = "cace.external.expert_robot_formal_static"


def canonical_sha(payload):
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def request_for():
    return {
        "schema_version": 1,
        "request_id": "candidate-001-probe",
        "source_repository": "Mannyspiro/expert-robot",
        "source_commit": SOURCE,
        "source_branch": "feat/candidate-001",
        "cace_repository": "morganaspim/Cace-app",
        "cace_commit": PIN,
        "capability_id": CAPABILITY,
        "executor_kind": "expert-robot-source-bundle",
        "workflow_repository": "Mannyspiro/expert-robot",
        "workflow": ".github/workflows/external-free-runner-bridge.yml",
        "input_sha256": HEX_A,
        "requested_lane": "cace-oci-aarch64",
        "authority": "qualification-only",
        "promotion_authority": False,
        "monetary_cost": "free",
        "budget": {
            "wall_seconds": 1200,
            "lean_checks": 40,
        },
        "candidate_id": "candidate-001",
        "parent_generation_id": "generation-000",
    }


def result_for(request, *, status="pass"):
    payload = {
        "schema_version": 1,
        "request_id": request["request_id"],
        "source_repository": request["source_repository"],
        "source_commit": request["source_commit"],
        "cace_repository": request["cace_repository"],
        "cace_commit": request["cace_commit"],
        "capability_id": request["capability_id"],
        "status": status,
        "cace_run_id": "cace-run-001",
        "authority": "qualification-only",
        "promotion_authority": False,
        "monetary_cost": "free",
        "compute": {
            "wall_seconds": 20,
            "lean_checks": min(2, request["budget"]["lean_checks"]),
        },
        "evidence_sha256": HEX_B,
    }
    payload["result_sha256"] = canonical_sha(payload)
    return payload


def invoke(request, result, policy_payload=None):
    with tempfile.TemporaryDirectory() as tmp_raw:
        tmp = Path(tmp_raw)
        request_path = tmp / "request.json"
        result_path = tmp / "result.json"
        policy_path = tmp / "policy.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        result_path.write_text(json.dumps(result), encoding="utf-8")
        if policy_payload is None:
            policy_payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        policy_path.write_text(json.dumps(policy_payload), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                str(policy_path),
                str(request_path),
                str(result_path),
            ],
            text=True,
            capture_output=True,
        )


def assert_rejected(request, result, needle, policy_payload=None):
    run = invoke(request, result, policy_payload)
    assert run.returncode != 0, run.stdout
    assert needle in (run.stderr + run.stdout), (
        needle,
        run.stderr,
        run.stdout,
    )


policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
assert policy["authority_invariant"] == "Capability grows, authority never expands."
assert policy["source_repository"] == "Mannyspiro/expert-robot"
assert policy["cace"]["pinned_commit"] == PIN
assert policy["cace"]["remote_mutation_by_probe"] is False
assert policy["native_cace_capabilities"]["status"] == "discovery-only"
assert policy["native_cace_capabilities"]["repository"] == "morganaspim/Cace-app"

assert len(policy["capabilities"]) == 1
capability = policy["capabilities"][0]
assert capability["capability_id"] == CAPABILITY
assert capability["executor_kind"] == "expert-robot-source-bundle"
assert capability["source_repository"] == "Mannyspiro/expert-robot"
assert capability["workflow_repository"] == "Mannyspiro/expert-robot"
assert capability["workflow"] == ".github/workflows/external-free-runner-bridge.yml"
assert capability["can_qualify"] is True
assert capability["can_promote"] is False

# A valid source-bundle result is evidence/gate state only.
request = request_for()
result = result_for(request)
run = invoke(request, result)
assert run.returncode == 0, run.stderr
normalized = json.loads(run.stdout)
assert normalized["qualification_capability"] is True
assert normalized["qualification_evidence"] is True
assert normalized["gate_id"] == f"cace::{CAPABILITY}"
assert normalized["required_for_promotion"] is True
assert normalized["gate_passed"] is True
assert normalized["promotion_authority"] is False
assert normalized["automatic_promotion"] is False

# Failed qualification still emits a blocking gate result.
result = result_for(request, status="fail")
run = invoke(request, result)
assert run.returncode == 0, run.stderr
normalized = json.loads(run.stdout)
assert normalized["qualification_evidence"] is False
assert normalized["required_for_promotion"] is True
assert normalized["gate_passed"] is False

# Exact CACE source pin.
bad = request_for()
bad["cace_commit"] = "1" * 40
assert_rejected(bad, result_for(bad), "stale or unapproved CACE commit")

# Unknown/native CACE capabilities are not callable through this broker.
bad = request_for()
bad["capability_id"] = "cace.formal.exact_pin_lean_preflight"
assert_rejected(bad, result_for(bad), "unknown or unapproved CACE capability")

# Executor identity is part of the request contract.
for field, value, error in (
    ("requested_lane", "arbitrary-host", "requested lane"),
    ("executor_kind", "cace-native", "executor kind"),
    ("workflow_repository", "morganaspim/Cace-app", "workflow repository"),
    ("workflow", ".github/workflows/cace-exact-pin-lean-preflight.yml", "request workflow"),
):
    bad = request_for()
    bad[field] = value
    assert_rejected(bad, result_for(bad), error)

# Policy itself cannot reclassify a native CACE workflow as an Expert Robot
# source verifier.
native_policy = copy.deepcopy(policy)
native_policy["capabilities"][0]["executor_kind"] = "cace-native"
native_policy["capabilities"][0]["workflow_repository"] = "morganaspim/Cace-app"
assert_rejected(
    request_for(),
    result_for(request_for()),
    "native CACE workflows are not Expert Robot source verifiers",
    native_policy,
)

# Compute admission.
bad = request_for()
bad["budget"]["wall_seconds"] = 1501
assert_rejected(bad, result_for(bad), "wall time budget exceeds capability maximum")

bad = request_for()
bad["budget"]["lean_checks"] = 41
assert_rejected(bad, result_for(bad), "Lean check budget exceeds capability maximum")

# Exact request/result binding.
request = request_for()
result = result_for(request)
result["request_id"] = "different-request"
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(request, result, "result binding mismatch: request_id")

result = result_for(request)
result["source_commit"] = "e" * 40
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(request, result, "result binding mismatch: source_commit")

# Authority/zero-spend gates.
result = result_for(request)
result["promotion_authority"] = True
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(request, result, "result may not carry promotion authority")

result = result_for(request)
result["monetary_cost"] = "paid"
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(request, result, "result must come from free resources")

# Runtime circuit breakers.
small = request_for()
small["budget"] = {"wall_seconds": 30, "lean_checks": 2}
result = result_for(small)
result["compute"]["wall_seconds"] = 31
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(small, result, "result exceeded requested wall time budget")

result = result_for(small)
result["compute"]["lean_checks"] = 3
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(small, result, "result exceeded requested Lean check budget")

# Cryptographic integrity.
result = result_for(request)
result["evidence_sha256"] = "bad"
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(request, result, "evidence_sha256 must be lowercase SHA-256")

result = result_for(request)
result["status"] = "fail"
assert_rejected(
    request,
    result,
    "result_sha256 does not match canonical result payload",
)

print("CACE tool broker guardrails: PASS")
