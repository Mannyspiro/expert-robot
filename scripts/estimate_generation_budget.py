#!/usr/bin/env python3
"""Estimate an experiment run budget from gain, uncertainty, cost and diminishing returns."""

import argparse
import json
import math


def estimate(expected_gain, variance, cost_per_run, diminishing_rate,
             information_weight, cost_weight, min_runs, max_runs):
    if expected_gain < 0 or variance < 0 or cost_per_run < 0:
        raise ValueError("gain, variance and cost must be non-negative")
    if not 0 <= diminishing_rate < 1:
        raise ValueError("diminishing rate must be in [0, 1)")
    if min_runs < 1 or max_runs < min_runs:
        raise ValueError("invalid run bounds")

    cumulative = 0.0
    best_utility = float("-inf")
    best_runs = min_runs
    trace = []

    sigma = math.sqrt(variance)
    for run in range(1, max_runs + 1):
        exploitation = expected_gain * math.exp(-diminishing_rate * (run - 1))
        information = information_weight * sigma / math.sqrt(run)
        cost = cost_weight * cost_per_run
        marginal = exploitation + information - cost
        cumulative += marginal
        trace.append({
            "run": run,
            "expected_capability_gain": exploitation,
            "information_value": information,
            "normalized_cost": cost,
            "marginal_utility": marginal,
            "cumulative_utility": cumulative,
        })
        if run >= min_runs and cumulative > best_utility:
            best_utility = cumulative
            best_runs = run

    # Stop at the first non-positive marginal after the current optimum.
    for row in trace:
        if row["run"] >= min_runs and row["run"] >= best_runs and row["marginal_utility"] <= 0:
            best_runs = min(best_runs, row["run"])
            break

    return {
        "schema_version": 1,
        "recommended_runs": max(min_runs, min(max_runs, best_runs)),
        "assumptions": {
            "expected_gain": expected_gain,
            "variance": variance,
            "cost_per_run": cost_per_run,
            "diminishing_rate": diminishing_rate,
            "information_weight": information_weight,
            "cost_weight": cost_weight,
            "min_runs": min_runs,
            "max_runs": max_runs,
        },
        "trace": trace,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--expected-gain", type=float, default=0.10)
    p.add_argument("--variance", type=float, default=0.05)
    p.add_argument("--cost-per-run", type=float, default=1.0)
    p.add_argument("--diminishing-rate", type=float, default=0.20)
    p.add_argument("--information-weight", type=float, default=0.35)
    p.add_argument("--cost-weight", type=float, default=0.08)
    p.add_argument("--min-runs", type=int, default=2)
    p.add_argument("--max-runs", type=int, default=30)
    args = p.parse_args()
    print(json.dumps(estimate(
        args.expected_gain, args.variance, args.cost_per_run,
        args.diminishing_rate, args.information_weight, args.cost_weight,
        args.min_runs, args.max_runs,
    ), indent=2))


if __name__ == "__main__":
    main()
