#!/usr/bin/env python3
"""Only obsolete, unassigned PR-47 research jobs may be cancelled."""
import copy
import importlib.util
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("queue", ROOT / "scripts/prune_research_ci_queue.py")
queue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(queue)
head = "a" * 40
old = "b" * 40
pr = {"number": 47, "state": "open", "head": {"ref": queue.BRANCH, "sha": head,
      "repo": {"full_name": queue.REPOSITORY}},
      "base": {"repo": {"full_name": queue.REPOSITORY}}}
run = {"id": 100, "head_branch": queue.BRANCH, "head_sha": old,
       "event": "pull_request", "status": "pending",
       "path": ".github/workflows/cace-contract-extract.yml",
       "repository": {"full_name": queue.REPOSITORY},
       "pull_requests": [{"number": 47}]}
job = {"status": "pending", "runner_id": None, "runner_name": None,
       "steps": [], "started_at": "2026-10-07T22:00:00Z", "completed_at": None}
assert queue.candidate(run, head, 200)
assert queue.unassigned([job])
for change in ({"head_sha": head}, {"head_branch": "main"}, {"status": "in_progress"},
               {"event": "push"}, {"pull_requests": [{"number": 48}]},
               {"path": ".github/workflows/collared-rsi-generation.yml"},
               {"repository": {"full_name": "other/repo"}}, {"head_sha": "unknown"}):
    assert not queue.candidate(dict(run, **change), head, 200), change
assert not queue.candidate(run, head, 100)
assert not queue.unassigned([])
for change in ({"runner_id": 3}, {"runner_name": "runner"},
               {"steps": [{"name": "Set up job"}]}, {"status": "in_progress"},
               {"completed_at": "2026-10-07T22:00:01Z"}):
    assert not queue.unassigned([dict(job, **change)]), change
missing = dict(job)
del missing["runner_id"]
assert not queue.unassigned([missing])
queue.check_head(pr, head)
for change in ({"state": "closed"}, {"number": 48}):
    try:
        queue.check_head(dict(pr, **change), head)
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe PR context accepted")

calls = []
def api(path, token, method="GET"):
    calls.append((method, path))
    if path == "pulls/47":
        return copy.deepcopy(pr)
    if path == "actions/runs/100":
        return copy.deepcopy(run)
    if path.startswith("actions/runs/100/jobs"):
        return {"total_count": 1, "jobs": [copy.deepcopy(job)]}
    if path == "actions/runs/100/cancel" and method == "POST":
        return {}
    raise AssertionError(path)
with patch.object(queue, "api", side_effect=api):
    result = queue.cancel_one(run, head, 200, "fixture", apply=False)
assert result["status"] == "would_cancel"
assert all(method == "GET" for method, _ in calls)
calls.clear()
with patch.object(queue, "api", side_effect=api):
    result = queue.cancel_one(run, head, 200, "fixture", apply=True)
assert result["status"] == "cancel_requested"
assert calls[-1] == ("POST", "actions/runs/100/cancel")
assert sum(method == "POST" for method, _ in calls) == 1

# A head that changes after planning must stop all cancellation.
moved = copy.deepcopy(pr)
moved["head"]["sha"] = "c" * 40
with patch.object(queue, "api", return_value=moved):
    try:
        queue.cancel_one(run, head, 200, "fixture", apply=True)
    except ValueError:
        pass
    else:
        raise AssertionError("moving branch was not detected")

# Re-check assignment at action time; a job that started is preserved.
def assigned_api(path, token, method="GET"):
    if path.startswith("actions/runs/100/jobs"):
        return {"total_count": 1, "jobs": [dict(job, runner_id=7)]}
    return api(path, token, method)
calls.clear()
with patch.object(queue, "api", side_effect=assigned_api):
    assert queue.cancel_one(run, head, 200, "fixture", apply=True)["status"] == "preserved"
assert all(method == "GET" for method, _ in calls)

# A scheduler conflict is reported without a force-cancel fallback.
def conflict_api(path, token, method="GET"):
    if method == "POST":
        calls.append((method, path))
        raise urllib.error.HTTPError("fixture", 409, "conflict", {}, None)
    return api(path, token, method)
calls.clear()
with patch.object(queue, "api", side_effect=conflict_api):
    assert queue.cancel_one(run, head, 200, "fixture", apply=True)["status"] == "preserved_conflict"
assert [path for method, path in calls if method == "POST"] == ["actions/runs/100/cancel"]

# Pagination must not silently turn a partial inventory into a cleanup plan.
with patch.object(queue, "api", return_value={"total_count": 1001, "workflow_runs": []}):
    try:
        queue.list_runs("fixture")
    except ValueError:
        pass
    else:
        raise AssertionError("oversized queue inventory accepted")
print("research CI queue scope, dry-run and branch/runner race checks: PASS")
