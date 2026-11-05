#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
external = (ROOT / ".github" / "workflows" / "external-free-runner-bridge.yml").read_text(encoding="utf-8")
opener = (ROOT / ".github" / "workflows" / "cace-return-pr.yml").read_text(encoding="utf-8")
validator = (ROOT / "scripts" / "validate_cace_return.py").read_text(encoding="utf-8")

# Expert Robot must not embed CACE's reverse deploy key or generate a second
# copy of CACE's workflow. The CACE repository branch owns that workflow.
for secret_name in (
    "EXPERT_ROBOT_SSH_PRIVATE_KEY",
    "EXPERT_ROBOT_DEPLOY_KEY",
    "CACE_TO_EXPERT_ROBOT_SSH_KEY",
    "EXPERT_ROBOT_DEPLOY_PRIVATE_KEY",
):
    assert secret_name not in external

assert 'BRIDGE_BASE_BRANCH: repair/oci-disk-diagnostics-20261105' in external
assert 'REQUEST_BRANCH: cace-request/${{ steps.package.outputs.request_id }}' in external
assert 'git fetch origin "$BRIDGE_BASE_BRANCH:refs/remotes/origin/$BRIDGE_BASE_BRANCH"' in external
assert 'git checkout -b "$REQUEST_BRANCH" "refs/remotes/origin/$BRIDGE_BASE_BRANCH"' in external
assert 'git push origin "HEAD:refs/heads/$REQUEST_BRANCH"' in external
assert 'git add bridge/request.json bridge/expert-robot-source.tar.gz' in external
assert 'request_id="expert-robot-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT-$GITHUB_SHA"' in external
assert 'git rebase "origin/$BRIDGE_BRANCH"' not in external
assert "rm -f bridge/expert-robot-source.tar.gz bridge/result.json bridge/result.log" not in external
assert "cat > .github/workflows/expert-robot-bridge.yml" not in external
assert "BRIDGE_YAML" not in external
assert "RESULT_BRANCH: cace-result/${{ steps.package.outputs.request_id }}" in external
assert 'refs/heads/$RESULT_BRANCH:refs/remotes/origin/result' in external
assert 'refs/remotes/origin/result:bridge/result.json' in external

# Producer/consumer contract: schema v3, exact request and both CACE commits,
# exact workflow/run identity, log integrity, and pass/fail as valid outcomes.
assert 'result.get("schema_version") == 3' in external
assert "cace_workflow_sha" in external
assert 'json.dumps(manifest, sort_keys=True, indent=2) + "\\n"' in external
assert 'json.dumps(manifest, sort_keys=True, indent=2) + "\\\\n"' not in external
assert "cace_workflow_id" in external
assert "expected_workflow_ref" in external
assert "refs/heads/cace-request/" in external
assert '"schema_version": 3' in external
assert "source_archive_sha256" in external
assert "hashlib.sha256(archive).hexdigest()" in external
assert "request_sha256" in external
assert "toolchain" in external
await_section, persist_section = external.split("      - name: Persist CACE evidence in Expert Robot", 1)
assert "+ expected_request" in await_section
assert "+ expected_id" not in await_section
assert "+ expected_id" in persist_section
assert "cace_workflow_run_id" in external
assert "cace_run_attempt" in external
assert "result_log_sha256" in external
assert "result_log_size_bytes" in external
assert 'result.get("status") in ("pass", "fail")' in external
assert "valid structured FAIL result" in external
assert 'echo "qualification_passed=false"' in external
assert "Persist CACE evidence in Expert Robot" in external
assert '"verification_level": "integrity-checked; source archive, request, commit, workflow and toolchain bound; signer key not yet configured"' in external
assert "EXPERT_ROBOT_SSH_PRIVATE_KEY" not in external

# A failed qualification remains valid evidence, but it must not create a PR
# that could be mistaken for a passing qualification.
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
assert "qualification_status" in opener
assert "steps.validate.outputs.qualification_status == 'pass'" in opener

assert 'payload["status"] not in {"pass", "fail"}' in validator
assert 'payload["promotion_authority"] is not False' in validator
assert 'payload["authority"] != "qualification-only"' in validator
assert 'payload["monetary_cost"] != "free"' in validator
assert 'branch.startswith("cace-return/")' in validator
assert 'expected_evidence_dir = f".cace/evidence/{request_id}"' in validator

print("CACE return bridge guardrails: PASS")
