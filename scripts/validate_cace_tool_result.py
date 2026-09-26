#!/usr/bin/env python3
"""Fail-closed validation for CACE tool-broker requests and results."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-\\-]{0,127}$")
SAFE_BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")
INVARIANT = "Capability grows, authority never expands."


def fail(message: str) -> None:
    raise SystemExit(message)


def load(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{path} must contain a JSON object")
    return payload


def require_fields(payload: dict[str, Any], names: set[str], label: str) -> None:
    missing = sorted(names - payload.keys())
    if missing:
        fail(f"{label} missing fields: {', '.join(missing)}")


def require_sha40(value: Any, label: str) -> str:
    text = str(value)
    if not SHA40.fullmatch(text):
        fail(f"{label} must be lowercase 40-character git SHA")
    return text


def require_sha256(value: Any, label: str) -> str:
    text = str(value)
    if not SHA256.fullmatch(text):
        fail(f"{label} must be lowercase SHA-256")
    return text


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_policy(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if policy.get("schema_version") != 1:
        fail("unsupported broker policy schema")
    if policy.get("authority_invariant") != INVARIANT:
        fail("authority invariant drift")

    cace = policy.get("cace")
    defaults = policy.get("defaults")
    result_policy = policy.get("result_policy")
    if not isinstance(cace, dict) or not isinstance(defaults, dict):
        fail("broker policy requires cace/defaults objects")
    if not isinstance(result_policy, dict):
        fail("broker policy requires result_policy object")

    require_sha40(cace.get("pinned_commit"), "pinned CACE commit")
    if cace.get("repository") != "morganaspim/Cace-app":
        fail("unexpected CACE repository")
    if cace.get("remote_mutation_by_probe") is not False:
        fail("capability probe must not mutate CACE")

    if defaults.get("authority") != "qualification-only":
        fail("broker authority must be qualification-only")
    if defaults.get("promotion_authority") is not False:
        fail("broker may not carry promotion authority")
    if defaults.get("monetary_cost") != "free":
        fail("broker is restricted to free lanes")
    if defaults.get("automatic_merge") is not False:
        fail("automatic merge is forbidden")
    if defaults.get("automatic_promotion") is not False:
        fail("automatic promotion is forbidden")

    capabilities = policy.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        fail("broker requires a non-empty capability allowlist")

    by_id: dict[str, dict[str, Any]] = {}
    for item in capabilities:
        if not isinstance(item, dict):
            fail("capability entries must be objects")
        capability_id = str(item.get("capability_id", ""))
        if not SAFE_ID.fullmatch(capability_id):
            fail(f"invalid capability_id: {capability_id!r}")
        if capability_id in by_id:
            fail(f"duplicate capability_id: {capability_id}")
        if item.get("can_promote") is not False:
            fail(f"{capability_id}: CACE capability may not promote")
        if item.get("lane") != "cace-oci-aarch64":
            fail(f"{capability_id}: unexpected execution lane")
        if not str(item.get("workflow", "")).startswith(".github/workflows/"):
            fail(f"{capability_id}: workflow must be repository-scoped")
        for key in ("max_wall_seconds", "max_lean_checks"):
            value = item.get(key)
            if not isinstance(value, int) or value < 0:
                fail(f"{capability_id}: invalid {key}")
        by_id[capability_id] = item

    required_true = (
        "exact_request_binding_required",
        "exact_source_commit_binding_required",
        "exact_cace_commit_binding_required",
        "evidence_sha256_required",
        "result_sha256_required",
        "pass_is_evidence_only",
        "promotion_requires_existing_external_boundary",
    )
    for key in required_true:
        if result_policy.get(key) is not True:
            fail(f"result policy requires {key}=true")
    for key in (
        "base44_telemetry_authoritative",
        "railway_relay_authoritative",
        "vercel_observability_authoritative",
    ):
        if result_policy.get(key) is not False:
            fail(f"{key} must remain false")
    if result_policy.get("accepted_result_statuses") != ["pass", "fail"]:
        fail("accepted result statuses drift")

    return by_id


def main() -> int:
    if len(sys.argv) != 4:
        fail(
            "usage: validate_cace_tool_result.py "
            "<broker-policy.json> <request.json> <result.json>"
        )

    policy = load(sys.argv[1])
    request = load(sys.argv[2])
    result = load(sys.argv[3])
    capabilities = validate_policy(policy)

    require_fields(
        request,
        {
            "schema_version",
            "request_id",
            "source_repository",
            "source_commit",
            "source_branch",
            "cace_repository",
            "cace_commit",
            "capability_id",
            "input_sha256",
            "requested_lane",
            "authority",
            "promotion_authority",
            "monetary_cost",
            "budget",
        },
        "request",
    )
    if request["schema_version"] != 1:
        fail("unsupported request schema")
    if not SAFE_ID.fullmatch(str(request["request_id"])):
        fail("invalid request_id")
    if request["source_repository"] != policy["source_repository"]:
        fail("source repository mismatch")
    source_commit = require_sha40(request["source_commit"], "source commit")
    if not SAFE_BRANCH.fullmatch(str(request["source_branch"])):
        fail("invalid source branch")
    require_sha256(request["input_sha256"], "input_sha256")
    if request["cace_repository"] != policy["cace"]["repository"]:
        fail("CACE repository mismatch")
    if request["cace_commit"] != policy["cace"]["pinned_commit"]:
        fail("stale or unapproved CACE commit")
    require_sha40(request["cace_commit"], "request CACE commit")

    capability_id = str(request["capability_id"])
    capability = capabilities.get(capability_id)
    if capability is None:
        fail("unknown or unapproved CACE capability")
    if request["requested_lane"] != capability["lane"]:
        fail("requested lane does not match capability contract")

    if request["authority"] != "qualification-only":
        fail("request authority escalation")
    if request["promotion_authority"] is not False:
        fail("request may not grant promotion authority")
    if request["monetary_cost"] != "free":
        fail("request must use free resources")

    budget = request["budget"]
    if not isinstance(budget, dict):
        fail("request budget must be an object")
    require_fields(budget, {"wall_seconds", "lean_checks"}, "request budget")
    wall_budget = budget["wall_seconds"]
    lean_budget = budget["lean_checks"]
    if not isinstance(wall_budget, int) or wall_budget < 0:
        fail("invalid wall_seconds budget")
    if not isinstance(lean_budget, int) or lean_budget < 0:
        fail("invalid lean_checks budget")
    if wall_budget > capability["max_wall_seconds"]:
        fail("wall time budget exceeds capability maximum")
    if lean_budget > capability["max_lean_checks"]:
        fail("Lean check budget exceeds capability maximum")

    require_fields(
        result,
        {
            "schema_version",
            "request_id",
            "source_repository",
            "source_commit",
            "cace_repository",
            "cace_commit",
            "capability_id",
            "status",
            "cace_run_id",
            "authority",
            "promotion_authority",
            "monetary_cost",
            "compute",
            "evidence_sha256",
            "result_sha256",
        },
        "result",
    )
    if result["schema_version"] != 1:
        fail("unsupported result schema")

    exact_pairs = (
        ("request_id", "request_id"),
        ("source_repository", "source_repository"),
        ("source_commit", "source_commit"),
        ("cace_repository", "cace_repository"),
        ("cace_commit", "cace_commit"),
        ("capability_id", "capability_id"),
    )
    for request_key, result_key in exact_pairs:
        if result[result_key] != request[request_key]:
            fail(f"result binding mismatch: {result_key}")

    require_sha40(result["source_commit"], "result source commit")
    require_sha40(result["cace_commit"], "result CACE commit")
    if result["status"] not in policy["result_policy"]["accepted_result_statuses"]:
        fail("invalid result status")
    if not SAFE_ID.fullmatch(str(result["cace_run_id"])):
        fail("invalid CACE run id")
    if result["authority"] != "qualification-only":
        fail("result authority escalation")
    if result["promotion_authority"] is not False:
        fail("result may not carry promotion authority")
    if result["monetary_cost"] != "free":
        fail("result must come from free resources")

    compute = result["compute"]
    if not isinstance(compute, dict):
        fail("result compute must be an object")
    require_fields(compute, {"wall_seconds", "lean_checks"}, "result compute")
    wall_used = compute["wall_seconds"]
    lean_used = compute["lean_checks"]
    if not isinstance(wall_used, int) or wall_used < 0:
        fail("invalid result wall_seconds")
    if not isinstance(lean_used, int) or lean_used < 0:
        fail("invalid result lean_checks")
    if wall_used > wall_budget:
        fail("result exceeded requested wall time budget")
    if lean_used > lean_budget:
        fail("result exceeded requested Lean check budget")

    evidence_sha = require_sha256(result["evidence_sha256"], "evidence_sha256")
    supplied_result_sha = require_sha256(result["result_sha256"], "result_sha256")
    result_payload = dict(result)
    result_payload.pop("result_sha256")
    calculated_result_sha = canonical_sha256(result_payload)
    if supplied_result_sha != calculated_result_sha:
        fail("result_sha256 does not match canonical result payload")

    status_pass = result["status"] == "pass"
    qualification_capability = bool(capability["can_qualify"])
    qualification_evidence = bool(status_pass and qualification_capability)
    gate_id = f"cace::{capability_id}" if qualification_capability else None
    normalized = {
        "schema_version": 1,
        "request_id": request["request_id"],
        "capability_id": capability_id,
        "status": result["status"],
        "source_commit": source_commit,
        "cace_commit": request["cace_commit"],
        "evidence_sha256": evidence_sha,
        "result_sha256": supplied_result_sha,
        "eligible_for_evaluation": status_pass,
        "eligible_for_lineage": True,
        "qualification_capability": qualification_capability,
        "qualification_evidence": qualification_evidence,
        "gate_id": gate_id,
        "required_for_promotion": qualification_capability,
        "gate_passed": status_pass if qualification_capability else None,
        "promotion_authority": False,
        "automatic_promotion": False,
        "evaluation_evidence_hash": canonical_sha256(
            {
                "request": request,
                "result_sha256": supplied_result_sha,
                "evidence_sha256": evidence_sha,
            }
        ),
    }
    print(json.dumps(normalized, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
