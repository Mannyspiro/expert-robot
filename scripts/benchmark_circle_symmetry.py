#!/usr/bin/env python3
"""Benchmark proof-backed quarter-turn canonicalization for circle workloads.

The formal theorem MathAI.Geometry.squaredDistance_origin_quarterTurnZ proves
that exact squared distance from the origin is invariant under a 90-degree
z-axis rotation. Therefore four quarter-turn-related orientations may share one
distance computation when all other correctness preconditions are satisfied.

This benchmark measures only that exact geometry kernel opportunity. It does
not claim a full CACE solver speedup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: int
    y: int
    z: int


def quarter_turn(p: Point) -> Point:
    return Point(-p.y, p.x, p.z)


def squared_distance_origin(p: Point) -> int:
    return p.x * p.x + p.y * p.y + p.z * p.z


def make_points(n: int) -> list[Point]:
    if n < 1:
        raise ValueError("n must be positive")
    state = 0x5A17
    out = []
    for _ in range(n):
        # Small deterministic integer coordinates avoid overflow and make the
        # benchmark perfectly reproducible across runners.
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        x = (state % 2001) - 1000
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        y = (state % 2001) - 1000
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        z = (state % 2001) - 1000
        out.append(Point(x, y, z))
    return out


def digest_ints(values: list[int]) -> str:
    h = hashlib.sha256()
    for value in values:
        h.update(int(value).to_bytes(16, "little", signed=True))
    return h.hexdigest()


def naive(points: list[Point]) -> tuple[str, int]:
    values: list[int] = []
    operations = 0
    for p0 in points:
        p = p0
        for _ in range(4):
            values.append(squared_distance_origin(p))
            operations += 1
            p = quarter_turn(p)
    return digest_ints(values), operations


def reduced(points: list[Point]) -> tuple[str, int]:
    values: list[int] = []
    operations = 0
    for p in points:
        value = squared_distance_origin(p)
        operations += 1
        values.extend((value, value, value, value))
    return digest_ints(values), operations


def timed(fn, points: list[Point], repeats: int) -> list[float]:
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn(points)
        times.append(time.perf_counter() - start)
    return times


def run(n: int, repeats: int) -> dict:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    points = make_points(n)

    naive_hash, naive_ops = naive(points)
    reduced_hash, reduced_ops = reduced(points)
    equivalent = naive_hash == reduced_hash
    if not equivalent:
        raise AssertionError("canonicalized workload changed exact outputs")

    naive_times = timed(naive, points, repeats)
    reduced_times = timed(reduced, points, repeats)
    naive_median = statistics.median(naive_times)
    reduced_median = statistics.median(reduced_times)

    return {
        "schema_version": 1,
        "benchmark": "circle_quarter_turn_canonicalization",
        "theorem_refs": [
            "MathAI.Geometry.squaredDistance_origin_quarterTurnZ"
        ],
        "points": n,
        "orbit_size": 4,
        "repeats": repeats,
        "correctness": {
            "exact_output_hash_equal": equivalent,
            "naive_sha256": naive_hash,
            "reduced_sha256": reduced_hash,
        },
        "work_count": {
            "naive_distance_evaluations": naive_ops,
            "reduced_distance_evaluations": reduced_ops,
            "operation_reduction_ratio": naive_ops / reduced_ops,
            "eliminated_fraction": 1.0 - reduced_ops / naive_ops,
        },
        "timing_seconds": {
            "naive_samples": naive_times,
            "reduced_samples": reduced_times,
            "naive_median": naive_median,
            "reduced_median": reduced_median,
            "median_speedup": (
                naive_median / reduced_median
                if reduced_median > 0
                else None
            ),
        },
        "evidence_ceiling": (
            "exact_geometry_kernel_benchmark_not_full_cace_solver_speedup"
        ),
        "activation_rule": (
            "Do not promote a CACE runtime optimization from this benchmark "
            "alone. Full integration requires applicability checks, CACE-level "
            "benchmarking, blind holdout non-regression, rollback, and collar gates."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--points", type=int, default=250000)
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("-o", "--output")
    args = p.parse_args()
    result = run(args.points, args.repeats)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
