#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(*args):
    return subprocess.run(
        [sys.executable, *map(str, args)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

ready = run(ROOT / "scripts" / "production_readiness.py")
payload = json.loads(ready.stdout)
assert payload["ready"] is True
assert payload["max_parallel_vcpu"] == 24

low_cost = json.loads(run(
    ROOT / "scripts" / "estimate_generation_budget.py",
    "--cost-per-run", "0.2",
).stdout)
high_cost = json.loads(run(
    ROOT / "scripts" / "estimate_generation_budget.py",
    "--cost-per-run", "5.0",
).stdout)
for payload in (low_cost, high_cost):
    assert 2 <= payload["recommended_runs"] <= 30
assert high_cost["recommended_runs"] <= low_cost["recommended_runs"]

passing = {
    "candidate_id": "candidate-pass",
    "generation_budget_estimated": True,
    "collared_execution": True,
    "validation_verified_rate_delta": 0.10,
    "holdout_verified_rate_delta": 0.0,
    "qualification_passed": True,
    "formal_verification_passed": True,
    "rollback_verified": True,
    "lineage_verified": True,
    "authority_change": "same",
    "core_integrity_verified": True,
    "collar_tripped": False,
}
failing = dict(passing)
failing["candidate_id"] = "candidate-no-validation-gain"
failing["validation_verified_rate_delta"] = 0.0

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "pass.json"
    p.write_text(json.dumps(passing), encoding="utf-8")
    verdict = json.loads(run(ROOT / "scripts" / "evaluate_promotion.py", p).stdout)
    assert verdict["eligible_for_automatic_promotion"] is True

    f = Path(td) / "fail.json"
    f.write_text(json.dumps(failing), encoding="utf-8")
    verdict = json.loads(run(ROOT / "scripts" / "evaluate_promotion.py", f).stdout)
    assert verdict["eligible_for_automatic_promotion"] is False
    assert "validation_improved" in verdict["failed_gates"]

print("production policy smoke: PASS")
