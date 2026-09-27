#!/usr/bin/env python3
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BROKER = ROOT / "config" / "cace_tool_broker.json"
TRANSPORT = ROOT / "config" / "cace_async_transport.json"
PLANNER = ROOT / "scripts" / "plan_cace_tool_requests.py"
BUILDER = ROOT / "scripts" / "build_cace_async_packet.py"
SOURCE = "a" * 40
BASE = "d" * 40


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(payload) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def plan(input_sha: str):
    run = subprocess.run(
        [
            sys.executable,
            str(PLANNER),
            str(BROKER),
            SOURCE,
            "feat/async-smoke",
            input_sha,
            "formal/MathAI/Geometry/Exact.lean",
        ],
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, run.stderr
    payload = json.loads(run.stdout)
    assert len(payload["cace_requests"]) == 1
    return payload["cace_requests"][0]


def build(
    tmp: Path,
    request: dict,
    archive: Path,
    *,
    transport_payload=None,
    generation_id="generation-async-001",
    trusted_base=BASE,
    attempt=1,
):
    request_path = tmp / "request.json"
    transport_path = tmp / "transport.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    if transport_payload is None:
        transport_payload = json.loads(TRANSPORT.read_text(encoding="utf-8"))
    transport_path.write_text(json.dumps(transport_payload), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            str(BROKER),
            str(transport_path),
            str(request_path),
            generation_id,
            str(archive),
            trusted_base,
            str(attempt),
        ],
        text=True,
        capture_output=True,
    )


with tempfile.TemporaryDirectory() as tmp_raw:
    tmp = Path(tmp_raw)
    archive = tmp / "source.tar.gz"
    archive.write_bytes(b"immutable-expert-robot-source-bundle")
    archive_sha = sha(archive.read_bytes())
    request = plan(archive_sha)

    first = build(tmp, request, archive)
    assert first.returncode == 0, first.stderr
    packet = json.loads(first.stdout)

    assert packet["schema_version"] == 1
    assert packet["generation_id"] == "generation-async-001"
    assert packet["trusted_dispatch_ref"] == "feat/reuse-refactored-fishstick"
    assert packet["trusted_base_commit"] == BASE
    assert (
        packet["gate_id"]
        == "cace::cace.external.expert_robot_formal_static"
    )
    assert packet["request"] == request
    assert packet["request_sha256"] == canonical(request)
    assert packet["source_archive_sha256"] == archive_sha
    assert packet["source_archive_size_bytes"] == archive.stat().st_size
    assert (
        packet["cace_base_commit"]
        == "0e7aa229d3bb57174e281b883ee8af5445f15f75"
    )
    assert packet["request_branch"].startswith(
        "executor/expert-robot-request/"
    )
    assert packet["return_branch"] == f'cace-return/{request["request_id"]}'
    assert packet["attempt"] == 1
    assert packet["request_branch"].endswith("-a1")
    assert packet["return_branch"].endswith("-a1")
    assert packet["max_attempts"] == 3
    assert packet["response_deadline_seconds"] == 1800
    assert packet["authority"] == "qualification-only"
    assert packet["promotion_authority"] is False
    assert packet["monetary_cost"] == "free"
    assert packet["automatic_merge"] is False
    assert packet["automatic_promotion"] is False

    without_hash = dict(packet)
    supplied = without_hash.pop("packet_sha256")
    assert supplied == canonical(without_hash)

    # Deterministic inputs produce byte-equivalent packet JSON.
    again = build(tmp, request, archive)
    assert again.returncode == 0, again.stderr
    assert json.loads(again.stdout) == packet


    retry = build(tmp, request, archive, attempt=2)
    assert retry.returncode == 0, retry.stderr
    retry_packet = json.loads(retry.stdout)
    assert retry_packet["attempt"] == 2
    assert retry_packet["request_branch"] != packet["request_branch"]
    assert retry_packet["return_branch"] != packet["return_branch"]
    assert retry_packet["transport_id"] != packet["transport_id"]

    rejected = build(tmp, request, archive, attempt=4)
    assert rejected.returncode != 0
    assert "outside allowed retry range" in (
        rejected.stderr + rejected.stdout
    )

    # Archive tampering after admission is rejected.
    archive.write_bytes(b"tampered")
    rejected = build(tmp, request, archive)
    assert rejected.returncode != 0
    assert "does not match admitted request" in (
        rejected.stderr + rejected.stdout
    )

    # Restore archive and reject unsafe request IDs that cannot become branch
    # names even if the broader broker identifier syntax would accept them.
    archive.write_bytes(b"immutable-expert-robot-source-bundle")
    bad_request = copy.deepcopy(request)
    bad_request["request_id"] = "unsafe:request"
    rejected = build(tmp, bad_request, archive)
    assert rejected.returncode != 0
    assert "unsafe for async branch namespace" in (
        rejected.stderr + rejected.stdout
    )

    # Generation IDs are transport-bound identifiers.
    rejected = build(
        tmp,
        request,
        archive,
        generation_id="../generation",
    )
    assert rejected.returncode != 0
    assert "invalid generation_id" in (
        rejected.stderr + rejected.stdout
    )

    # Transport may never grow retry/cost/authority policy.
    policy = json.loads(TRANSPORT.read_text(encoding="utf-8"))
    policy["max_attempts"] = 4
    rejected = build(tmp, request, archive, transport_payload=policy)
    assert rejected.returncode != 0
    assert "retry ceiling" in (rejected.stderr + rejected.stdout)

    policy = json.loads(TRANSPORT.read_text(encoding="utf-8"))
    policy["force_push_forbidden"] = False
    rejected = build(tmp, request, archive, transport_payload=policy)
    assert rejected.returncode != 0
    assert "safety drift" in (rejected.stderr + rejected.stdout)

    policy = json.loads(TRANSPORT.read_text(encoding="utf-8"))
    policy["dispatcher_secret_job_executes_candidate"] = True
    rejected = build(tmp, request, archive, transport_payload=policy)
    assert rejected.returncode != 0
    assert "safety drift" in (rejected.stderr + rejected.stdout)

    policy = json.loads(TRANSPORT.read_text(encoding="utf-8"))
    policy["source_archive_max_bytes"] = 8
    rejected = build(tmp, request, archive, transport_payload=policy)
    assert rejected.returncode != 0
    assert "source archive exceeds" in (rejected.stderr + rejected.stdout)

print("CACE async transport packet guardrails: PASS")
