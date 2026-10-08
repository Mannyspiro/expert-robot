#!/usr/bin/env python3
"""Tests for Avrea's independent 1,500-minute half-month budgets."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "avrea_budget", ROOT / "scripts" / "check_avrea_halfmonth_budget.py"
)
budget = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(budget)

policy = json.loads((ROOT / "config" / "avrea_half_month_budget.json").read_text())
phx = ZoneInfo("America/Phoenix")

def date(day, month=10, year=2026):
    return datetime(year, month, day, 12, 0, tzinfo=phx)

assert budget.budget_window(date(1), policy)["id"] == "first_half"
assert budget.budget_window(date(15), policy)["id"] == "first_half"
assert budget.budget_window(date(16), policy)["id"] == "second_half"
assert budget.budget_window(date(31), policy)["id"] == "second_half"
assert budget.budget_window(date(28, month=2, year=2027), policy)["last_day"] == 28
assert budget.budget_window(date(29, month=2, year=2028), policy)["last_day"] == 29
assert budget.budget_window(date(31, month=12), policy)["end"].year == 2027
assert budget.assess(1490, 10, policy, date(15))["allowed"] is True
assert budget.assess(1490, 11, policy, date(15))["allowed"] is False
assert budget.assess(1499, 2, policy, date(16))["allowed"] is False
assert budget.assess(0, 1500, policy, date(16))["allowed"] is True
assert budget.assess(0, 1501, policy, date(1))["allowed"] is False
assert budget.assess(1490, 10, policy, date(16))["remaining_after_reservation"] == 0
assert policy["non_transferable"] is True
assert policy["monthly_max_minutes"] == 3000
assert policy["runner_weights"]["avrea-ubuntu-latest-8-vcpu"] == 4
assert policy["runner_weights"]["avrea-ubuntu-latest-32-vcpu"] == 16
assert policy["fail_closed_on_usage_error"] is True

# Count active jobs at the full reserved max; not just elapsed time.
period = budget.budget_window(date(14), policy)
run = {"id": 12, "path": ".github/workflows/ci.yml"}
active = {"name": "build-and-smoke", "status": "in_progress",
          "started_at": "2026-10-14T18:00:00Z", "completed_at": None}
assert budget.charge_for_job(active, run, period, policy, "", "") == 260
# A cancelled job that never started costs zero.
cancelled = {"name": "build-and-smoke", "status": "completed",
             "conclusion": "cancelled", "started_at": None, "completed_at": None}
assert budget.charge_for_job(cancelled, run, period, policy, "", "") == 0

# The shared Avrea lock means unassigned jobs cannot spend runner minutes.
# GitHub may populate started_at with the scheduling time even without a runner.
unassigned = {"id": 101, "name": "build-and-smoke", "status": "pending",
              "started_at": "2026-10-14T18:00:00Z", "completed_at": None,
              "runner_id": None, "runner_name": None, "steps": [],
              "labels": ["avrea-ubuntu-latest-8-vcpu"]}
for state in ("queued", "pending", "waiting", "requested"):
    assert budget.charge_for_job(dict(unassigned, status=state), run, period,
                                 policy, "", "") == 0

# A rejected workflow that never acquired a runner also consumed no runtime.
not_started = dict(unassigned, status="completed", conclusion="failure",
                   completed_at="2026-10-14T18:00:00Z")
assert budget.charge_for_job(not_started, run, period, policy, "", "") == 0

# Live job 113033122335 was canceled after two hours in the shared queue.
# Its synthetic start equals creation, with no assigned runner or executed steps.
queue_cancelled = dict(unassigned, status="completed", conclusion="cancelled",
                       runner_id=0, runner_name="", created_at="2026-10-14T18:00:00Z",
                       completed_at="2026-10-14T20:02:30Z")
assert budget.charge_for_job(queue_cancelled, run, period, policy, "", "") == 0
assert budget.charge_for_job(dict(queue_cancelled, conclusion="skipped"), run,
                             period, policy, "", "") == 0
for ambiguous in (
    dict(queue_cancelled, created_at=None),
    dict(queue_cancelled, created_at="2026-10-14T17:59:59Z"),
    dict(queue_cancelled, completed_at="2026-10-14T17:59:59Z"),
    dict(queue_cancelled, conclusion="failure"),
):
    try:
        budget.charge_for_job(ambiguous, run, period, policy, "", "")
    except ValueError:
        pass
    else:
        raise AssertionError("ambiguous cancellation bypassed the budget gate")

# Cancellation after assignment or a setup step is still billable.
assert budget.charge_for_job(dict(queue_cancelled, runner_id=7, runner_name="avrea-worker"),
                             run, period, policy, "", "") == 492
assert budget.charge_for_job(dict(queue_cancelled, steps=[{"name": "Set up job"}]),
                             run, period, policy, "", "") == 492
for unknown in (
    dict(not_started, completed_at="2026-10-14T18:01:00Z"),
    dict(not_started, conclusion="success"),
):
    try:
        budget.charge_for_job(unknown, run, period, policy, "", "")
    except ValueError:
        pass
    else:
        raise AssertionError("ambiguous unassigned completion bypassed the budget gate")

# Runner assignment/step evidence remains conservative, even while queued.
assigned = dict(unassigned, runner_id=7, runner_name="avrea-worker")
assert budget.charge_for_job(assigned, run, period, policy, "", "") == 260
running = dict(unassigned, status="in_progress")
assert budget.charge_for_job(running, run, period, policy, "", "") == 260
step_evidence = dict(unassigned, steps=[{"name": "Set up job"}])
assert budget.charge_for_job(step_evidence, run, period, policy, "", "") == 260
unknown_assignment = dict(unassigned)
del unknown_assignment["runner_id"]
assert budget.charge_for_job(unknown_assignment, run, period, policy, "", "") == 260

completed = dict(assigned, status="completed", conclusion="success",
                 completed_at="2026-10-14T18:01:01Z")
assert budget.charge_for_job(completed, run, period, policy, "", "") == 8
heavy = dict(completed, labels=["avrea-ubuntu-latest-32-vcpu"])
assert budget.charge_for_job(heavy, run, period, policy, "", "") == 32

# Moving CI to GitHub must preserve older Avrea spending in the same workflow.
assert "ci.yml" in policy["avrea_workflow_files"]
assert "ci.yml" in policy["historical_avrea_workflow_files"]
hosted = dict(completed, runner_id=1000001, runner_name="GitHub Actions 1000001",
              labels=["ubuntu-latest"])
assert budget.charge_for_job(hosted, run, period, policy, "", "") == 0
assert budget.charge_for_job(dict(hosted, runner_name="unknown"), run, period,
                             policy, "", "") == 8
assert budget.charge_for_job(dict(hosted, labels=["ubuntu-latest", "avrea-ubuntu-latest-8-vcpu"]),
                             run, period, policy, "", "") == 8
assert budget.charge_for_job(completed, run, period, policy, "", "") == 8

# Unknown completed timing still blocks approval.
try:
    budget.charge_for_job(dict(completed, started_at=None), run, period,
                         policy, "", "")
except ValueError:
    pass
else:
    raise AssertionError("unknown completed runner timing incorrectly accepted")

# Account for prior rerun attempts as well as the latest attempt. Replay the
# GitHub response contract rather than making a live/API-token request.
first = dict(completed, id=201, run_attempt=1)
second = dict(completed, id=202, run_attempt=2)
attempt_run = dict(run, run_attempt=2, created_at="2026-09-25T00:00:00Z",
                   updated_at="2026-10-14T18:01:01Z", status="completed")
old_run = dict(run, id=99, status="completed", updated_at="2026-09-29T00:00:00Z")
calls = []
def fake_pages(url, token, key, **kwargs):
    calls.append(url)
    if key == "workflow_runs":
        assert "created=" not in url, "current-period rerun of an old run was omitted"
        return [attempt_run, old_run]
    assert "/runs/99/" not in url, "completed prior-period run should not need job queries"
    assert "filter=all" in url, "earlier rerun runtime was omitted"
    return [first, second]
with patch.object(budget, "list_pages", side_effect=fake_pages):
    used, count = budget.usage_from_github(policy, date(14), "test/repo", "fixture", "", "")
assert used == 16 and count == 1

print("Avrea half-month budget: PASS")

