#!/usr/bin/env python3
"""Prevent Avrea workflows from bypassing the 1,500-minute half-month gate."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
policy = json.loads((ROOT / "config/avrea_half_month_budget.json").read_text())
registered = set(policy["avrea_workflow_files"])
actual = set()
failures = []

for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
    txt = path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^jobs:\s*$", txt)
    if not match:
        continue
    jobs = re.split(r"(?m)(?=^  [A-Za-z][\w-]*:\s*$)", txt[match.end():])
    avrea_jobs = []
    for job in jobs:
        if not re.search(r"(?m)^    runs-on:[^\n]*avrea[^\n]*$", job):
            continue
        avrea_jobs.append(job)
        if "Enforce Avrea half-month budget" not in job:
            failures.append(f"{path.name}: Avrea job missing budget gate")
        if "group: expert-robot-avrea-half-month-slot" not in job:
            failures.append(f"{path.name}: Avrea job missing shared concurrency lock")
        if not re.search(r"(?m)^    timeout-minutes:\s*\d+", job):
            failures.append(f"{path.name}: Avrea job missing upper time limit")
        if "--reserve-minutes " not in job:
            failures.append(f"{path.name}: Avrea job missing timeout reservation")
    if avrea_jobs:
        actual.add(path.name)
        if not re.search(r"(?m)^  actions: read\s*$", txt[:match.start()]):
            failures.append(f"{path.name}: missing Actions read permission")

if actual != registered:
    failures.append(
        f"Avrea workflows differ from metering allowlist: "
        f"missing={sorted(actual-registered)} stale={sorted(registered-actual)}"
    )
assert policy["periods"][0]["budget_minutes"] == 1500
assert policy["periods"][1]["budget_minutes"] == 1500
assert policy["non_transferable"] is True
assert policy["fail_closed_on_usage_error"] is True

if failures:
    raise SystemExit("\n".join(failures))
print(f"Avrea workflow half-month guardrails: PASS ({len(actual)} workflow files)")
