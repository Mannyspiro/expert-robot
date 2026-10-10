#!/usr/bin/env python3
"""Fail-closed Avrea half-month minute gate for Expert Robot GitHub Actions.

Period boundaries: America/Phoenix, days 1-15 and 16-end, separate 1500-min caps.
Completed jobs count rounded-up job wall-clock minutes. Assigned/active jobs
reserve full workflow worst-case minutes; proven unassigned queue entries do not.
All rerun attempts count. All jobs within Avrea-using workflow files count
conservatively; non-Avrea jobs in mixed workflows may overcount (never undercount).
This is repository-scoped accounting, NOT an Avrea-provider billing API.
"""

from __future__ import annotations

import argparse
import calendar
import json
import math
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


def budget_window(now, policy):
    local = now.astimezone(ZoneInfo(policy["timezone"]))
    first = local.day <= 15
    start_day = 1 if first else 16
    end_day = 15 if first else calendar.monthrange(local.year, local.month)[1]
    start = local.replace(day=start_day, hour=0, minute=0, second=0, microsecond=0)
    if first:
        end = local.replace(day=16, hour=0, minute=0, second=0, microsecond=0)
    elif local.month == 12:
        end = local.replace(year=local.year + 1, month=1, day=1, hour=0,
                            minute=0, second=0, microsecond=0)
    else:
        end = local.replace(month=local.month + 1, day=1, hour=0,
                            minute=0, second=0, microsecond=0)
    selected = policy["periods"][0 if first else 1]
    if int(selected["budget_minutes"]) != 1500 or not policy["non_transferable"]:
        raise ValueError("unapproved Avrea period budget or transfer policy")
    return {
        "id": "first_half" if first else "second_half",
        "start": start.astimezone(timezone.utc),
        "end": end.astimezone(timezone.utc),
        "last_day": end_day,
        "budget": int(selected["budget_minutes"]),
    }


def assess(used_minutes, requested_minutes, policy, now):
    period = budget_window(now, policy)
    if requested_minutes <= 0 or used_minutes < 0:
        raise ValueError("minutes must be positive and usage nonnegative")
    allowed = used_minutes + requested_minutes <= period["budget"]
    return {
        "allowed": allowed,
        "period": period["id"],
        "local_month": now.astimezone(ZoneInfo(policy["timezone"])).strftime("%Y-%m"),
        "limit_minutes": period["budget"],
        "used_or_reserved_minutes": used_minutes,
        "requested_reserved_minutes": requested_minutes,
        "remaining_after_reservation": period["budget"] - used_minutes - requested_minutes,
        "no_cross_period_borrowing": True,
    }


def parse_stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def charge_for_job(job, run, period, policy, current_run_id, current_job):
    # These workflows retain their historical Avrea entries after migration.
    # Exclude only positively identified GitHub-hosted jobs, never an unknown
    # runner or an Avrea/self-hosted label that happens to resemble a host name.
    labels = set(job.get("labels") or [])
    if (labels and labels <= {"ubuntu-latest", "ubuntu-24.04", "ubuntu-22.04"} and
        type(job.get("runner_id")) is int and job["runner_id"] > 0 and
        (job.get("runner_name") or "").startswith("GitHub Actions ")):
        return 0
    if str(run["id"]) == str(current_run_id) and job.get("status") == "in_progress":
        # The just-started job is charged by --reserve-minutes instead.
        # Serial Avrea concurrency ensures no other Avrea job runs alongside it.
        if job.get("name") == current_job:
            return 0
    state = job.get("status", "")
    # A GitHub scheduling timestamp alone is not evidence of runner runtime.
    # Require explicit, complete assignment metadata before treating a queue
    # entry as unstarted; missing fields remain conservatively reserved.
    unassigned = (
        {"runner_id", "runner_name", "steps"}.issubset(job) and
        job["runner_id"] in (None, 0) and
        job["runner_name"] in (None, "") and job["steps"] == []
    )
    if unassigned and state in ("queued", "pending", "waiting", "requested"):
        return 0
    # GitHub-hosted jobs that never received any runner and executed no steps
    # cannot consume Avrea time, regardless of GitHub's synthetic timestamps.
    # This exception NEVER applies to Avrea labels or unknown/mixed labels.
    github_labels = {"ubuntu-latest", "ubuntu-24.04", "ubuntu-22.04"}
    github_only = bool(labels) and labels <= github_labels
    if unassigned and github_only and state == "completed" and job.get("conclusion") in (
        "failure", "startup_failure", "cancelled", "skipped"
    ):
        return 0
    if unassigned and state == "completed":
        # GitHub may report a skipped, never-assigned job with a completion
        # timestamp preceding its synthetic start timestamp by a second.
        # A skipped job with no runner and zero steps executes no workload.
        if job.get("conclusion") == "skipped":
            return 0
        if job.get("conclusion") in ("cancelled", "skipped", "failure", "startup_failure"):
            started = parse_stamp(job.get("started_at"))
            finished = parse_stamp(job.get("completed_at"))
            if started is None or (finished is not None and started == finished):
                return 0
            # Queue cancellation keeps the synthetic scheduling start. A live
            # GitHub job can wait for hours with started_at == created_at while
            # runner_id/name remain empty and no steps ever execute. Recognize
            # only that exact cancelled/skipped lifecycle, not failed startup.
            if job.get("conclusion") in ("cancelled", "skipped"):
                created = parse_stamp(job.get("created_at"))
                if created == started and finished is not None and finished >= started:
                    return 0
            raise ValueError("unassigned completed job has ambiguous execution timing")
        raise ValueError("completed job lacks runner/step execution evidence")
    started = parse_stamp(job.get("started_at"))
    finished = parse_stamp(job.get("completed_at"))
    if finished and finished <= period["start"]:
        return 0
    if started and started >= period["end"]:
        return 0
    if not started and state == "completed":
        # Unstarted cancelled/skipped jobs consumed no runner time.
        if job.get("conclusion") in ("cancelled", "skipped"):
            return 0
        # Unknown completed job timing: block, do not silently undercount.
        raise ValueError("completed job missing start timestamp")
    if started and finished:
        seconds = max(0, (min(finished, period["end"]) -
                          max(started, period["start"])).total_seconds())
        minutes = max(1, math.ceil(seconds / 60.0)) if seconds > 0 else 0
    else:
        basename = run.get("path", "").split("/")[-1].split("@")[0]
        minutes = policy["estimated_max_run_minutes"].get(basename)
        if minutes is None:
            raise ValueError("unbudgeted active workflow " + basename)
    runner = (job.get("runner_name") or "").lower()
    labels = " ".join(str(x) for x in (job.get("labels") or [])).lower()
    runner_details = runner + " " + labels
    basename = run.get("path", "").split("/")[-1].split("@")[0]
    heavy = ("32-vcpu" in runner_details or basename == "heavy-qualification.yml" or
             (basename == "math-benchmark.yml" and "8-vcpu" not in runner_details))
    return minutes * (16 if heavy else 4)


def request_json(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "expert-robot-half-month-budget",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def list_pages(url, token, key, max_pages=30):
    out = []
    for page in range(1, max_pages + 1):
        sep = "&" if "?" in url else "?"
        response = request_json(url + sep + "per_page=100&page=" + str(page), token)
        batch = response[key]
        out.extend(batch)
        if len(batch) < 100:
            return out
    raise RuntimeError("usage enumeration exceeded pagination limit: refusing budget approval")


def usage_from_github(policy, now, repo, token, current_run_id, current_job):
    period = budget_window(now, policy)
    base = f"https://api.github.com/repos/{repo}/actions/runs"
    # A run created before this period can be rerun or leave the queue during
    # it. Filtering by created_at silently omits that consumption. Scan bounded
    # run metadata, then skip only completed runs last updated before the period.
    runs = list_pages(base, token, "workflow_runs", max_pages=100)
    allowed_workflows = set(policy["avrea_workflow_files"])
    used = 0
    counted = 0
    for run in runs:
        basename = run.get("path", "").split("/")[-1].split("@")[0]
        if basename not in allowed_workflows:
            continue
        updated = parse_stamp(run.get("updated_at"))
        if run.get("status") == "completed" and updated and updated <= period["start"]:
            continue
        # GitHub defaults to only the latest attempt, which would omit runtime
        # already spent by earlier attempts after a workflow is rerun.
        jobs_url = f"https://api.github.com/repos/{repo}/actions/runs/{run['id']}/jobs?filter=all"
        jobs = list_pages(jobs_url, token, "jobs", max_pages=10)
        counted += 1
        for job in jobs:
            try:
                used += charge_for_job(job, run, period, policy, current_run_id, current_job)
            except ValueError as exc:
                raise ValueError(f"run {run['id']} job {job.get('id', 'unknown')}: {exc}") from exc
    return used, counted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", type=Path,
                    default=Path("config/avrea_half_month_budget.json"))
    ap.add_argument("--reserve-minutes", type=int, required=True)
    ap.add_argument("--runner-label", type=str, required=True)
    ap.add_argument("--offline-used-minutes", type=int, default=None,
                    help="For local testing only; forbidden within GitHub Actions")
    args = ap.parse_args()
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN", "")
    try:
        if not policy["fail_closed_on_usage_error"]:
            raise ValueError("budget policy must be fail-closed")
        if args.offline_used_minutes is not None:
            if os.environ.get("GITHUB_ACTIONS") == "true":
                raise ValueError("offline usage override forbidden in GitHub Actions")
            used, count = args.offline_used_minutes, 0
        else:
            if not repo or not token:
                raise ValueError("GITHUB_REPOSITORY and GH_TOKEN required")
            used, count = usage_from_github(
                policy, now, repo, token, os.environ.get("GITHUB_RUN_ID", ""),
                os.environ.get("GITHUB_JOB", "")
            )
        weight = policy["runner_weights"].get(args.runner_label)
        if weight is None:
            raise ValueError("unknown Avrea runner label")
        result = assess(used, args.reserve_minutes * weight, policy, now)
        result["counted_workflow_runs"] = count
        result["runner_label"] = args.runner_label
        print(json.dumps(result, indent=2))
        if not result["allowed"]:
            print("::error::Avrea half-month cap would be exceeded; blocking workload.", file=sys.stderr)
            return 3
        return 0
    except Exception as exc:
        print("::error::Avrea budget check unavailable; fail closed: " + str(exc), file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())

