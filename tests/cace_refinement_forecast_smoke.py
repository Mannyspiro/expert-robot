#!/usr/bin/env python3
import importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "forecast",ROOT/"scripts"/"forecast_cace_refinement.py"
)
module=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

bridge=json.loads(
    (ROOT/"config"/"cace_refinement_formal_bridge.json").read_text()
)
r=module.forecast(0.75,0.1,bridge)
assert r["recommended_uniform_levels"]==3
assert abs(r["predicted_h_after_levels"]-0.09375)<1e-15
assert r["minimal_level_under_halving_model"] is True
assert r["advisory_only"] is True
assert r["must_still_validate_resulting_mesh"] is True

r2=module.forecast(0.75,1.0,bridge)
assert r2["recommended_uniform_levels"]==0

print("CACE refinement forecast: PASS")
