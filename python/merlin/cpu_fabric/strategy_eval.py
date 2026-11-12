"""Randomized paired strategy evaluation with a held-out confirmation set.

Evaluators must use the supplied seed to control workload randomness. Order is
randomized independently per seed to reduce systematic order effects. Results
are descriptive evidence only; held-out data is never used to select candidates.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from random import Random
from statistics import mean, pstdev
from typing import Callable, Iterable

METRICS = ("quality", "latency_ms", "peak_rss_bytes", "resident_bytes",
           "load_overhead_ms", "maintenance_cost", "failures")


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


def _validate_seeds(seeds: Iterable[int], label: str) -> tuple[int, ...]:
    values = tuple(seeds)
    if not values:
        raise ValueError(f"at least one {label} seed is required")
    if len(set(values)) != len(values) or any(not isinstance(s, int) or isinstance(s, bool) for s in values):
        raise ValueError(f"{label} seeds must be unique integers")
    return values


def _run_set(strategies, seeds, quality_floor, order_seed):
    names = tuple(strategies)
    rng = Random(order_seed)
    by_strategy = {name: [] for name in names}
    order_log = []
    for seed in seeds:
        order = list(names)
        rng.shuffle(order)
        order_log.append({"seed": seed, "order": order})
        for name in order:
            result = strategies[name](seed)
            if not isinstance(result, dict):
                raise ValueError(f"evaluator for {name} must return a metrics object")
            required = ("quality", "latency_ms", "peak_rss_bytes", "resident_bytes")
            if any(key not in result for key in required):
                raise ValueError(f"evaluator for {name} omitted required metrics")
            failures = result.get("failures", 0)
            if isinstance(failures, bool) or not isinstance(failures, int):
                raise ValueError(f"failures for {name} must be an integer")
            t = Trial(name, seed, float(result["quality"]), float(result["latency_ms"]),
                      int(result["peak_rss_bytes"]), int(result["resident_bytes"]),
                      float(result.get("load_overhead_ms", 0.0)),
                      float(result.get("maintenance_cost", 0.0)), failures)
            vals = (t.quality, t.latency_ms, t.peak_rss_bytes, t.resident_bytes,
                    t.load_overhead_ms, t.maintenance_cost, t.failures)
            if any(not isfinite(v) for v in vals) or not 0 <= t.quality <= 1 or min(vals[1:]) < 0:
                raise ValueError(f"invalid metrics for {name}")
            by_strategy[name].append(t)

    summary = {}
    for name, rows in by_strategy.items():
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

    baseline = names[0]
    paired = {}
    for name in names[1:]:
        a = {t.seed: t for t in by_strategy[baseline]}
        b = {t.seed: t for t in by_strategy[name]}
        paired[name] = {}
        for metric in METRICS:
            diffs = [getattr(b[s], metric) - getattr(a[s], metric) for s in seeds]
            avg = mean(diffs)
            se = pstdev(diffs) / sqrt(len(diffs)) if len(diffs) > 1 else None
            paired[name][metric] = {
                "mean_difference_vs_baseline": avg,
                "sd_of_paired_differences": pstdev(diffs),
                "approx_95pct_interval": [avg - 1.96 * se, avg + 1.96 * se] if se is not None else None,
                "n_pairs": len(diffs),
            }

    eligible = [n for n, row in summary.items() if row["eligible"]]
    def vector(name):
        r = summary[name]
        return (-r["quality_mean"], r["latency_ms_mean"], r["peak_rss_bytes_mean"],
                r["resident_bytes_mean"], r["load_overhead_ms_mean"], r["maintenance_cost_mean"])
    frontier = []
    for candidate in eligible:
        if not any(other != candidate and
                   all(x <= y for x, y in zip(vector(other), vector(candidate))) and
                   any(x < y for x, y in zip(vector(other), vector(candidate)))
                   for other in eligible):
            frontier.append(candidate)
    return {"seed_set": list(seeds), "randomized_order": order_log, "baseline": baseline,
            "summary": summary, "paired_differences": paired,
            "pareto_frontier": sorted(frontier)}


def run_paired_trials(strategies: dict[str, Callable[[int], dict]],
                      seeds: Iterable[int], quality_floor: float,
                      *, held_out_seeds: Iterable[int] = (), order_seed: int = 0) -> dict:
    """Evaluate development seeds, then optionally untouched held-out seeds.

    The first strategy in insertion order is the declared baseline. Development
    results may guide selection. Held-out results are a separate confirmation
    pass and must not be used to tune the selected candidate.
    """
    dev = _validate_seeds(seeds, "development")
    held = tuple(held_out_seeds)
    if held:
        held = _validate_seeds(held, "held-out")
        if set(dev) & set(held):
            raise ValueError("development and held-out seeds must be disjoint")
    if not strategies or any(not isinstance(n, str) or not n.strip() for n in strategies):
        raise ValueError("at least one named strategy is required")
    if len(strategies) < 1 or not callable(next(iter(strategies.values()))):
        raise ValueError("strategies must map names to evaluators")
    if not isfinite(quality_floor) or not 0 <= quality_floor <= 1:
        raise ValueError("quality_floor must be within [0, 1]")
    if isinstance(order_seed, bool) or not isinstance(order_seed, int):
        raise ValueError("order_seed must be an integer")
    if any(not callable(fn) for fn in strategies.values()):
        raise ValueError("every strategy must be callable")
    development = _run_set(strategies, dev, quality_floor, order_seed)
    heldout = _run_set(strategies, held, quality_floor, order_seed ^ 0x5EED) if held else None
    return {
        "development": development,
        "held_out": heldout,
        "protocol": {
            "baseline": next(iter(strategies)),
            "order_seed": order_seed,
            "evaluator_seed_contract": "Each evaluator must use its seed to control workload randomness.",
            "held_out_policy": "Held-out seeds are a confirmation set; do not use them for candidate selection or tuning.",
            "interval_method": "normal-approximation 95% interval over paired differences; descriptive for small n",
        },
        "promotion_authorized": False,
        "note": "Evaluation ranks candidates; independent verification and explicit approval are required for promotion.",
    }
