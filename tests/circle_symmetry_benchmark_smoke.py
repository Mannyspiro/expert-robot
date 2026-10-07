#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_circle_symmetry.py"

spec = importlib.util.spec_from_file_location("bench", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

result = module.run(1000, 1)
assert result["correctness"]["exact_output_hash_equal"] is True
assert result["work_count"]["operation_reduction_ratio"] == 4.0
assert result["work_count"]["eliminated_fraction"] == 0.75
assert result["evidence_ceiling"] == "exact_geometry_kernel_benchmark_not_full_cace_solver_speedup"

print("circle symmetry benchmark: PASS")
