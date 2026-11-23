#!/usr/bin/env python3
"""Remove superseded, unassigned research validation runs for Expert Robot PR 47.

Administrative CI maintenance only. No contents writes, proof edits, runtime
promotion or RSI permissions. Default mode is read-only; --apply requests only
standard GitHub workflow cancellation after fresh scope and assignment checks.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPOSITORY = "Mannyspiro/expert-robot"
BRANCH = "research/magick-ir-v0-1"
PR_NUMBER = 47
WAITING = {"queued", "pending", "waiting", "requested"}
WORKFLOWS = {
    "ci.yml", "formal-qualification.yml", "cace-contract-extract.yml",
    "cace-fem-nd-contract-verify.yml", "cace-nd-bridge-integration.yml",
    "cace-refinement-counterexample.yml", "cace-research-interface-probe.yml",
    "circle-symmetry-benchmark.yml", "crl-symmetry-component-benchmark.yml",
}

def check_head(pr, expected_sha):
    if (pr.get("number") != PR_NUMBER or pr.get("state") != "open" or
        pr.get("head", {}).get("ref") != BRANCH or
        pr.get("head", {}).get("sha") != expected_sha or
        pr.get("head", {}).get("repo", {}).get("full_name") != REPOSITORY or
        pr.get("base", {}).get("repo", {}).get("full_name") != REPOSITORY or
        not re.fullmatch(r"[0-9a-f]{40}", expected_sha)):
        raise ValueError("PR scope/head changed; refusing CI cancellation")

def superseded_head(pr, expected_sha):
    """Only a valid newer SHA on the same open PR permits an audited no-op."""
    current = pr.get("head", {}).get("sha")
    return (
        pr.get("number") == PR_NUMBER and pr.get("state") == "open"
        and pr.get("head", {}).get("ref") == BRANCH
        and pr.get("head", {}).get("repo", {}).get("full_name") == REPOSITORY
        and pr.get("base", {}).get("repo", {}).get("full_name") == REPOSITORY
        and isinstance(current, str)
        and bool(re.fullmatch(r"[0-9a-f]{40}", current))
        and bool(re.fullmatch(r"[0-9a-f]{40}", expected_sha))
        and current != expected_sha
    )


def candidate(run, head, own_run_id):
    rid = run.get("id")
    return (
        type(rid) is int and rid > 0 and str(rid) != str(own_run_id) and
        run.get("head_branch") == BRANCH and run.get("head_sha") != head and
        bool(re.fullmatch(r"[0-9a-f]{40}", str(run.get("head_sha", "")))) and
        run.get("event") == "pull_request" and run.get("status") in WAITING and
        run.get("repository", {}).get("full_name") == REPOSITORY and
        any(p.get("number") == PR_NUMBER for p in run.get("pull_requests", [])) and
        run.get("path") in {".github/workflows/" + p for p in WORKFLOWS}
    )

def unassigned(jobs):
    return bool(jobs) and all(
        {"runner_id", "runner_name", "steps", "completed_at"}.issubset(j) and
        j.get("status") in WAITING and j["runner_id"] in (None, 0) and
        j["runner_name"] in (None, "") and j["steps"] == [] and
        j["completed_at"] is None for j in jobs
    )

def api(path, token, method="GET"):
    # Paths are constructed here from fixed scope and integer IDs only.
    url = "https://api.github.com/repos/" + REPOSITORY + "/" + path
    request = urllib.request.Request(url, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "expert-robot-research-queue-maintenance",
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise ValueError("CI response exceeded bound")
    return json.loads(data) if data else {}

def list_runs(token):
    runs = {}
    for state in sorted(WAITING):
        query = urllib.parse.urlencode({"branch": BRANCH, "status": state})
        for page in range(1, 11):
            response = api(f"actions/runs?{query}&per_page=100&page={page}", token)
            batch = response["workflow_runs"]
            if response["total_count"] > 1000:
                raise ValueError("CI queue exceeds bounded API search")
            for run in batch:
                runs[run["id"]] = run
            if len(batch) < 100:
                break
        else:
            raise ValueError("CI queue pagination limit reached")
    return [runs[rid] for rid in sorted(runs)]

def cancel_one(run, head, own_run_id, token, apply=False):
    check_head(api("pulls/47", token), head)
    live = api(f"actions/runs/{run['id']}", token)
    result = {"run_id": run["id"], "workflow": run["path"], "status": "preserved"}
    if not candidate(live, head, own_run_id):
        return result
    jobs = api(f"actions/runs/{run['id']}/jobs?filter=latest&per_page=100", token)
    if jobs["total_count"] != len(jobs["jobs"]) or not unassigned(jobs["jobs"]):
        return result
    if not apply:
        result["status"] = "would_cancel"
        return result
    try:
        api(f"actions/runs/{run['id']}/cancel", token, method="POST")
        result["status"] = "cancel_requested"
    except urllib.error.HTTPError as exc:
        # The run can leave the queue between the final GET and cancellation.
        # Standard cancellation only; never escalate to force-cancel.
        if exc.code != 409:
            raise
        result["status"] = "preserved_conflict"
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN")
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or not token:
        raise ValueError("maintenance requires the scoped repository token")
    live_pr = api("pulls/47", token)
    if superseded_head(live_pr, args.head_sha):
        # Stale jobs never cancel a run or change repository state.
        report = {"schema_version": 1, "repository": REPOSITORY, "pr": PR_NUMBER,
                  "preserved_head": args.head_sha, "observed_head": live_pr["head"]["sha"],
                  "status": "superseded_noop", "applied": False, "runs": [],
                  "cancel_requested_count": 0}
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "superseded_noop", "cancel_requested_count": 0}))
        return
    check_head(live_pr, args.head_sha)
    own_id = os.environ.get("GITHUB_RUN_ID", "")
    records = [cancel_one(r, args.head_sha, own_id, token, args.apply)
               for r in list_runs(token) if candidate(r, args.head_sha, own_id)]
    report = {"schema_version": 1, "repository": REPOSITORY, "pr": PR_NUMBER,
              "preserved_head": args.head_sha, "applied": args.apply,
              "runs": records, "cancel_requested_count": sum(
                  r["status"] == "cancel_requested" for r in records)}
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cancel_requested_count": report["cancel_requested_count"],
                      "preserved_head": args.head_sha, "applied": args.apply}))

if __name__ == "__main__":
    main()
