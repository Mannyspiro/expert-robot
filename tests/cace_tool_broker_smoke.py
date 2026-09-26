#!/usr/bin/env python3
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "cace_tool_broker.json"
VALIDATOR = ROOT / "scripts" / "validate_cace_tool_result.py"
PIN = "0e7aa229d3bb57174e281b883ee8af5445f15f75"
SOURCE = "f" * 40
HEX_A = "a" * 64
HEX_B = "b" * 64


def canonical_sha(payload):
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def request_for(capability="cace.formal.exact_pin_lean_preflight"):
    return {
        "schema_version": 1,
        "request_id": "candidate-001-probe",
        "source_repository": "Mannyspiro/expert-robot",
        "source_commit": SOURCE,
        "source_branch": "feat/candidate-001",
        "cace_repository": "morganaspim/Cace-app",
        "cace_commit": PIN,
        "capability_id": capability,
        "input_sha256": HEX_A,
        "requested_lane": "cace-oci-aarch64",
        "authority": "qualification-only",
        "promotion_authority": False,
        "monetary_cost": "free",
        "budget": {
            "wall_seconds": 300,
            "lean_checks": 4,
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


def invoke(request, result):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        request_path = tmp / "request.json"
        result_path = tmp / "result.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        result_path.write_text(json.dumps(result), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                str(POLICY),
                str(request_path),
                str(result_path),
            ],
            text=True,
            capture_output=True,
        )


def assert_rejected(request, result, needle):
    run = invoke(request, result)
    assert run.returncode != 0, run.stdout
    assert needle in (run.stderr + run.stdout), (needle, run.stderr, run.stdout)


policy = json.loads(POLICY.read_text(encoding="utf-8"))
assert policy["authority_invariant"] == "Capability grows, authority never expands."
assert policy["cace"]["pinned_commit"] == PIN
assert policy["cace"]["remote_mutation_by_probe"] is False
assert policy["defaults"]["promotion_authority"] is False
assert policy["defaults"]["automatic_merge"] is False
assert policy["defaults"]["automatic_promotion"] is False
assert all(item["can_promote"] is False for item in policy["capabilities"])
assert len({item["capability_id"] for item in policy["capabilities"]}) == len(
    policy["capabilities"]
)
assert policy["result_policy"]["base44_telemetry_authoritative"] is False
assert policy["result_policy"]["railway_relay_authoritative"] is False
assert policy["result_policy"]["vercel_observability_authoritative"] is False

# A qualifying formal capability may produce evidence eligible for evaluation,
# but never promotion authority.
request = request_for()
result = result_for(request)
run = invoke(request, result)
assert run.returncode == 0, run.stderr
normalized = json.loads(run.stdout)
assert normalized["eligible_for_evaluation"] is True
assert normalized["qualification_evidence"] is True
assert normalized["promotion_authority"] is False
assert normalized["automatic_promotion"] is False
assert len(normalized["evaluation_evidence_hash"]) == 64

# A non-qualifying regression capability can still produce useful evaluation
# evidence, but its pass must not be mislabeled formal qualification.
request = request_for("cace.regression.python")
request["budget"] = {"wall_seconds": 300, "lean_checks": 0}
result = result_for(request)
run = invoke(request, result)
assert run.returncode == 0, run.stderr
normalized = json.loads(run.stdout)
assert normalized["eligible_for_evaluation"] is True
assert normalized["qualification_evidence"] is False

# Exact CACE pinning.
request = request_for()
request["cace_commit"] = "1" * 40
result = result_for(request)
assert_rejected(request, result, "stale or unapproved CACE commit")

# Capability allowlist and lane binding.
request = request_for("cace.unreviewed.shell")
result = result_for(request)
assert_rejected(request, result, "unknown or unapproved CACE capability")

request = request_for()
request["requested_lane"] = "arbitrary-host"
result = result_for(request)
assert_rejected(request, result, "requested lane does not match capability contract")

# Budget admission before execution.
request = request_for()
request["budget"]["wall_seconds"] = 1501
result = result_for(request)
assert_rejected(request, result, "wall time budget exceeds capability maximum")

request = request_for()
request["budget"]["lean_checks"] = 9
result = result_for(request)
assert_rejected(request, result, "Lean check budget exceeds capability maximum")

# Exact request/result binding.
request = request_for()
result = result_for(request)
result["request_id"] = "different-request"
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(request, result, "result binding mismatch: request_id")

request = request_for()
result = result_for(request)
result["source_commit"] = "e" * 40
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(request, result, "result binding mismatch: source_commit")

# Authority and zero-spend gates.
request = request_for()
result = result_for(request)
result["promotion_authority"] = True
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(request, result, "result may not carry promotion authority")

request = request_for()
result = result_for(request)
result["monetary_cost"] = "paid"
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(request, result, "result must come from free resources")

# Runtime circuit breakers.
request = request_for()
result = result_for(request)
result["compute"]["wall_seconds"] = 301
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(request, result, "result exceeded requested wall time budget")

request = request_for()
result = result_for(request)
result["compute"]["lean_checks"] = 5
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(request, result, "result exceeded requested Lean check budget")

# Cryptographic evidence/result integrity.
request = request_for()
result = result_for(request)
result["evidence_sha256"] = "bad"
result["result_sha256"] = canonical_sha(
    {key: value for key, value in result.items() if key != "result_sha256"}
)
assert_rejected(request, result, "evidence_sha256 must be lowercase SHA-256")

request = request_for()
result = result_for(request)
result["status"] = "fail"  # mutate after the result digest is fixed
assert_rejected(request, result, "result_sha256 does not match canonical result payload")

print("CACE tool broker guardrails: PASS")
