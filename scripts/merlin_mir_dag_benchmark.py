"""Measure retained memory and construction cost of a repeated-expression DAG."""
from __future__ import annotations

import argparse
import gc
import json
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from merlin.glyph_foundry import Expr, ExprArena, TypeRef


INT = TypeRef("Int")


def make_repeated_tree(depth: int) -> Expr:
    if depth == 0:
        return Expr("identity", (), INT, INT)
    left = make_repeated_tree(depth - 1)
    right = make_repeated_tree(depth - 1)
    return Expr("compose", (left, right), INT, INT)


def retained_bytes(build):
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    value = build()
    elapsed = time.perf_counter() - started
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return value, current, peak, elapsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--depth", type=int, default=12)
    parser.add_argument("--output", default="artifacts/merlin-mir-dag-benchmark.json")
    args = parser.parse_args()
    if args.depth < 1 or args.depth > 16:
        raise SystemExit("depth must be between 1 and 16")

    raw, raw_current, raw_peak, raw_seconds = retained_bytes(
        lambda: make_repeated_tree(args.depth)
    )
    raw_stats = {
        "occurrence_nodes": raw.node_count(),
        "depth": raw.depth(),
    }
    del raw
    gc.collect()

    arena_holder = {}

    def build_dag():
        source = make_repeated_tree(args.depth)
        arena = ExprArena(max_nodes=args.depth + 2)
        dag = arena.intern(source)
        arena_holder["arena"] = arena
        del source
        gc.collect()
        return dag

    dag, dag_current, dag_peak, dag_seconds = retained_bytes(build_dag)
    dag_stats = arena_holder["arena"].stats(dag)
    direct_arena_holder = {}

    def build_direct_dag():
        arena = ExprArena(max_nodes=args.depth + 2)

        def build(depth):
            if depth == 0:
                return arena.make("identity", (), INT, INT)
            child = build(depth - 1)
            return arena.make("compose", (child, child), INT, INT)

        result = build(args.depth)
        direct_arena_holder["arena"] = arena
        return result

    direct_dag, direct_current, direct_peak, direct_seconds = retained_bytes(
        build_direct_dag
    )
    direct_stats = direct_arena_holder["arena"].stats(direct_dag)
    reduction = (
        1.0 - dag_current / raw_current if raw_current else 0.0
    )
    direct_reduction = (
        1.0 - direct_current / raw_current if raw_current else 0.0
    )
    payload = {
        "schema": "merlin.mir-dag-benchmark/1",
        "depth": args.depth,
        "raw_tree": {
            **raw_stats,
            "retained_tracemalloc_bytes": raw_current,
            "peak_tracemalloc_bytes": raw_peak,
            "construction_seconds": raw_seconds,
        },
        "interned_dag": {
            **dag_stats,
            "retained_tracemalloc_bytes": dag_current,
            "peak_tracemalloc_bytes": dag_peak,
            "construction_seconds": dag_seconds,
            "arena_capacity": args.depth + 2,
        },
        "direct_dag": {
            **direct_stats,
            "retained_tracemalloc_bytes": direct_current,
            "peak_tracemalloc_bytes": direct_peak,
            "construction_seconds": direct_seconds,
            "arena_capacity": args.depth + 2,
        },
        "retained_memory_reduction_fraction": reduction,
        "direct_dag_retained_memory_reduction_fraction": direct_reduction,
        "interpretation": (
            "Synthetic repeated-subexpression benchmark only. It measures "
            "Python allocation behavior for this constructed workload; it "
            "does not predict every Merlin workload or production RSS."
        ),
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
