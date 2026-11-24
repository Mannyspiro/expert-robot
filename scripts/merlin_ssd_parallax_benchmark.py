#!/usr/bin/env python3
"""Matched CPU Parallax attention with resident and file-backed KV records.

Default protocol: n=512/2048/8192, d=8, five trials, 32/128-record blocks.
Timing and Python allocation tracing are separate experiments. Files have just
been written and are warmed up; no result is a cold physical SSD measurement.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
from statistics import median
import subprocess
import sys
import tempfile
from time import perf_counter
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from merlin.ssd_parallax_reference import (
    load_kv_store,
    parallax_attention_file,
    parallax_attention_resident,
    write_kv_store,
)

SIZES = (512, 2048, 8192)
DIMENSION = 8
REPEATS = 5
BLOCK_SIZES = (32, 128)
SEED = 20261124
ABS_TOLERANCE = 1e-10
REL_TOLERANCE = 1e-10
SOURCE_PATHS = (
    ROOT / "python" / "merlin" / "ssd_parallax_reference.py",
    Path(__file__).resolve(),
    ROOT / "tests" / "test_merlin_ssd_parallax_reference.py",
    ROOT / "docs" / "merlin" / "SSD_PARALLAX_EXPERIMENT_PROTOCOL_20261124.md",
)


def _hash_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _source_hashes():
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in SOURCE_PATHS}


def _source_identity():
    """Only bind a Git commit when every declared source/protocol file is clean.

    Unrelated runner evidence outside this explicit scope does not affect the
    content identity. An environment label alone never establishes provenance.
    """
    scope = [str(path.relative_to(ROOT)) for path in SOURCE_PATHS]
    expected = os.environ.get("MERLIN_EXPECTED_SHA")
    head = None
    clean = False
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", *scope],
                                 cwd=ROOT, capture_output=True, text=True)
        status = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all",
                                 "--", *scope], cwd=ROOT, check=True,
                                capture_output=True, text=True).stdout
        clean = tracked.returncode == 0 and not status
    except (OSError, subprocess.CalledProcessError):
        pass
    return {"source_commit": head if clean else "unbound", "git_head": head,
            "source_tree_clean": clean, "source_tree_clean_scope": scope,
            "expected_source_commit": expected,
            "expected_source_matches_head": expected == head if expected else None,
            "source_binding": "clean declared files at actual Git HEAD" if clean
                              else "content hashes only; source commit unbound"}


def _assert_equivalent(actual, expected):
    if len(actual) != len(expected) or not all(
            math.isfinite(a) and math.isclose(a, b, rel_tol=REL_TOLERANCE,
                                             abs_tol=ABS_TOLERANCE)
            for a, b in zip(actual, expected)):
        raise AssertionError("streamed and resident Parallax outputs disagree")


def _measure_peak(operation):
    """No elapsed-time inference is made while allocation tracing is active."""
    gc.collect()
    tracemalloc.start()
    try:
        result = operation()
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, {"current_bytes": current, "peak_bytes": peak}


def _validate_protocol(sizes, dimension, repeats, block_sizes):
    if (not isinstance(sizes, (tuple, list)) or not sizes
            or len(sizes) > 4 or len(set(sizes)) != len(sizes)
            or any(type(n) is not int or not 1 <= n <= 8192 for n in sizes)):
        raise ValueError("benchmark requires one to four distinct sizes in 1..8192")
    if type(dimension) is not int or not 1 <= dimension <= 16:
        raise ValueError("benchmark dimension must be in 1..16")
    if type(repeats) is not int or not 1 <= repeats <= 7:
        raise ValueError("benchmark repeats must be in 1..7")
    if (not isinstance(block_sizes, (tuple, list)) or not block_sizes
            or len(block_sizes) > 3 or len(set(block_sizes)) != len(block_sizes)
            or any(type(n) is not int or not 1 <= n <= 256 for n in block_sizes)):
        raise ValueError("benchmark requires one to three distinct block sizes in 1..256")


def run_benchmark(work_dir: Path, *, sizes=SIZES, dimension=DIMENSION,
                  repeats=REPEATS, block_sizes=BLOCK_SIZES):
    """Run a fixed, bounded protocol; overrides are recorded as protocol changes."""
    _validate_protocol(sizes, dimension, repeats, block_sizes)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    if tracemalloc.is_tracing():
        raise ValueError("timing requires tracemalloc to be inactive")
    started_utc = datetime.now(timezone.utc).isoformat()
    source_hashes = _source_hashes()
    source_identity = _source_identity()
    observations = []
    for n in sizes:
        generation_start = perf_counter()
        rng = random.Random(SEED + n)
        q = [rng.uniform(-1, 1) for _ in range(dimension)]
        r = [rng.uniform(-0.5, 0.5) for _ in range(dimension)]
        keys = [[rng.uniform(-1, 1) for _ in range(dimension)] for _ in range(n)]
        values = [[rng.uniform(-1, 1) for _ in range(dimension)] for _ in range(n)]
        generation_seconds = perf_counter() - generation_start
        path = work_dir / f"parallax-{n}-{dimension}.kv"
        start = perf_counter()
        metadata = write_kv_store(path, keys, values)
        write_seconds = perf_counter() - start
        del keys, values
        start = perf_counter()
        loaded = load_kv_store(path, expected_sha256=metadata["sha256"])
        load_seconds = perf_counter() - start

        def resident():
            return parallax_attention_resident(q, r, loaded["keys"], loaded["values"])

        def load_and_compute():
            fresh = load_kv_store(path, expected_sha256=metadata["sha256"])
            return parallax_attention_resident(q, r, fresh["keys"], fresh["values"])

        operations = {"hot_resident": resident, "resident_load_and_compute": load_and_compute}
        for block in block_sizes:
            operations[f"file_block_{block}"] = (
                lambda block=block: parallax_attention_file(
                    path, q, r, expected_sha256=metadata["sha256"], block_records=block))
        reference = resident()["output"]
        # An explicit warm-up validates all paths before the frozen trial budget.
        for operation in operations.values():
            _assert_equivalent(operation()["output"], reference)
        trial_seconds = {name: [] for name in operations}
        final_results = {}
        order = list(operations)
        trial_orders = []
        for trial in range(repeats):
            offset = trial % len(order)
            trial_order = order[offset:] + order[:offset]
            trial_orders.append(trial_order)
            for name in trial_order:
                start = perf_counter()
                result = operations[name]()
                elapsed = perf_counter() - start
                trial_seconds[name].append(elapsed)
                _assert_equivalent(result["output"], reference)
                final_results[name] = result

        result, resident_load_allocations = _measure_peak(load_and_compute)
        _assert_equivalent(result["output"], reference)
        _, resident_compute_allocations = _measure_peak(resident)
        stream_allocations = {}
        for name, operation in operations.items():
            if name.startswith("file_block_"):
                result, allocations = _measure_peak(operation)
                _assert_equivalent(result["output"], reference)
                stream_allocations[name] = allocations["peak_bytes"]
        variants = {}
        for name, timings in trial_seconds.items():
            result = final_results[name]
            variants[name] = {
                "trial_seconds": timings, "median_seconds": median(timings),
                "min_seconds": min(timings), "max_seconds": max(timings),
                "output": result["output"], "output_sha256": _hash_json(result["output"]),
                "max_abs_error_vs_resident": max(
                    abs(a - b) for a, b in zip(result["output"], reference)),
            }
            if name.startswith("file_block_"):
                variants[name]["io"] = result["io"]
        observations.append({
            "rows": n, "key_dim": dimension, "value_dim": dimension,
            "seed": SEED + n, "queries": {"q": q, "r": r},
            "qk_scale": 1.0 / math.sqrt(dimension),
            "input_sha256": _hash_json({"q": q, "r": r, "store_sha256": metadata["sha256"]}),
            "store": metadata,
            "preparation": {"fixture_generation_seconds": generation_seconds,
                            "store_creation_seconds": write_seconds,
                            "resident_verified_load_seconds": load_seconds,
                            "resident_load_io": loaded["io"],
                            "file_open_read_validation_in_each_streamed_trial": True},
            "trial_orders": trial_orders, "variants": variants,
            "numerical_agreement": True,
            "allocations": {
                "method": "separate tracemalloc runs; Python allocations, not process RSS",
                "resident_load_and_compute_peak_bytes": resident_load_allocations["peak_bytes"],
                "hot_resident_compute_peak_bytes": resident_compute_allocations["peak_bytes"],
                "file_read_and_compute_peak_bytes": stream_allocations,
                "resident_payload_bytes": metadata["payload_bytes"],
                "existing_resident_inputs_excluded_from_hot_compute_peak": True,
            },
        })
    protocol = {
        "sizes": list(sizes), "dimension": dimension, "repeats": repeats,
        "block_sizes": list(block_sizes), "seed": SEED,
        "warmup_runs_per_variant": 1,
        "trial_order": "rotate all variants by one position each trial",
        "absolute_tolerance": ABS_TOLERANCE, "relative_tolerance": REL_TOLERANCE,
        "stopping_rule": "fixed trial counts; fail immediately on output disagreement",
        "default_protocol_used": (tuple(sizes) == SIZES and dimension == DIMENSION
                                  and repeats == REPEATS and tuple(block_sizes) == BLOCK_SIZES),
    }
    if _source_hashes() != source_hashes or _source_identity() != source_identity:
        raise RuntimeError("benchmark source files or Git identity changed during measurement")
    return {
        "schema": "merlin-ssd-parallax-attention-benchmark/1",
        **source_identity,
        "source_files_sha256": source_hashes,
        "source_files_unchanged_during_measurement": True,
        "measurement_started_utc": started_utc,
        "measurement_finished_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(), "host_architecture": platform.machine(),
        "platform": platform.platform(), "protocol": protocol,
        "protocol_sha256": _hash_json(protocol), "observations": observations,
        "operation": "single query, one head, full KV Parallax attention in float64 CPU Python",
        "comparison": "identical operation and inputs; resident direct expression vs online file stream",
        "cache_conditions": "newly written files and warm-up runs; OS page cache uncontrolled",
        "allocation_scope": "Python allocations during specified operation; excludes OS page cache and native RSS",
        "resident_fixture_remains_live_during_trials": True,
        "resident_fixture_remains_live_during_allocation_measurements": True,
        "timing_scope": "perf_counter with tracemalloc disabled; hot resident and verified load+compute separate, stream verification included",
        "real_parallax_formula_executed": True, "synthetic_inputs": True,
        "optimized_upstream_kernel_executed": False, "trained_model_evaluated": False,
        "gpu_used": False, "physical_ssd_verified": False, "cold_storage_benchmark": False,
        "process_rss_measured": False, "production_qualified": False,
    }


def write_report_exclusive(path: Path, report):
    """Preserve earlier receipts, including when another writer wins a race."""
    path = Path(path)
    encoded = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        output.write(encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise FileExistsError("benchmark receipt already exists; choose a new output path")
    with tempfile.TemporaryDirectory(prefix="merlin-parallax-benchmark-") as directory:
        report = run_benchmark(Path(directory))
    write_report_exclusive(args.output, report)
    print(json.dumps({"schema": report["schema"], "sizes": report["protocol"]["sizes"],
                      "numerical_agreement": all(row["numerical_agreement"] for row in report["observations"]),
                      "physical_ssd_verified": False, "trained_model_evaluated": False}))


if __name__ == "__main__":
    main()
