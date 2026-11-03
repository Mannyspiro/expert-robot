"""Paired, repeatable evaluation for single and hybrid execution strategies.

The evaluator is supplied by the caller; this module does not assume that
alternation is beneficial. All strategies receive the same deterministic seeds.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean, pstdev
from typing import Callable, Iterable


@dataclass(frozen=True)
class Trial:
    strategy: str
    seed: int
    quality: float
    latency_ms: float
    peak_rss_bytes: int
    resident_bytes: int
    load_overhead_ms: float
    maintenance_cost: float
    failures: int = 0


def run_paired_trials(strategies: dict[str, Callable[[int], dict]],
                      seeds: Iterable[int], quality_floor: float) -> dict:
    """Run each strategy on identical seeds and return metrics + Pareto set."""
    seed_list = tuple(seeds)
    if not seed_list:
        raise ValueError("at least one seed is required")
    if len(set(seed_list)) != len(seed_list) or any(not isinstance(seed, int) or isinstance(seed, bool) for seed in seed_list):
        raise ValueError("seeds must be unique integers")
    if not strategies or any(not isinstance(name, str) or not name.strip() for name in strategies):
        raise ValueError("at least one named strategy is required")
    if not isfinite(quality_floor) or not 0.0 <= quality_floor <= 1.0:
        raise ValueError("quality_floor must be within [0, 1]")
    trials: list[Trial] = []
    for name, evaluator in strategies.items():
        for seed in seed_list:
            result = evaluator(seed)
            if not isinstance(result, dict):
                raise ValueError(f"evaluator for {name} must return a metrics object")
            required = ("quality", "latency_ms", "peak_rss_bytes", "resident_bytes")
            if any(key not in result for key in required):
                raise ValueError(f"evaluator for {name} omitted required metrics")
            if isinstance(result.get("failures", 0), bool) or not isinstance(result.get("failures", 0), int):
                raise ValueError(f"failures for {name} must be an integer")
            trial = Trial(
                strategy=name, seed=seed,
                quality=float(result["quality"]),
                latency_ms=float(result["latency_ms"]),
                peak_rss_bytes=int(result["peak_rss_bytes"]),
                resident_bytes=int(result["resident_bytes"]),
                load_overhead_ms=float(result.get("load_overhead_ms", 0.0)),
                maintenance_cost=float(result.get("maintenance_cost", 0.0)),
                failures=int(result.get("failures", 0)),
            )
            numeric_metrics = (trial.quality, trial.latency_ms, trial.peak_rss_bytes,
                               trial.resident_bytes, trial.load_overhead_ms,
                               trial.maintenance_cost, trial.failures)
            if any(not isfinite(value) for value in numeric_metrics) or not 0.0 <= trial.quality <= 1.0 or min(
                trial.latency_ms, trial.peak_rss_bytes, trial.resident_bytes,
                trial.load_overhead_ms, trial.maintenance_cost, trial.failures
            ) < 0 or not isinstance(trial.failures, int):
                raise ValueError(f"invalid metrics for {name}")
            trials.append(trial)

    summary = {}
    for name in strategies:
        rows = [t for t in trials if t.strategy == name]
        summary[name] = {
            "n": len(rows),
            "quality_mean": mean(t.quality for t in rows),
            "quality_sd": pstdev(t.quality for t in rows),
            "latency_ms_mean": mean(t.latency_ms for t in rows),
            "latency_ms_sd": pstdev(t.latency_ms for t in rows),
            "peak_rss_bytes_mean": mean(t.peak_rss_bytes for t in rows),
            "resident_bytes_mean": mean(t.resident_bytes for t in rows),
            "load_overhead_ms_mean": mean(t.load_overhead_ms for t in rows),
            "maintenance_cost_mean": mean(t.maintenance_cost for t in rows),
            "failures": sum(t.failures for t in rows),
            "eligible": min(t.quality for t in rows) >= quality_floor and sum(t.failures for t in rows) == 0,
        }

    # All dimensions are minimized except quality. Pareto filtering only
    # compares candidates that passed the hard quality/failure gate.
    eligible = [name for name, row in summary.items() if row["eligible"]]
    def vector(name: str) -> tuple[float, ...]:
        r = summary[name]
        return (-r["quality_mean"], r["latency_ms_mean"],
                r["peak_rss_bytes_mean"], r["resident_bytes_mean"],
                r["load_overhead_ms_mean"], r["maintenance_cost_mean"])

    frontier = []
    for candidate in eligible:
        dominated = False
        for other in eligible:
            if other == candidate:
                continue
            a, b = vector(other), vector(candidate)
            if all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b)):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return {
        "seed_set": list(seed_list),
        "quality_floor": quality_floor,
        "summary": summary,
        "pareto_frontier": sorted(frontier),
        "promotion_authorized": False,
        "note": "Evaluation ranks candidates; a separate verifier and approval step is required for promotion.",
    }
