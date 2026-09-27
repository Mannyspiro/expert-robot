#!/usr/bin/env python3
"""Build an immutable asynchronous CACE dispatch packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

import validate_cace_tool_result as broker

SAFE_TRANSPORT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_GENERATION_ID = SAFE_TRANSPORT_ID


def fail(message: str) -> None:
    raise SystemExit(message)


def load_object(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{path} must contain a JSON object")
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def validate_transport_policy(
    transport: dict[str, Any],
    broker_policy: dict[str, Any],
) -> None:
    if transport.get("schema_version") != 1:
        fail("unsupported async transport schema")
    if transport.get("authority_invariant") != broker.INVARIANT:
        fail("async transport authority invariant drift")
    if transport.get("broker_policy") != "config/cace_tool_broker.json":
        fail("async transport broker policy path drift")
    if transport.get("cace_repository") != broker_policy["cace"]["repository"]:
        fail("async transport CACE repository drift")
    if transport.get("cace_base_commit") != broker_policy["cace"]["pinned_commit"]:
        fail("async transport CACE base commit drift")
    if transport.get("request_branch_prefix") != "executor/expert-robot-request/":
        fail("async request branch prefix drift")
    if transport.get("return_branch_prefix") != "cace-return/":
        fail("async return branch prefix drift")
    if transport.get("executor_template") != (
        "integration/cace/workflows/expert-robot-async-request.yml"
    ):
        fail("async executor template drift")
    if transport.get("result_contract") != "cace-tool-broker-v1":
        fail("async result contract drift")
    if transport.get("trusted_dispatch_ref") != "feat/reuse-refactored-fishstick":
        fail("async trusted dispatch ref drift")
    if transport.get("require_candidate_parent_equals_dispatch_head") is not True:
        fail("async candidate-parent admission drift")

    allowed = transport.get("allowed_capabilities")
    if allowed != ["cace.external.expert_robot_formal_static"]:
        fail("async capability allowlist drift")

    for key in (
        "source_archive_max_bytes",
        "max_attempts",
        "response_deadline_seconds",
        "request_artifact_retention_days",
    ):
        value = transport.get(key)
        if not isinstance(value, int) or value <= 0:
            fail(f"invalid async transport integer: {key}")

    if transport["source_archive_max_bytes"] > 25 * 1024 * 1024:
        fail("async source archive maximum exceeds 25 MiB")
    if transport["max_attempts"] > 3:
        fail("async retry ceiling exceeds three attempts")
    if transport["response_deadline_seconds"] > 3600:
        fail("async response deadline exceeds one hour")

    for key in (
        "zero_spend_only",
        "force_push_forbidden",
        "dispatcher_secret_job_executes_candidate",
    ):
        expected = True if key != "dispatcher_secret_job_executes_candidate" else False
        if transport.get(key) is not expected:
            fail(f"async transport safety drift: {key}")

    if transport.get("automatic_merge") is not False:
        fail("async transport automatic merge is forbidden")
    if transport.get("automatic_promotion") is not False:
        fail("async transport automatic promotion is forbidden")


def main() -> int:
    if len(sys.argv) not in {7, 8}:
        fail(
            "usage: build_cace_async_packet.py "
            "<broker-policy.json> <transport-policy.json> "
            "<request.json> <generation-id> <source-archive.tar.gz> "
            "<trusted-base-commit> [attempt]"
        )

    broker_policy = broker.load(sys.argv[1])
    transport = load_object(sys.argv[2])
    request = broker.load(sys.argv[3])
    generation_id = sys.argv[4]
    archive = Path(sys.argv[5])
    trusted_base_commit = sys.argv[6]
    attempt = int(sys.argv[7]) if len(sys.argv) == 8 else 1

    capabilities = broker.validate_policy(broker_policy)
    validated = broker.validate_request(
        broker_policy,
        request,
        capabilities,
    )
    validate_transport_policy(transport, broker_policy)

    if not SAFE_GENERATION_ID.fullmatch(generation_id):
        fail("invalid generation_id for async transport")
    broker.require_sha40(trusted_base_commit, "trusted base commit")
    if attempt < 1 or attempt > transport["max_attempts"]:
        fail("async attempt is outside allowed retry range")

    capability = validated["capability"]
    capability_id = capability["capability_id"]
    if capability_id not in transport["allowed_capabilities"]:
        fail("capability is not allowed for async transport")
    if capability.get("executor_kind") != "expert-robot-source-bundle":
        fail("async transport requires Expert Robot source-bundle executor")

    request_id = str(request["request_id"])
    if not SAFE_TRANSPORT_ID.fullmatch(request_id):
        fail("request_id is unsafe for async branch namespace")

    if not archive.is_file():
        fail("source archive does not exist")
    archive_size = archive.stat().st_size
    if archive_size <= 0:
        fail("source archive must be non-empty")
    if archive_size > transport["source_archive_max_bytes"]:
        fail("source archive exceeds async transport maximum")

    archive_sha = file_sha256(archive)
    if archive_sha != request["input_sha256"]:
        fail("source archive SHA-256 does not match admitted request input_sha256")

    request_sha = broker.canonical_sha256(request)
    suffix = request_sha[:12]
    transport_id = f"async-{request_id}-{suffix}-a{attempt}"
    if len(transport_id) > 128 or not SAFE_TRANSPORT_ID.fullmatch(transport_id):
        fail("derived transport_id is invalid")

    request_branch = (
        transport["request_branch_prefix"]
        + request_id
        + "-"
        + suffix
        + f"-a{attempt}"
    )
    return_branch = (
        transport["return_branch_prefix"]
        + request_id
        + f"-a{attempt}"
    )

    packet = {
        "schema_version": 1,
        "transport_id": transport_id,
        "generation_id": generation_id,
        "gate_id": f"cace::{capability_id}",
        "trusted_dispatch_ref": transport["trusted_dispatch_ref"],
        "trusted_base_commit": trusted_base_commit,
        "request": request,
        "request_sha256": request_sha,
        "source_archive_sha256": archive_sha,
        "source_archive_size_bytes": archive_size,
        "cace_repository": transport["cace_repository"],
        "cace_base_commit": transport["cace_base_commit"],
        "request_branch": request_branch,
        "return_branch": return_branch,
        "executor_template": transport["executor_template"],
        "result_contract": transport["result_contract"],
        "attempt": attempt,
        "max_attempts": transport["max_attempts"],
        "response_deadline_seconds": transport["response_deadline_seconds"],
        "authority": "qualification-only",
        "promotion_authority": False,
        "monetary_cost": "free",
        "automatic_merge": False,
        "automatic_promotion": False,
    }
    packet["packet_sha256"] = broker.canonical_sha256(packet)
    print(json.dumps(packet, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
