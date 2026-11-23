#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"evaluate_symmetry_reduction.py"

spec=importlib.util.spec_from_file_location("symgate",SCRIPT)
module=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

contract=json.loads(
    (ROOT/"config"/"examples"/"quarter_turn_circle_symmetry_contract.json").read_text()
)
result=module.evaluate(contract)
assert result["reduction_permitted"] is False
assert "materials_invariant" in result["missing_invariance_proofs_or_declarations"]
assert result["benchmark_level"]=="kernel"

qualified=json.loads(json.dumps(contract))
for field in module.FIELDS:
    qualified[field]=True
qualified["benchmark_evidence"]["level"]="component"
qualified["status"]="COMPONENT_QUALIFIED"
result2=module.evaluate(qualified)
assert result2["reduction_permitted"] is True

print("symmetry reduction contract: PASS")
