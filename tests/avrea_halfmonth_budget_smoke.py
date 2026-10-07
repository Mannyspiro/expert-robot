#!/usr/bin/env python3
"""Tests for Avrea's independent 1,500-minute half-month budgets."""

from datetime import datetime
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

print("Avrea half-month budget: PASS")
