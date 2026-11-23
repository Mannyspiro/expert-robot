#!/usr/bin/env python3
"""Convert a live CACE ND bridge report into experiment-to-math input."""

from __future__ import annotations
import argparse, json
from pathlib import Path


def convert(report: dict) -> dict:
    summary = report.get("summary", {})
    history = summary.get("convergence_history")
    if not isinstance(history, dict):
        raise ValueError("report is missing summary.convergence_history")
    records = history.get("records")
    if not isinstance(records, list) or len(records) < 4:
        raise ValueError("at least four CACE convergence records are required")

    samples = []
    for row in records:
        samples.append({
            "inputs": {
                "level": int(row["level"]),
                "h_max": float(row["h_max"]),
            },
            "outputs": {
                "h_max": float(row["h_max"]),
                "interior_dofs": float(row["interior_dofs"]),
                "residual_inf": float(row["residual_inf"]),
            },
        })

    return {
        "dataset_id": f"{report['experiment_id']}::cace-refinement-history",
        "domain": "cace_fem_nd_refinement",
        "holdout_sealed": True,
        "source_scope": summary.get("scope"),
        "samples": samples,
        "probes": [
            {
                "id": "h-geometric-recurrence",
                "kind": "geometric_recurrence",
                "order": "level",
                "y": "h_max",
                "tolerance": 1e-12,
                "optimization_mechanism": "mesh_reduction",
                "expected_gain": "prove exact refinement-scale recurrence and reuse level-to-level bounds",
                "benchmark_suite": ["cace-nd-refinement"],
                "lean_namespace": "MathAI.Geometry.Refinement",
            },
            {
                "id": "h-monotone",
                "kind": "monotonicity",
                "x": "level",
                "y": "h_max",
                "direction": "decreasing",
                "optimization_mechanism": "bound_pruning",
                "expected_gain": "bound future mesh scales without recomputing geometric maxima",
                "benchmark_suite": ["cace-nd-refinement"],
                "lean_namespace": "MathAI.Geometry.Refinement",
            },
            {
                "id": "dof-vs-h",
                "kind": "scaling_law",
                "x": "h_max",
                "y": "interior_dofs",
                "optimization_mechanism": "other",
                "expected_gain": "forecast refinement cost and choose information-efficient experiment depth",
                "benchmark_suite": ["cace-nd-refinement"],
                "lean_namespace": "MathAI.Geometry.Refinement",
            },
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("report", type=Path)
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()
    result = convert(json.loads(args.report.read_text(encoding="utf-8")))
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
