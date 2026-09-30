#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
baseline = json.loads((ROOT / "config/benchmarks/g0_baseline.json").read_text())

summaries = []
records = []
for variant in sorted(baseline["variants"]):
    summaries.extend([
        {"variant":variant,"split":"validation","domain":"all","cases":2,"verified":1,
         "zero_model_verified":1,"verified_rate":0.5,"average_model_calls":0.0,
         "average_proof_attempts":8.0,"average_resource_cost":0.04},
        {"variant":variant,"split":"holdout","domain":"all","cases":5,"verified":0,
         "zero_model_verified":0,"verified_rate":0.0,"average_model_calls":0.0,
         "average_proof_attempts":13.0,"average_resource_cost":0.067708},
    ])
    for case_id in baseline["evaluation_case_ids"]["holdout_overlap"]:
        records.append({"variant":variant+"::holdout","case_id":case_id,"verified":False})

payload = {"run_id":"synthetic","summaries":summaries,"records":records}
with tempfile.TemporaryDirectory() as td:
    current = Path(td) / "current.json"
    output = Path(td) / "merit.json"
    current.write_text(json.dumps(payload))
    subprocess.run([
        sys.executable, str(ROOT / "scripts/compare_benchmark_to_baseline.py"),
        str(current), "--output", str(output)
    ], cwd=ROOT, check=True, capture_output=True, text=True)
    result = json.loads(output.read_text())
    assert result["merit_demonstrated"] is True
    assert result["blind_holdout_non_regression"] is True
    assert result["validation_verified_rate_delta"] == 0.5

print("benchmark baseline comparison smoke: PASS")
