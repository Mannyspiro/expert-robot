#!/usr/bin/env python3
"""Deterministically plan bounded CACE tool requests from changed repository paths."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import PurePosixPath, Path
from typing import Any

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")


def fail(message: str) -> None:
    raise SystemExit(message)


def load_policy(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read broker policy: {exc}")
    if payload.get("schema_version") != 1:
        fail("unsupported broker policy schema")
    if payload.get("authority_invariant") != "Capability grows, authority never expands.":
        fail("broker authority invariant drift")
    return payload


def normalize_path(raw: str) -> str:
    value = raw.strip().replace("\\", "/")
    if not value:
        fail("changed paths must be non-empty")
    path = PurePosixPath(value)
    if path.is_absolute() or "." in path.parts or ".." in path.parts:
        fail(f"unsafe changed path: {raw!r}")
    normalized = str(path)
    if normalized.startswith("../") or normalized == "..":
        fail(f"unsafe changed path: {raw!r}")
    return normalized


def capability_map(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = policy.get("capabilities")
    if not isinstance(items, list) or not items:
        fail("broker policy has no capabilities")
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            fail("invalid capability policy entry")
        capability_id = str(item.get("capability_id", ""))
        if not capability_id or capability_id in by_id:
            fail("invalid or duplicate capability_id")
        if item.get("can_promote") is not False:
            fail("CACE capability may not carry promotion authority")
        by_id[capability_id] = item
    return by_id


def bounded_budget(
    capability: dict[str, Any],
    *,
    wall_seconds: int,
    lean_checks: int,
) -> dict[str, int]:
    maximum_wall = int(capability["max_wall_seconds"])
    maximum_lean = int(capability["max_lean_checks"])
    return {
        "wall_seconds": min(wall_seconds, maximum_wall),
        "lean_checks": min(lean_checks, maximum_lean),
    }


def request_id(
    source_commit: str,
    capability_id: str,
    input_sha256: str,
) -> str:
    short_capability = capability_id.replace(".", "-").replace("_", "-")
    seed = f"{source_commit}:{capability_id}:{input_sha256}".encode("utf-8")
    suffix = hashlib.sha256(seed).hexdigest()[:10]
    value = f"cace-{source_commit[:8]}-{short_capability}-{suffix}"
    return value[:128]


def make_request(
    policy: dict[str, Any],
    capability: dict[str, Any],
    source_commit: str,
    source_branch: str,
    input_sha256: str,
    budget: dict[str, int],
    changed_paths: list[str],
) -> dict[str, Any]:
    defaults = policy["defaults"]
    return {
        "schema_version": 1,
        "request_id": request_id(
            source_commit,
            capability["capability_id"],
            input_sha256,
        ),
        "source_repository": policy["source_repository"],
        "source_commit": source_commit,
        "source_branch": source_branch,
        "cace_repository": policy["cace"]["repository"],
        "cace_commit": policy["cace"]["pinned_commit"],
        "capability_id": capability["capability_id"],
        "executor_kind": capability["executor_kind"],
        "workflow_repository": capability["workflow_repository"],
        "workflow": capability["workflow"],
        "input_sha256": input_sha256,
        "requested_lane": capability["lane"],
        "authority": defaults["authority"],
        "promotion_authority": False,
        "monetary_cost": defaults["monetary_cost"],
        "budget": budget,
        "changed_paths": changed_paths,
    }


def main() -> int:
    if len(sys.argv) < 6:
        fail(
            "usage: plan_cace_tool_requests.py <broker-policy.json> "
            "<source-commit> <source-branch> <input-sha256> <changed-path>..."
        )

    policy = load_policy(sys.argv[1])
    source_commit = sys.argv[2]
    source_branch = sys.argv[3]
    input_sha256 = sys.argv[4]
    if not SHA40.fullmatch(source_commit):
        fail("source commit must be lowercase 40-character git SHA")
    if not SAFE_BRANCH.fullmatch(source_branch):
        fail("invalid source branch")
    if not SHA256.fullmatch(input_sha256):
        fail("input_sha256 must be lowercase SHA-256")

    changed_paths = sorted({normalize_path(item) for item in sys.argv[5:]})
    if not changed_paths:
        fail("at least one changed path is required")

    by_id = capability_map(policy)

    lean_paths = [
        path
        for path in changed_paths
        if path.startswith("formal/MathAI/") and path.endswith(".lean")
    ]
    formal_infra_paths = [
        path
        for path in changed_paths
        if path.startswith("formal/") and path not in lean_paths
    ]
    avrea_paths = [
        path
        for path in changed_paths
        if path == "CMakeLists.txt"
        or path.startswith("cpp/")
        or path.endswith((".cpp", ".cc", ".cxx", ".hpp", ".h"))
        or path.startswith("models/")
        or path.startswith("runtime/")
        or path in formal_infra_paths
    ]

    requests: list[dict[str, Any]] = []
    reasons: list[str] = []

    if lean_paths:
        capability_id = "cace.external.expert_robot_formal_static"
        capability = by_id.get(capability_id)
        if capability is None:
            fail(f"required capability missing from allowlist: {capability_id}")
        if capability.get("executor_kind") != "expert-robot-source-bundle":
            fail("formal Expert Robot source requires source-bundle executor")
        requests.append(
            make_request(
                policy,
                capability,
                source_commit,
                source_branch,
                input_sha256,
                bounded_budget(
                    capability,
                    wall_seconds=1200,
                    lean_checks=40,
                ),
                lean_paths,
            )
        )
        reasons.append(
            "Expert Robot formal changes routed to the pinned CACE "
            "source-bundle qualification lane"
        )

    if any(
        path.endswith(".py") or path.startswith("python/")
        for path in changed_paths
    ):
        reasons.append(
            "Expert Robot Python changes are not routed to CACE-native Python "
            "regression; normal repository CI remains required"
        )

    if any(
        path.startswith("collaboration/")
        or path.startswith("config/collaboration")
        for path in changed_paths
    ):
        reasons.append(
            "Expert Robot collaboration changes are not routed to CACE-native "
            "collaboration validation; normal repository CI remains required"
        )

    requires_avrea = bool(avrea_paths)
    if formal_infra_paths:
        reasons.append(
            "Lean build/dependency infrastructure changes require repository "
            "qualification and are not admitted to the CACE source-bundle lane"
        )

    if requires_avrea:
        reasons.append(
            "C++/model/runtime or formal-infrastructure changes require Avrea "
            "repository qualification; CACE OCI is not treated as a general build lane"
        )

    if not requests and not requires_avrea:
        reasons.append(
            "no reviewed CACE capability is justified by these paths; "
            "use local/static and normal repository CI only"
        )

    output = {
        "schema_version": 1,
        "source_repository": policy["source_repository"],
        "source_commit": source_commit,
        "source_branch": source_branch,
        "input_sha256": input_sha256,
        "cace_repository": policy["cace"]["repository"],
        "cace_commit": policy["cace"]["pinned_commit"],
        "changed_paths": changed_paths,
        "cace_requests": requests,
        "requires_avrea": requires_avrea,
        "avrea_paths": avrea_paths,
        "repository_ci_required": True,
        "automatic_dispatch": False,
        "automatic_promotion": False,
        "reasons": reasons,
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
