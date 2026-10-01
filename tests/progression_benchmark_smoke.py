#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script = ROOT / "scripts" / "compare_progression_to_reference.py"

variants = ["proof_search","theorem_graph","route_memory","sequence_memory","strategy_memory"]
validation = ["hard2-validation-001","hard2-validation-002"]
holdout = ["hard2-holdout-001","hard2-holdout-002"]
sentinels = ["validation-geometry-dot-zero-right","holdout-geometry-distance-symm"]

baseline = {
    "schema_version": 1,
    "baseline_id": "synthetic-g2",
    "source_candidate_sha": "g2",
    "source_calibration_run_id": 1,
    "evaluation_case_ids": {
        "progression_validation": validation,
        "progression_holdout": holdout,
        "required_verified_sentinels": sentinels,
    },
    "variants": {
        v: {
            "validation": {"verified_rate": 0.5},
            "holdout": {"verified_rate": 0.5},
        }
        for v in variants
    },
}

records = []
for variant in variants:
    outcomes = {
        validation[0]: True,
        validation[1]: True,
        holdout[0]: True,
        holdout[1]: False,
        sentinels[0]: True,
        sentinels[1]: True,
    }
    for case_id, verified in outcomes.items():
        records.append({
            "variant": variant + "::validation",
            "case_id": case_id,
            "verified": verified,
            "proof_attempts": 3,
            "resource_cost": 0.01,
        })

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    current = td / "current.json"
    reference = td / "reference.json"
    output = td / "out.json"
    current.write_text(json.dumps({"records": records}), encoding="utf-8")
    reference.write_text(json.dumps(baseline), encoding="utf-8")
    subprocess.run([
        sys.executable, str(script), str(current),
        "--baseline", str(reference), "--output", str(output)
    ], check=True, cwd=ROOT, capture_output=True, text=True)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["merit_demonstrated"] is True
    assert result["sentinel_non_regression"] is True
    assert result["validation_verified_rate_delta"] == 0.5
    assert result["holdout_verified_rate_delta"] == 0.0

    # A saturated-core sentinel failure must veto an otherwise improving variant.
    for row in records:
        if row["case_id"] == sentinels[0]:
            row["verified"] = False
    current.write_text(json.dumps({"records": records}), encoding="utf-8")
    subprocess.run([
        sys.executable, str(script), str(current),
        "--baseline", str(reference), "--output", str(output)
    ], check=True, cwd=ROOT, capture_output=True, text=True)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["merit_demonstrated"] is False
    assert result["sentinel_non_regression"] is False

print("progression comparator smoke: PASS")
