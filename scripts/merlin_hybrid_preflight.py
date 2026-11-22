#!/usr/bin/env python3
"""Exact-source, fail-closed source inventory for non-deploying Merlin CI.

This is an integrity gate, not a review of model behavior or release authority.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys

REQUIRED = (
    "CMakeLists.txt",
    "portable/merlin_studio/engine.py",
    "portable/merlin_studio/model.py",
    "portable/merlin_studio/tools.py",
    "portable/merlin_studio/server.py",
    "portable/merlin_studio/web/index.html",
    "portable/merlin_studio/tests/test_studio.py",
    "python/merlin/browser_policy.py",
    "python/merlin/browser_egress.py",
    "python/merlin/public_browser.py",
    "python/merlin/browser_service.py",
    "python/merlin/browser_client.py",
    "python/merlin/browser_ingest.py",
    "python/merlin/browser_research_handoff.py",
    "python/merlin_release_gate.py",
    "tests/test_merlin_release_gate.py",
    "tests/test_merlin_studio_tool_compatibility.py",
    "tests/test_merlin_bundled_model_launcher.py",
    "portable/build_offline_profile.py",
    "scripts/verify_offline_profile.py",
    "tests/test_merlin_offline_profile.py",
    "tests/test_public_browser.py",
    "tests/test_browser_research_handoff.py",
    "scripts/run_merlin_offline_ci.sh",
    "scripts/merlin_public_https_acceptance.py",
    "scripts/merlin_cited_research_cycle.py",
    "tests/test_merlin_public_primary_sources.py",
    "portable/merlin_studio/browser_bridge.py",
)

def insist(ok, reason):
    if not ok:
        raise ValueError(reason)

def source_preflight(root: Path, expected_sha: str):
    insist(re.fullmatch(r"[0-9a-f]{40}", expected_sha) is not None,
           "exact lowercase Git SHA-1 commit required")
    root = root.resolve(strict=True)
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True, timeout=15).stdout.strip()
    insist(head == expected_sha, "checked-out source revision differs")
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain",
                            "--untracked-files=no"],
                           check=True, capture_output=True, text=True, timeout=15).stdout
    insist(not dirty, "tracked source differs from checked-out commit")
    files = []
    for rel in REQUIRED:
        target = root
        for part in Path(rel).parts:
            target /= part
            insist(not target.is_symlink(), "symlink in required source path: " + rel)
        insist(target.is_file(), "missing required source: " + rel)
        mode = target.stat().st_mode
        insist(stat.S_ISREG(mode), "non-regular source: " + rel)
        data = target.read_bytes()
        insist(0 < len(data) <= 512 * 1024, "unexpected source byte size: " + rel)
        files.append({"path": rel, "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest()})
    return {"schema": "merlin-integrated-offline-source-preflight/1",
            "status": "passed", "source_commit": head,
            "files_verified": len(files), "file_pins": files,
            "model_calls": 0, "host_mutations": 0, "production_qualified": False}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = source_preflight(args.root, args.expected_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "files_verified": result["files_verified"],
                      "source_commit": result["source_commit"], "production_qualified": False}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
