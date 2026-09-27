#!/usr/bin/env python3
"""Asynchronous CACE capability transport. Python is orchestration only.

No candidate code is sent or executed. A receipt binds each result to its
request, Expert Robot commit, and CACE dispatch commit. No polling or retries.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid


REPOSITORY = "morganaspim/Cace-app"
REMOTE = "git@github.com:morganaspim/Cace-app.git"
SOURCE_REPOSITORY = "Mannyspiro/expert-robot"
BRANCH_PREFIX = "executor/expert-robot-v2/"
ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"[0-9a-f]{40}")
REQUEST_ID = re.compile(r"probe-[0-9a-f]{32}")
MAX_JSON_BYTES = 8192


class BridgeError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise BridgeError(message)


def decode_json(raw):
    require(len(raw.encode("utf-8")) <= MAX_JSON_BYTES, "oversized JSON")
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique_pairs)
    require(isinstance(value, dict), "expected JSON object")
    return value


def encode_json(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"


def read_json(path):
    require(path.stat().st_size <= MAX_JSON_BYTES, "oversized JSON file")
    return decode_json(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encode_json(value), encoding="utf-8")
    temporary.replace(path)


def parse_time(value):
    require(isinstance(value, str), "missing timestamp")
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(instant.tzinfo is not None, "timestamp needs timezone")
    return instant.astimezone(timezone.utc)


def check_quota(quota, owner, minutes, now=None):
    """Validate operator-recorded billing evidence; this does not query billing.

    Platform-enforced zero paid overage is required even with a fresh balance:
    other workflows can consume the remaining minutes after this check.
    """
    now = now or datetime.now(timezone.utc)
    require(quota.get("schema_version") == 1, "unsupported quota schema")
    accounts = quota.get("accounts", [])
    require(isinstance(accounts, list), "invalid quota accounts")
    matches = [item for item in accounts if isinstance(item, dict) and item.get("owner") == owner]
    require(len(matches) == 1, "missing or duplicate account quota: " + owner)
    record = matches[0]
    age = now - parse_time(record.get("checked_at"))
    require(timedelta(0) <= age <= timedelta(hours=6), "stale or future quota evidence")
    require(record.get("billing_cycle") == now.strftime("%Y-%m"), "wrong billing cycle")
    require(record.get("paid_overage_blocked") is True, "paid overage must be blocked at GitHub")
    remaining = record.get("free_linux_minutes_remaining")
    require(type(remaining) is int and remaining >= minutes, "insufficient verified free minutes")
    require(isinstance(record.get("evidence"), str) and bool(record["evidence"].strip()), "missing quota evidence")


def validate_request(request):
    require(request.get("schema_version") == 1 and request.get("kind") == "capability-probe", "unsupported request")
    require(REQUEST_ID.fullmatch(str(request.get("request_id"))) is not None, "invalid request ID")
    require(request.get("source_repository") == SOURCE_REPOSITORY, "wrong source repository")
    require(request.get("cace_repository") == REPOSITORY, "wrong CACE repository")
    for field in ("expert_robot_commit", "cace_base_commit"):
        require(SHA.fullmatch(str(request.get(field))) is not None, "invalid commit: " + field)
    parse_time(request.get("requested_at"))


def validate_receipt(receipt):
    require(receipt.get("schema_version") == 1, "unsupported receipt")
    validate_request(receipt.get("request", {}))
    require(receipt.get("branch") == BRANCH_PREFIX + receipt["request"]["request_id"], "invalid receipt branch")
    require(SHA.fullmatch(str(receipt.get("dispatch_commit"))) is not None, "invalid dispatch commit")


def validate_result(result, receipt):
    validate_receipt(receipt)
    require(result.get("schema_version") == 1 and result.get("kind") == "capability-probe", "unsupported result")
    require(result.get("request") == receipt["request"], "result/request mismatch")
    require(result.get("dispatch_commit") == receipt["dispatch_commit"], "result/dispatch mismatch")
    require(result.get("status") == "observed", "capability result was not observed")
    require(result.get("formal_verified") is False and result.get("promotion_authority") is False,
            "capability observations cannot assert proof or promotion")
    require(type(result.get("run_id")) is int and result["run_id"] > 0, "invalid CACE run ID")
    require(isinstance(result.get("capabilities"), dict), "missing capabilities")
    return result


class GitRemote:
    def __init__(self, directory, remote=REMOTE):
        self.directory = Path(directory)
        self.remote = remote
        self.git("init", "--quiet")
        self.git("remote", "add", "origin", remote)

    def git(self, *arguments, input=None):
        # Argument arrays, no shell interpolation. A failed read is not 'pending'.
        result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *arguments],
                                cwd=self.directory, input=input, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
        if result.returncode:
            raise BridgeError("git operation failed: " + arguments[0])
        return result

    def head(self):
        self.git("fetch", "--quiet", "--depth=1", "origin", "HEAD")
        return self.git("rev-parse", "FETCH_HEAD").stdout.strip()

    def fetch_branch(self, branch):
        found = self.git("ls-remote", "--heads", "origin", "refs/heads/" + branch).stdout
        if not found.strip():
            return None
        self.git("fetch", "--quiet", "--depth=1", "origin", "refs/heads/" + branch)
        return self.git("rev-parse", "FETCH_HEAD").stdout.strip()

    def file(self, commit, path):
        # ls-tree distinguishes absent result from a failed transport/read.
        entry = self.git("ls-tree", commit, "--", path).stdout.strip()
        if not entry:
            return None
        require(entry.startswith("100644 blob "), "unexpected result file mode")
        size = int(self.git("cat-file", "-s", commit + ":" + path).stdout)
        require(size <= MAX_JSON_BYTES, "oversized remote JSON")
        return decode_json(self.git("show", commit + ":" + path).stdout)

    def create_dispatch(self, request, workflow):
        # A fresh branch with only two files. Other CACE workflows cannot run
        # because they are absent from this tree. Main is never checked out.
        for path, content in (("bridge/request.json", encode_json(request)),
                              (".github/workflows/expert-robot-capability.yml", workflow)):
            blob = self.git("hash-object", "-w", "--stdin", input=content).stdout.strip()
            self.git("update-index", "--add", "--cacheinfo", "100644," + blob + "," + path)
        tree = self.git("write-tree").stdout.strip()
        return self.git("-c", "user.name=expert-robot-dispatcher", "-c", "user.email=noreply@github.com",
                        "commit-tree", tree, "-p", request["cace_base_commit"],
                        input="Inspect CACE capacity for " + request["request_id"] + "\n").stdout.strip()

    def push_new(self, commit, branch):
        # Empty lease permits branch creation only, never replacement.
        self.git("push", "--quiet", "--force-with-lease=refs/heads/" + branch + ":",
                 "origin", commit + ":refs/heads/" + branch)


def dispatch(git, source_sha, quota, receipt_path, workflow, now=None):
    require(SHA.fullmatch(source_sha) is not None, "source must be a full commit SHA")
    if receipt_path.exists():
        receipt = read_json(receipt_path)
        validate_receipt(receipt)
        require(receipt["request"]["expert_robot_commit"] == source_sha, "receipt belongs to another source")
        head = git.fetch_branch(receipt["branch"])
        require(head is not None, "receipt exists but remote branch is absent; inspect before retrying")
        require(git.file(head, "bridge/request.json") == receipt["request"], "existing request changed")
        return receipt  # Identical retries never dispatch another job.
    check_quota(quota, "morganaspim", 3, now)
    request = {
        "schema_version": 1, "kind": "capability-probe",
        "request_id": "probe-" + uuid.uuid4().hex,
        "source_repository": SOURCE_REPOSITORY, "expert_robot_commit": source_sha,
        "cace_repository": REPOSITORY, "cace_base_commit": git.head(),
        "requested_at": (now or datetime.now(timezone.utc)).isoformat(),
    }
    validate_request(request)
    commit = git.create_dispatch(request, workflow)
    receipt = {"schema_version": 1, "request": request,
               "branch": BRANCH_PREFIX + request["request_id"], "dispatch_commit": commit}
    # Save before pushing so an interrupted response cannot lose the request ID.
    write_json(receipt_path, receipt)
    git.push_new(commit, receipt["branch"])
    return receipt


def collect(git, receipt):
    validate_receipt(receipt)
    head = git.fetch_branch(receipt["branch"])
    require(head is not None, "CACE request branch is missing")
    require(git.file(head, "bridge/request.json") == receipt["request"], "remote request changed")
    result = git.file(head, "bridge/result.json")
    if result is None:
        # Missing, queued, cancelled, or publisher-disabled are all unverified.
        return {"status": "pending", "formal_verified": False,
                "request_id": receipt["request"]["request_id"]}
    return validate_result(result, receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-quota")
    check.add_argument("--quota", type=Path, required=True)
    check.add_argument("--owner", choices=["Mannyspiro", "morganaspim"], required=True)
    check.add_argument("--minutes", type=int, default=3)
    send = commands.add_parser("dispatch")
    send.add_argument("--source-sha", required=True)
    send.add_argument("--quota", type=Path, required=True)
    send.add_argument("--receipt", type=Path, required=True)
    receive = commands.add_parser("collect")
    receive.add_argument("--receipt", type=Path, required=True)
    receive.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "check-quota":
            require(args.minutes >= 1, "invalid reservation")
            check_quota(read_json(args.quota), args.owner, args.minutes)
            print("quota evidence accepted; platform zero-overage enforcement remains required")
            return 0
        with tempfile.TemporaryDirectory(prefix="expert-robot-cace-") as directory:
            git = GitRemote(directory)
            if args.command == "dispatch":
                # On Actions, the transport owner needs a separate reservation.
                quota = read_json(args.quota)
                if os.environ.get("GITHUB_ACTIONS") == "true":
                    check_quota(quota, "Mannyspiro", 3)
                result = dispatch(git, args.source_sha, quota, args.receipt,
                                  (ROOT / "ops/cace/capability-probe.yml").read_text())
                print(encode_json(result))
            else:
                result = collect(git, read_json(args.receipt))
                write_json(args.output, result)
                print(encode_json(result))
                return 2 if result["status"] == "pending" else 0
        return 0
    except (BridgeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("CACE bridge stopped: " + str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
