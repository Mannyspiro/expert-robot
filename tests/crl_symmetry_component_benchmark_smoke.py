#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_crl_symmetry_component.py"

spec = importlib.util.spec_from_file_location("component_bench", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

result = module.run(20, 1)
assert result["correctness"]["exact_component_outputs_equal"] is True
assert result["work_count"]["operation_reduction_ratio"] == 4.0
assert result["work_count"]["eliminated_fraction"] == 0.75
assert all(result["symmetry_preconditions"].values())
assert result["evidence_ceiling"] == "crl_exact_geometry_component_not_full_cace_solver"

print("CRL symmetry component benchmark: PASS")
