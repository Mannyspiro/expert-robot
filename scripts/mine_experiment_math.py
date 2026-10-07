#!/usr/bin/env python3
"""Mine experiment/simulation data for mathematical conjecture candidates.

This is a hypothesis generator only. It never proves a statement and never
creates a runtime optimization directly.

Input JSON:
{
  "dataset_id": "...",
  "domain": "...",
  "samples": [{"inputs": {...}, "outputs": {...}}, ...],
  "probes": [
    {"id":"...", "kind":"monotonicity", "x":"h", "y":"error", "direction":"decreasing"},
    {"id":"...", "kind":"scaling_law", "x":"scale", "y":"response"},
    {"id":"...", "kind":"invariance", "group_by":["invariant"], "y":"response"}
  ]
}
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any


def canonical_sha256(payload: Any) -> str:
    data = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def numeric(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _candidate_base(payload: dict, probe: dict, pattern_class: str) -> dict:
    return {
        "schema_version": "0.1",
        "candidate_id": f"{payload['dataset_id']}::{probe['id']}",
        "source_evidence": {
            "artifact_sha256": canonical_sha256(payload),
            "generator": "mine_experiment_math.py",
            "sample_count": len(payload["samples"]),
            "holdout_sealed": bool(payload.get("holdout_sealed", False)),
            "domains": [payload.get("domain", "unknown")],
        },
        "pattern_class": pattern_class,
        "empirical_support": {
            "fit_score": None,
            "max_observed_residual": None,
            "counterexamples_found": 0,
            "notes": "",
        },
        "formalization_target": {
            "domain": payload.get("domain", "unknown"),
            "lean_namespace": probe.get("lean_namespace", "MathAI.Experimental"),
            "quantifiers": [],
            "assumptions": [],
            "conclusion": "",
        },
        "proof_obligations": [
            "state exact mathematical domain",
            "state all assumptions explicitly",
            "search for counterexamples before promotion",
            "obtain Lean proof before treating candidate as theorem",
        ],
        "optimization_hypothesis": {
            "mechanism": probe.get("optimization_mechanism", "other"),
            "expected_gain": probe.get(
                "expected_gain",
                "unknown until benchmarked",
            ),
            "correctness_dependency": "requires formal proof of candidate statement",
            "benchmark_suite": probe.get("benchmark_suite", []),
        },
        "status": "INSPIRED",
        "proof_ref": None,
        "lineage": [payload["dataset_id"], probe["id"]],
    }


def monotonicity(payload: dict, probe: dict) -> dict:
    x_name, y_name = probe["x"], probe["y"]
    direction = probe.get("direction", "increasing")
    rows = []
    for i, sample in enumerate(payload["samples"]):
        x = numeric(sample["inputs"][x_name], f"samples[{i}].inputs.{x_name}")
        y = numeric(sample["outputs"][y_name], f"samples[{i}].outputs.{y_name}")
        rows.append((x, y))
    rows.sort()

    violations = 0
    comparisons = 0
    for (_, y0), (_, y1) in zip(rows, rows[1:]):
        comparisons += 1
        if direction == "increasing":
            violations += int(y1 < y0)
        elif direction == "decreasing":
            violations += int(y1 > y0)
        else:
            raise ValueError("monotonicity direction must be increasing or decreasing")

    fit = 1.0 if comparisons == 0 else 1.0 - violations / comparisons
    c = _candidate_base(payload, probe, "monotonicity")
    c["informal_statement"] = (
        f"Observed {y_name} is {direction} as {x_name} increases "
        f"over the sampled domain."
    )
    c["empirical_support"].update({
        "fit_score": fit,
        "counterexamples_found": violations,
        "notes": f"{comparisons} adjacent ordered comparisons",
    })
    c["formalization_target"].update({
        "quantifiers": [f"x1 x2 : {probe.get('lean_type', 'ℝ')}"],
        "assumptions": [
            f"x1 ≤ x2",
            "x1 and x2 lie in the formally specified admissible domain",
        ],
        "conclusion": (
            f"F x1 {'≤' if direction == 'increasing' else '≥'} F x2"
        ),
    })
    return c


def scaling_law(payload: dict, probe: dict) -> dict:
    x_name, y_name = probe["x"], probe["y"]
    pts = []
    for i, sample in enumerate(payload["samples"]):
        x = numeric(sample["inputs"][x_name], f"samples[{i}].inputs.{x_name}")
        y = numeric(sample["outputs"][y_name], f"samples[{i}].outputs.{y_name}")
        if x > 0 and y > 0:
            pts.append((math.log(x), math.log(y)))
    if len(pts) < 3:
        raise ValueError("scaling_law requires at least 3 positive samples")

    xs, ys = zip(*pts)
    mx, my = mean(xs), mean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        raise ValueError("scaling_law x values must vary")
    exponent = sum((x - mx) * (y - my) for x, y in pts) / denom
    intercept = my - exponent * mx
    predictions = [intercept + exponent * x for x in xs]
    ss_res = sum((y - p) ** 2 for y, p in zip(ys, predictions))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1.0 if ss_tot == 0 else max(0.0, min(1.0, 1.0 - ss_res / ss_tot))
    max_log_residual = max(abs(y - p) for y, p in zip(ys, predictions))

    c = _candidate_base(payload, probe, "scaling_law")
    c["informal_statement"] = (
        f"Observed {y_name} approximately follows C*{x_name}^k "
        f"with k≈{exponent:.8g} over the sampled domain."
    )
    c["empirical_support"].update({
        "fit_score": r2,
        "max_observed_residual": max_log_residual,
        "notes": f"log-log least-squares exponent={exponent:.17g}",
    })
    c["formalization_target"].update({
        "quantifiers": ["λ x"],
        "assumptions": [
            "λ > 0",
            "x and λ*x lie in the formally specified admissible domain",
        ],
        "conclusion": f"F (λ • x) = λ ^ k * F x for an exact candidate exponent k",
    })
    c["proof_obligations"].append(
        "replace fitted floating exponent with an exact proposed exponent before proof search"
    )
    return c


def invariance(payload: dict, probe: dict) -> dict:
    group_by = probe["group_by"]
    y_name = probe["y"]
    tolerance = float(probe.get("tolerance", 1e-9))

    groups: dict[tuple, list[float]] = {}
    for i, sample in enumerate(payload["samples"]):
        key = tuple(sample["inputs"][name] for name in group_by)
        y = numeric(sample["outputs"][y_name], f"samples[{i}].outputs.{y_name}")
        groups.setdefault(key, []).append(y)

    max_residual = 0.0
    comparisons = 0
    violations = 0
    for values in groups.values():
        if len(values) < 2:
            continue
        anchor = values[0]
        for value in values[1:]:
            residual = abs(value - anchor)
            max_residual = max(max_residual, residual)
            comparisons += 1
            violations += int(residual > tolerance)

    fit = 1.0 if comparisons == 0 else 1.0 - violations / comparisons
    c = _candidate_base(payload, probe, "invariance")
    c["informal_statement"] = (
        f"Observed {y_name} appears invariant under transformations that preserve "
        f"{', '.join(group_by)}."
    )
    c["empirical_support"].update({
        "fit_score": fit,
        "max_observed_residual": max_residual,
        "counterexamples_found": violations,
        "notes": f"{comparisons} within-class comparisons, tolerance={tolerance}",
    })
    c["formalization_target"].update({
        "quantifiers": ["x", "g"],
        "assumptions": [
            "g belongs to the formally specified transformation class",
            "the declared invariants are preserved by g",
        ],
        "conclusion": "F (g • x) = F x",
    })
    return c


def geometric_recurrence(payload: dict, probe: dict) -> dict:
    order_name = probe["order"]
    y_name = probe["y"]
    tolerance = float(probe.get("tolerance", 1e-9))
    rows = []
    for i, sample in enumerate(payload["samples"]):
        order = numeric(sample["inputs"][order_name], f"samples[{i}].inputs.{order_name}")
        y = numeric(sample["outputs"][y_name], f"samples[{i}].outputs.{y_name}")
        if y == 0:
            raise ValueError("geometric_recurrence requires nonzero y values")
        rows.append((order, y))
    rows.sort()
    if len(rows) < 3:
        raise ValueError("geometric_recurrence requires at least 3 ordered samples")

    ratios = [b[1] / a[1] for a, b in zip(rows, rows[1:])]
    ratio = mean(ratios)
    max_residual = max(abs(r - ratio) for r in ratios)
    violations = sum(abs(r - ratio) > tolerance for r in ratios)
    scale = max(1.0, abs(ratio))
    fit = max(0.0, min(1.0, 1.0 - max_residual / scale))

    c = _candidate_base(payload, probe, "recurrence")
    c["informal_statement"] = (
        f"Observed {y_name} approximately satisfies y_(n+1)=q*y_n "
        f"with q≈{ratio:.12g} over ordered {order_name}."
    )
    c["empirical_support"].update({
        "fit_score": fit,
        "max_observed_residual": max_residual,
        "counterexamples_found": violations,
        "notes": f"successive ratios={ratios!r}",
    })
    c["formalization_target"].update({
        "quantifiers": ["n : ℕ"],
        "assumptions": [
            "n and n+1 are valid refinement levels",
            "the refinement operator satisfies the formally specified geometric assumptions",
        ],
        "conclusion": "measure (refine^(n+1) x) = q * measure (refine^n x) for an exact q",
    })
    c["proof_obligations"].append(
        "replace fitted recurrence ratio q with an exact rational/algebraic candidate before proof search"
    )
    return c


MINERS = {
    "monotonicity": monotonicity,
    "scaling_law": scaling_law,
    "invariance": invariance,
    "geometric_recurrence": geometric_recurrence,
}


def mine(payload: dict) -> dict:
    if not payload.get("dataset_id"):
        raise ValueError("dataset_id is required")
    if not isinstance(payload.get("samples"), list) or not payload["samples"]:
        raise ValueError("samples must be a nonempty array")
    probes = payload.get("probes")
    if not isinstance(probes, list) or not probes:
        raise ValueError("probes must be a nonempty array")

    results = []
    for probe in probes:
        kind = probe.get("kind")
        if kind not in MINERS:
            raise ValueError(f"unsupported probe kind {kind!r}")
        results.append(MINERS[kind](payload, probe))

    return {
        "schema_version": 1,
        "dataset_id": payload["dataset_id"],
        "source_sha256": canonical_sha256(payload),
        "candidate_count": len(results),
        "candidates": results,
        "epistemic_status": "hypothesis_generation_only_not_proof",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = mine(payload)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
