#!/usr/bin/env python3
import json
import re
import sys
import subprocess
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    if len(sys.argv) != 3:
        fail("usage: validate_cace_return.py <envelope> <branch>")

    envelope_path = Path(sys.argv[1])
    branch = sys.argv[2]
    payload = json.loads(envelope_path.read_text(encoding="utf-8"))

    required = {
        "schema_version",
        "request_id",
        "status",
        "expert_robot_commit",
        "base_branch",
        "source_branch",
        "evidence_dir",
        "authority",
        "promotion_authority",
        "monetary_cost",
    }
    missing = sorted(required - payload.keys())
    if missing:
        fail("missing return fields: " + ", ".join(missing))

    if payload["schema_version"] != 1:
        fail("unsupported return schema")
    if payload["status"] != "pass":
        fail("only passed qualification may open a return PR")
    if payload["authority"] != "qualification-only":
        fail("invalid return authority")
    if payload["promotion_authority"] is not False:
        fail("external return may never carry promotion authority")
    if payload["monetary_cost"] != "free":
        fail("return evidence must come from a zero-spend lane")

    if not branch.startswith("cace-return/"):
        fail("unexpected branch namespace")

    if payload["source_branch"] != payload["base_branch"]:
        fail("return base/source branch mismatch")

    source_sha = payload["expert_robot_commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        fail("invalid source commit")

    base_branch = payload["base_branch"]
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", base_branch):
        fail("invalid base branch")
    if base_branch.startswith("cace-return/"):
        fail("return branch cannot be its own base")

    request_id = payload["request_id"]
    if not re.fullmatch(r"[A-Za-z0-9._-]+", request_id):
        fail("invalid request id")

    expected_evidence_dir = f".cace/evidence/{request_id}"
    if payload["evidence_dir"] != expected_evidence_dir:
        fail("invalid evidence directory")

    # The evidence must be the only new commit on the exact qualified source.
    # An ancestor check alone accepts a moved branch or unrelated intervening code.
    repo = envelope_path.resolve().parent
    try:
        source_type = subprocess.check_output(
            ["git", "-C", str(repo), "cat-file", "-t", source_sha], text=True).strip()
        lineage = subprocess.check_output(
            ["git", "-C", str(repo), "rev-list", "--parents", "-n", "1", "HEAD"], text=True).split()
    except subprocess.CalledProcessError:
        fail("return source commit is unavailable")
    if source_type != "commit":
        fail("return source is not a commit")
    if len(lineage) != 2 or lineage[1] != source_sha:
        fail("return evidence commit must have exactly one parent equal to source SHA")

    normalized = {
        "request_id": request_id,
        "source_sha": source_sha,
        "base_branch": base_branch,
        "evidence_dir": expected_evidence_dir,
    }
    print(json.dumps(normalized, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
