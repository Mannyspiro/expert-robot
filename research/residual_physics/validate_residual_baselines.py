#!/usr/bin/env python3
"""Fail-closed checks for residual-physics toy baselines; not physical validation."""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


toy = load("residual_toy_baselines", "research/residual_physics/toy_baselines.py")
page = load("exact_page_curve_baseline", "research/residual_physics/page_curve_exact_baseline.py")

coarse, fine = toy.frg_toy(0.1), toy.frg_toy(0.05)
ratio = coarse["absolute_error"] / fine["absolute_error"]
assert 1.8 < ratio < 2.2, f"Euler first-order error ratio out of range: {ratio}"
assert coarse["fixed_points"] == [0.0, 1.0]
assert coarse["beta_prime_at_fixed_points"] == [-1.0, 1.0]

bell = toy.bell_pair_entropy_toy()
assert len(bell) == 5
for item in bell:
    k = item["crossing_bell_pairs"]
    assert math.isclose(item["entropy_nats"], k * math.log(2), rel_tol=0, abs_tol=1e-14)

affine = toy.affine_fixed_point_toy()
assert max(abs(x) for x in affine["residual"]) < 1e-12
assert all(x > 0 for x in affine["eigenvalues"])

mcmc = toy.gaussian_mcmc_toy()
assert abs(mcmc["sample_mean"]) < 0.03
assert 0.95 < mcmc["sample_variance"] < 1.02
assert 0.65 < mcmc["acceptance_rate_including_warmup"] < 0.75

curve = page.page_curve(8)
assert curve["checks"]["endpoint_entropies_zero"]
assert curve["checks"]["left_right_symmetry_max_abs_error"] <= 1e-12
assert curve["checks"]["peak_is_balanced_partition"]
assert curve["checks"]["peak_subsystem_qubits"] == 4
for point in curve["points"]:
    assert point["expected_entropy_nats"] >= -1e-14
    assert point["expected_entropy_nats"] <= point["max_entropy_nats"] + 1e-12

archive_path = ROOT / "research/residual_physics/page_curve_exact_baseline_20261028.json"
archived = json.loads(archive_path.read_text(encoding="utf-8"))
assert len(archived["points"]) == len(curve["points"])
for actual, expected in zip(curve["points"], archived["points"], strict=True):
    assert actual["subsystem_qubits"] == expected["subsystem_qubits"]
    assert math.isclose(actual["expected_entropy_nats"], expected["expected_entropy_nats"],
                        rel_tol=0, abs_tol=1e-12)

print(json.dumps({
    "status": "pass",
    "scope": "dependency-free toy baseline regression only",
    "frg_euler_error_ratio": ratio,
    "affine_max_abs_residual": max(abs(x) for x in affine["residual"]),
    "mcmc_mean": mcmc["sample_mean"],
    "mcmc_variance": mcmc["sample_variance"],
    "page_curve_peak_qubits": curve["checks"]["peak_subsystem_qubits"],
    "page_curve_symmetry_error": curve["checks"]["left_right_symmetry_max_abs_error"],
    "physical_task_promotion": False,
}, indent=2, sort_keys=True))
