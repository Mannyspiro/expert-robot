#!/usr/bin/env python3
"""Regression cases for push races, replayed collar evidence and manual sources."""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rsi_source", ROOT / "scripts/resolve_rsi_source.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

source_sha = "a" * 40
moved_sha = "b" * 40
evidence = {"source_run_id": 123, "candidate_sha": source_sha}
run = {"id": 123, "path": ".github/workflows/collared-rsi-generation.yml",
       "status": "completed", "conclusion": "success", "event": "push",
       "head_repository": {"full_name": "owner/expert-robot"},
       "head_branch": "candidate/test", "head_sha": source_sha}
options = {"repository": "owner/expert-robot", "candidate_ref": "candidate/test",
           "source_run_id": 123, "event_name": "workflow_run",
           "trusted_branch": "main", "trusted_sha": moved_sha,
           "event_source_sha": source_sha}


def rejects(artifact=evidence, metadata=run, **changes):
    try:
        module.resolve_source(artifact, metadata, **(options | changes))
    except ValueError:
        return
    raise AssertionError("incorrect source binding accepted")


assert module.resolve_source(evidence, run, **options)["candidate_sha"] == source_sha
# A newer checkout accidentally produced by an old push run must be rejected.
rejects(evidence | {"candidate_sha": moved_sha})
rejects(evidence | {"source_run_id": 124})
rejects(evidence | {"source_run_id": True})
rejects(metadata=run | {"id": 124})
rejects(metadata=run | {"head_sha": moved_sha})
rejects(event_source_sha=moved_sha)
rejects(metadata=run | {"head_branch": "candidate/other"})
rejects(metadata=run | {"path": ".github/workflows/untrusted.yml"})
rejects(metadata=run | {"conclusion": "failure"})
rejects(metadata=run | {"status": "in_progress"})
rejects(metadata=run | {"head_repository": {"full_name": "fork/expert-robot"}})
rejects(metadata=run | {"event": "pull_request"})

# Manual collar dispatch on trusted main has a different dispatcher commit.
manual = run | {"event": "workflow_dispatch", "head_branch": "main", "head_sha": moved_sha}
manual_options = options | {"event_name": "workflow_dispatch", "event_source_sha": "",
                            "resolved_candidate_sha": source_sha}
assert module.resolve_source(evidence, manual, **manual_options)["candidate_sha"] == source_sha
# Another branch can use the same workflow path and fabricate an artifact for a
# scope-clean candidate. Neither a matching path nor candidate SHA makes it trusted.
rejects(metadata=manual | {"head_branch": "untrusted/forged-collar-workflow", "head_sha": "f" * 40},
        event_name="workflow_dispatch", event_source_sha="", resolved_candidate_sha=source_sha)
rejects(metadata=manual | {"head_branch": "untrusted/forged-collar-workflow"},
        event_name="workflow_dispatch", event_source_sha="", resolved_candidate_sha=source_sha)
rejects(metadata=manual | {"head_sha": "f" * 40}, event_name="workflow_dispatch",
        event_source_sha="", resolved_candidate_sha=source_sha)
rejects(metadata=manual, event_name="workflow_dispatch", event_source_sha="",
        resolved_candidate_sha=source_sha, trusted_sha="invalid")
rejects(metadata=manual, event_name="workflow_dispatch", event_source_sha="",
        resolved_candidate_sha=moved_sha)
rejects(metadata=manual, event_name="workflow_dispatch", event_source_sha="")
# A manual qualification of a push artifact still verifies the original push SHA.
rejects(evidence | {"candidate_sha": moved_sha}, event_name="workflow_dispatch",
        event_source_sha="", resolved_candidate_sha=moved_sha)

# Exercise the actual CLI outputs that actions/checkout consumes.
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "evidence.json").write_text(json.dumps(evidence))
    (temp / "run.json").write_text(json.dumps(manual))
    command = [sys.executable, str(ROOT / "scripts/resolve_rsi_source.py"),
               "--evidence", str(temp / "evidence.json"), "--workflow-run", str(temp / "run.json"),
               "--repository", options["repository"], "--candidate-ref", options["candidate_ref"],
               "--source-run-id", "123", "--event-name", "workflow_dispatch",
               "--trusted-branch", "main", "--trusted-sha", moved_sha,
               "--resolved-candidate-sha", source_sha, "--output", str(temp / "source.json"),
               "--github-output", str(temp / "outputs")]
    subprocess.run(command, check=True, capture_output=True, text=True)
    assert json.loads((temp / "source.json").read_text())["candidate_sha"] == source_sha
    assert (temp / "outputs").read_text() == f"candidate_sha={source_sha}\n"
    for path in (temp / "source.json", temp / "outputs"):
        path.unlink()
    rejected = command.copy()
    rejected[rejected.index("--resolved-candidate-sha") + 1] = moved_sha
    assert subprocess.run(rejected, capture_output=True, text=True).returncode != 0
    assert not (temp / "source.json").exists() and not (temp / "outputs").exists()

workflow = (ROOT / ".github/workflows/rsi-candidate-qualification.yml").read_text()
candidate_checkout = workflow.split("      - name: Check out candidate\n", 1)[1].split("      - name:", 1)[0]
assert "ref: ${{ steps.source.outputs.candidate_sha }}" in candidate_checkout
assert "env.CANDIDATE_REF" not in candidate_checkout
assert workflow.index("Resolve immutable candidate source") < workflow.index("      - name: Check out candidate\n")
assert workflow.index("validate_collar_evidence.py") < workflow.index("      - name: Check out candidate\n")
assert "github.event.workflow_run.head_sha" in workflow
assert '--trusted-sha "$(git -C trusted rev-parse HEAD)"' in workflow
assert "--trusted-branch" in workflow
assert "--source-run-id" in workflow.split("      - name: Validate independent collar evidence", 1)[1]
print("RSI exact source binding smoke: PASS")
