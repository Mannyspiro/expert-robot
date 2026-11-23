#!/usr/bin/env python3
"""Research can change compute suppliers without dropping verification gates."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
policy = json.loads((ROOT / "config/avrea_half_month_budget.json").read_text())
historical = policy["historical_avrea_workflow_files"]
assert len(historical) == 9
for name in historical:
    text = (ROOT / ".github/workflows" / name).read_text()
    assert "runs-on: ubuntu-latest" in text, name
    assert "runs-on: avrea" not in text, name
    assert "group: expert-robot-research-validation-slot" in text, name
    assert "cancel-in-progress: false" in text, name
    assert "contents: write" not in text and "actions: write" not in text, name

ci = (ROOT / ".github/workflows/ci.yml").read_text()
for gate in ("cmake --build", "ctest", "tests/collar_policy_smoke.py",
             "tests/collar_runtime_contract_smoke.py", "tests/collar_vault_smoke.sh",
             "tests/research_cli_contract_smoke.py", "tests/research_runner_routing_smoke.py"):
    assert gate in ci, gate
formal = (ROOT / ".github/workflows/formal-qualification.yml").read_text()
for gate in ('LEAN_NUM_THREADS: "1"', 'build-args: "--wfail"',
             'leanchecker: "true"', 'axiom-audit: "true"',
             'axiom-audit-allow: "propext,Classical.choice,Quot.sound"',
             "hard_math_v2_witnesses.lean", "lake env lean MathAI.lean",
             "lake env lean MathAI/Audit.lean", "git diff --exit-code -- lake-manifest.json"):
    assert gate in formal, gate
compute = json.loads((ROOT / "config/compute_policy.json").read_text())
assert all(level["can_promote"] is False for level in compute["levels"])
assert compute["promotion"]["human_or_policy_gate_required"] is True
print("Research runner routing, verifier preservation and authority guards: PASS")
