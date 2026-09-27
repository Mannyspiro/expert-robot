#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "cace-headless-stage.yml"

text = WORKFLOW.read_text(encoding="utf-8")
assert "  validate-payload:" in text
assert "  stage-payload:" in text

validate, stage = text.split("  stage-payload:", 1)

# The validation job executes candidate tests but never receives the deploy key.
assert "RAILWAY_SSH_PRIVATE_KEY" not in validate
assert "secrets." not in validate
assert "python3 tests/cace_headless_client_smoke.py" in validate
assert "python3 tests/orchestrator_cace_headless_smoke.py" in validate
assert "test_headless_local_llm_contract.py" in validate
assert "actions/upload-artifact@v4" in validate

# The publisher receives only a validated artifact and must not execute it.
assert "actions/download-artifact@v4" in stage
assert "RAILWAY_SSH_PRIVATE_KEY" in stage
assert "sha256sum -c MANIFEST.sha256" in stage
for forbidden in (
    "python3 tests/",
    "python3 integration/",
    "bash -n integration/",
    "pytest",
    "ctest",
    "cmake",
    "uvicorn",
    "llama-server",
    "pip install",
    "git push --force",
    "git push -f",
):
    assert forbidden not in stage, f"publisher executes or force-pushes: {forbidden}"

# Publisher authority is limited to the CACE deploy key path. It never gets
# repository contents:write through the Expert Robot token.
assert "contents: write" not in text
assert "persist-credentials: true" not in text
assert 'git push origin "HEAD:$CACE_BRANCH"' in stage

# Fixed payload surface: recovery/provisioning helpers are deliberately not
# staged by this minimal trusted path.
assert "recover_cace_runner.sh" not in stage
assert "provision_qwen35_4b_q4km.py" not in stage

print("CACE headless staging separation: PASS")
