#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
external = (ROOT / ".github" / "workflows" / "external-free-runner-bridge.yml").read_text(encoding="utf-8")
opener = (ROOT / ".github" / "workflows" / "cace-return-pr.yml").read_text(encoding="utf-8")
validator = (ROOT / "scripts" / "validate_cace_return.py").read_text(encoding="utf-8")

for raw in (
    "${{ secrets.EXPERT_ROBOT_SSH_PRIVATE_KEY }}",
    "${{ secrets.EXPERT_ROBOT_DEPLOY_KEY }}",
    "${{ secrets.CACE_TO_EXPERT_ROBOT_SSH_KEY }}",
    "${{ secrets.EXPERT_ROBOT_DEPLOY_PRIVATE_KEY }}",
    "${{ secrets.RAILWAY_SSH_PRIVATE_KEY }}",
):
    assert raw not in external

for placeholder in (
    "__ER_SECRET_SSH_PRIVATE_KEY__",
    "__ER_SECRET_DEPLOY_KEY__",
    "__ER_SECRET_CACE_TO_ER__",
    "__ER_SECRET_DEPLOY_PRIVATE__",
    "__ER_SECRET_RAILWAY_SSH_PRIVATE_KEY__",
):
    assert placeholder in external

assert 'dollar + "{{ secrets.EXPERT_ROBOT_SSH_PRIVATE_KEY }}"' in external
assert 'dollar + "{{ secrets.RAILWAY_SSH_PRIVATE_KEY }}"' in external
assert "permissions:\\n  contents: read" in external
assert "persist-credentials: false" in external

# The execution envelope is checked against the request, exact source/CACE
# commits, workflow identity, run attempt, toolchain, authority and log digest.
for field in (
    "cace_workflow_sha",
    "cace_workflow_ref",
    "cace_workflow_run_id",
    "cace_run_attempt",
    "result_log_sha256",
    "result_log_size_bytes",
):
    assert field in external
assert 'result.get("schema_version") == 3' in external
assert 'result.get("status") in ("pass", "fail")' in external
assert 'result.get("authority") == "qualification-only"' in external
assert 'result.get("promotion_authority") is False' in external

# Failure results are retained in Expert Robot only after envelope validation.
assert "Persist CACE evidence in Expert Robot" in external
assert "steps.await.outputs.evidence_validated == 'true'" in external
assert "External qualification returned a valid structured FAIL result" in external
assert '"verification_level": "integrity-checked; Ed25519 signer trust not established"' in external
assert 'git add "$evidence_dir"' in external
assert '"promotion_authority": False' in external

# A separate PR workflow opens a review request only for passing evidence;
# it cannot merge or promote the result.
assert '- "cace-return/**"' in opener
assert "contents: read" in opener
assert "pull-requests: write" in opener
assert "contents: write" not in opener
assert "scripts/validate_cace_return.py" in opener
assert "git diff --name-only" in opener
assert "Non-evidence change on CACE return branch" in opener
assert "gh pr create" in opener
assert "gh pr merge" not in opener
assert "merge --auto" not in opener

assert 'payload["status"] != "pass"' in validator
assert 'payload["promotion_authority"] is not False' in validator
assert 'payload["authority"] != "qualification-only"' in validator
assert 'payload["monetary_cost"] != "free"' in validator
assert 'branch.startswith("cace-return/")' in validator
assert 'expected_evidence_dir = f".cace/evidence/{request_id}"' in validator

print("CACE return bridge guardrails: PASS")
