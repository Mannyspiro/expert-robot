#!/usr/bin/env python3
from pathlib import Path
import re
import subprocess
import textwrap

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
assert 'git clone --no-checkout "$EXPERT_ROBOT_REPO_SSH" "$work"' in publisher
assert 'git fetch --no-tags origin "$SOURCE_SHA"' in publisher
assert 'git cat-file -t "$SOURCE_SHA"' in publisher
assert 'git checkout -B "$return_branch" "$SOURCE_SHA"' in publisher
assert 'git checkout -B "$return_branch" "origin/$source_branch"' not in publisher
assert 'git rev-list --parents -n 1 HEAD' in publisher
assert 'git add .cace-return.json "$evidence_dir"' in publisher
assert '"promotion_authority": False' in publisher
assert '"monetary_cost": "free"' in publisher

assert '- "cace-return/**"' in opener
assert "contents: read" in opener
assert "pull-requests: write" in opener
assert "contents: write" not in opener
assert "scripts/validate_cace_return.py" in opener
assert "git diff --name-only" in opener
assert 'git diff --name-only "$source_sha" HEAD' in opener
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
assert '"rev-list", "--parents", "-n", "1", "HEAD"' in validator
assert 'len(lineage) != 2 or lineage[1] != source_sha' in validator

# Parse every generated shell block by its YAML indentation. A valid outer
# heredoc can still emit a broken workflow when inner Python delimiters indent.
generated = external.split("<<'BRIDGE_YAML'\n", 1)[1].split("          BRIDGE_YAML", 1)[0]
lines = generated.splitlines(keepends=True)
shell_blocks = 0
for index, line in enumerate(lines):
    if line.strip() != "run: |":
        continue
    indent = len(line) - len(line.lstrip())
    body = []
    for following in lines[index + 1:]:
        if following.strip() and len(following) - len(following.lstrip()) <= indent:
            break
        body.append(following)
    script = re.sub(r"\$\{\{.*?\}\}", "CHECK_VALUE", textwrap.dedent("".join(body)))
    parsed = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
    assert parsed.returncode == 0, parsed.stderr
    shell_blocks += 1
assert shell_blocks >= 6

print("CACE return bridge guardrails: PASS")
