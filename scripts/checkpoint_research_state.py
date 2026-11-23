#!/usr/bin/env python3
"""Record source-bound research status on a runner without creating commits.

Artifacts are resumable records, not certificates or instruction authority.
Only fixed repository metadata and an optional bounded queue report are saved;
no environment dump, access tokens, SSH keys, cookies or browser profiles.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from prune_research_ci_queue import api, REPOSITORY

ROOT = Path(__file__).resolve().parents[1]

def write_checkpoint(destination, head, run_id, outcome, runs, queue_report=None):
    if not re.fullmatch(r"[0-9a-f]{40}", head) or not str(run_id).isdigit():
        raise ValueError("invalid source or run identity")
    if destination.is_symlink():
        raise ValueError("checkpoint destination must not be a symlink")
    destination.mkdir(parents=True, exist_ok=True)
    policy = json.loads((ROOT / "config/research_session_policy.json").read_text())
    now = datetime.now(timezone.utc)
    state = {
        "schema_version": 1, "repository": REPOSITORY,
        "source_commit": head, "producer_run_id": str(run_id),
        "execution_commit": os.environ.get("GITHUB_SHA"),
        "trigger_event": os.environ.get("GITHUB_EVENT_NAME"),
        "timestamp_utc": now.isoformat(),
        "local_date": now.astimezone(ZoneInfo(policy["timezone"])).date().isoformat(),
        "step_outcome": outcome[:40], "session_policy": policy,
        "validation_runs": [{k: r.get(k) for k in
            ("id", "name", "head_sha", "status", "conclusion", "html_url")}
            for r in runs[:100]],
        "queue_maintenance": queue_report,
        "evidence_role": "runner_checkpoint_not_qualification_certificate",
        "promotion_authority": False,
    }
    payload = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode()
    if len(payload) > 256 * 1024:
        raise ValueError("checkpoint exceeds bounded size")
    target = destination / "research-checkpoint.json"
    if target.is_symlink():
        raise ValueError("checkpoint file must not be a symlink")
    target.write_bytes(payload)
    manifest = {"schema_version": 1, "source_commit": head,
                "producer_run_id": str(run_id), "files": [{
                    "path": target.name, "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest()}]}
    manifest_path = destination / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("checkpoint manifest must not be a symlink")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--outcome", default="unknown")
    parser.add_argument("--queue-report", type=Path)
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN")
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or not token:
        raise ValueError("checkpoint requires the repository-scoped token")
    query = urllib.parse.urlencode({"head_sha": args.head_sha, "per_page": 100})
    response = api("actions/runs?" + query, token)
    if response["total_count"] > 100:
        raise ValueError("current-head workflow inventory exceeds checkpoint bound")
    queue_report = None
    if args.queue_report and args.queue_report.exists():
        if args.queue_report.is_symlink() or args.queue_report.stat().st_size > 128 * 1024:
            raise ValueError("queue report outside bound")
        queue_report = json.loads(args.queue_report.read_text())
    manifest = write_checkpoint(args.state_dir, args.head_sha,
                                os.environ.get("GITHUB_RUN_ID", ""), args.outcome,
                                response["workflow_runs"], queue_report)
    print(json.dumps({"checkpoint_manifest": manifest}))

if __name__ == "__main__":
    main()
