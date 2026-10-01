#!/usr/bin/env python3
"""Validate that a candidate changes capability code only, never authority/verifier infrastructure."""

import argparse
import fnmatch
import json
import subprocess
from pathlib import Path


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("repo", type=Path)
    p.add_argument("--base-sha", required=True)
    p.add_argument("--candidate-sha", required=True)
    p.add_argument("--policy", type=Path, default=Path("config/auto_promotion_scope.json"))
    p.add_argument("--output", type=Path)
    args = p.parse_args()

    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    repo = args.repo.resolve()

    subprocess.run(["git","-C",str(repo),"merge-base","--is-ancestor",args.base_sha,args.candidate_sha], check=True)
    changed = git(repo, "diff", "--name-only", f"{args.base_sha}...{args.candidate_sha}").splitlines()
    stat = git(repo, "diff", "--numstat", f"{args.base_sha}...{args.candidate_sha}").splitlines()

    total_lines = 0
    for row in stat:
        parts = row.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            total_lines += int(parts[0]) + int(parts[1])

    failures = []
    if not changed:
        failures.append("candidate has no changes")
    if len(changed) > int(policy["max_changed_files"]):
        failures.append("too many changed files")
    if total_lines > int(policy["max_total_changed_lines"]):
        failures.append("too many changed lines")

    for path in changed:
        if any(path == prefix or path.startswith(prefix) for prefix in policy["forbidden_prefixes"]):
            failures.append(f"authority/verifier path is forbidden: {path}")
            continue
        if not any(fnmatch.fnmatch(path, pattern) for pattern in policy["allowed_globs"]):
            failures.append(f"path is outside automatic capability scope: {path}")

    result = {
        "schema_version":1,
        "base_sha":args.base_sha,
        "candidate_sha":args.candidate_sha,
        "changed_files":changed,
        "changed_file_count":len(changed),
        "changed_lines":total_lines,
        "authority_change":"same" if not failures else "unverified",
        "scope_allowed":not failures,
        "failures":failures,
    }
    rendered=json.dumps(result,indent=2)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(rendered,encoding="utf-8")
    print(rendered,end="")
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
