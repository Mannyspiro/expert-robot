#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
freezer = ROOT / "scripts" / "freeze_progression_baseline.py"
variants = ["proof_search","theorem_graph","route_memory","sequence_memory","strategy_memory"]

suite = {
    "schema_version": 1,
    "suite_id": "synthetic-progression",
    "variants": [{"variant_id": v, "enabled_layers": ["proof_search"]} for v in variants],
    "cases": [
        {"case_id":"train","split":"train","tags":[]},
        {"case_id":"hard-val","split":"validation","tags":["hard_v2"]},
        {"case_id":"hard-hold","split":"holdout","tags":["hard_v2"]},
        {"case_id":"sentinel","split":"holdout","tags":[]},
    ],
}
records = []
for v in variants:
    for case_id, verified in (
        ("hard-val", False),
        ("hard-hold", True),
        ("sentinel", True),
    ):
        records.append({
            "variant": v + "::validation",
            "case_id": case_id,
            "verified": verified,
        })
results = {"records": records}

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    suite_path = td / "suite.json"
    results_path = td / "results.json"
    out = td / "baseline.json"
    suite_path.write_text(json.dumps(suite, indent=2) + "\n", encoding="utf-8")
    results_path.write_text(json.dumps(results), encoding="utf-8")
    cmd = [
        sys.executable, str(freezer), str(results_path),
        "--suite", str(suite_path),
        "--source-candidate-sha", "g2",
        "--source-run-id", "123",
        "--source-commit", "calibration",
        "--baseline-id", "synthetic",
        "--output", str(out),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
    baseline = json.loads(out.read_text(encoding="utf-8"))
    assert baseline["variants"]["proof_search"]["validation"]["verified_rate"] == 0.0
    assert baseline["variants"]["proof_search"]["holdout"]["verified_rate"] == 1.0
    assert baseline["evaluation_case_ids"]["required_verified_sentinels"] == ["sentinel"]

    # Freezing must fail if the reference generation regresses a sentinel.
    bad = json.loads(json.dumps(results))
    for row in bad["records"]:
        if row["case_id"] == "sentinel":
            row["verified"] = False
    results_path.write_text(json.dumps(bad), encoding="utf-8")
    proc = subprocess.run(cmd, cwd=ROOT, check=False, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "sentinel regression" in (proc.stdout + proc.stderr)

print("progression baseline freezer smoke: PASS")
