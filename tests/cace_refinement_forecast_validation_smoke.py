#!/usr/bin/env python3
import importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "val",ROOT/"scripts"/"validate_cace_refinement_forecast.py"
)
module=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

bridge=json.loads((ROOT/"config"/"cace_refinement_formal_bridge.json").read_text())
report={
  "experiment_id":"fixture",
  "summary":{"convergence_history":{"records":[
    {"level":0,"h_max":0.75},
    {"level":1,"h_max":0.375},
    {"level":2,"h_max":0.1875},
    {"level":3,"h_max":0.09375}
  ]}}
}
r=module.validate(report,bridge)
assert r["passed"] is True
assert r["counterexamples_found"]==0
assert r["records_checked"]==4

bad=json.loads(json.dumps(report))
bad["summary"]["convergence_history"]["records"][2]["h_max"]=0.2
r2=module.validate(bad,bridge)
assert r2["passed"] is False
assert r2["counterexamples_found"]==1

print("CACE refinement forecast validation: PASS")
