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
):
    assert raw not in external

assert "__ER_SECRET_SSH_PRIVATE_KEY__" in external
assert "__ER_SECRET_DEPLOY_KEY__" in external
assert "__ER_SECRET_CACE_TO_ER__" in external
assert "__ER_SECRET_DEPLOY_PRIVATE__" in external
assert 'dollar + "{{ secrets.EXPERT_ROBOT_SSH_PRIVATE_KEY }}"' in external

qualify = external.split("            publish-result:", 1)[0]
publisher = external.split("            publish-result:", 1)[1]
assert "runs-on: [self-hosted, cace, oci, aarch64]" in qualify
assert "permissions:\n                contents: read" in qualify
assert "persist-credentials: false" in qualify
assert "EXPERT_ROBOT_SSH_PRIVATE_KEY" not in qualify
assert "Prepare Expert Robot reverse deploy key" in publisher
assert "Return passed evidence to Expert Robot" in publisher
assert 'return_branch="cace-return/$REQUEST_ID"' in publisher
assert 'git add .cace-return.json "$evidence_dir"' in publisher
assert '"promotion_authority": False' in publisher
assert '"monetary_cost": "free"' in publisher

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
