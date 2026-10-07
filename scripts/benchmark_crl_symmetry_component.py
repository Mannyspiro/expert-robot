#!/usr/bin/env python3
"""Component benchmark for quarter-turn CRL exact-geometry canonicalization.

This benchmark elevates the symmetry test from a scalar kernel to the
CRL -> Magick IR -> exact geometry compiler component. It still does not
represent a full CACE PDE solve.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import statistics
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


crl = load("compile_crl", ROOT / "scripts" / "compile_crl.py")
geom = load("compile_magick_geometry", ROOT / "scripts" / "compile_magick_geometry.py")
SOURCE = ROOT / "config" / "examples" / "circle_symmetry_component.crl"


def primitive_digest(compiled):
    payload = {
        "coordinate_frame": compiled["coordinate_frame"],
        "orientation_sensitive": compiled["orientation_sensitive"],
        "exact_primitives": compiled["exact_primitives"],
        "topology_constraints": compiled["topology_constraints"],
    }
    data = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def base_ir():
    return crl.parse(SOURCE.read_text(encoding="utf-8"), str(SOURCE))


def set_radius(ir, radius):
    out = copy.deepcopy(ir)
    circle = next(
        x for x in out["geometry"]["primitives"]
        if x["id"] == "outer"
    )
    circle["parameters"]["radius_m"] = str(radius)
    return out


def naive(cases):
    digests = []
    compiler_calls = 0
    for radius in cases:
        base = set_radius(base_ir(), radius)
        for angle in (0, 90, 180, 270):
            variant = copy.deepcopy(base)
            variant["orientation"]["azimuth_deg"] = angle
            compiled = geom.compile_magick(variant)
            digests.append(primitive_digest(compiled))
            compiler_calls += 1
    return digests, compiler_calls


def reduced(cases):
    digests = []
    compiler_calls = 0
    for radius in cases:
        variant = set_radius(base_ir(), radius)
        variant["orientation"]["azimuth_deg"] = 0
        compiled = geom.compile_magick(variant)
        digest = primitive_digest(compiled)
        digests.extend((digest, digest, digest, digest))
        compiler_calls += 1
    return digests, compiler_calls


def timed(fn, cases, repeats):
    samples = []
    result = None
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn(cases)
        samples.append(time.perf_counter() - start)
    return samples, result


def run(case_count, repeats):
    if case_count < 1 or repeats < 1:
        raise ValueError("case_count and repeats must be positive")

    cases = [f"{i + 1}/97" for i in range(case_count)]

    naive_times, naive_result = timed(naive, cases, repeats)
    reduced_times, reduced_result = timed(reduced, cases, repeats)
    naive_digests, naive_calls = naive_result
    reduced_digests, reduced_calls = reduced_result

    equivalent = naive_digests == reduced_digests
    if not equivalent:
        raise AssertionError(
            "component canonicalization changed exact geometry outputs"
        )

    naive_median = statistics.median(naive_times)
    reduced_median = statistics.median(reduced_times)

    return {
        "schema_version": 1,
        "benchmark": "crl_exact_geometry_quarter_turn_component",
        "theorem_refs": [
            "MathAI.Geometry.squaredDistance_origin_quarterTurnZ",
            "MathAI.Geometry.pointOn_xyCircleAtOrigin_quarterTurnZ",
        ],
        "fixture": "config/examples/circle_symmetry_component.crl",
        "cases": case_count,
        "orbit_size": 4,
        "repeats": repeats,
        "correctness": {
            "exact_component_outputs_equal": equivalent,
            "digest_sha256": hashlib.sha256(
                "".join(naive_digests).encode("utf-8")
            ).hexdigest(),
        },
        "work_count": {
            "naive_exact_geometry_compiles": naive_calls,
            "reduced_exact_geometry_compiles": reduced_calls,
            "operation_reduction_ratio": naive_calls / reduced_calls,
            "eliminated_fraction": 1.0 - reduced_calls / naive_calls,
        },
        "timing_seconds": {
            "naive_samples": naive_times,
            "reduced_samples": reduced_times,
            "naive_median": naive_median,
            "reduced_median": reduced_median,
            "median_speedup": (
                naive_median / reduced_median
                if reduced_median > 0 else None
            ),
        },
        "symmetry_preconditions": {
            "geometry_invariant": True,
            "materials_invariant": True,
            "sources_invariant": True,
            "boundary_conditions_invariant": True,
            "observables_invariant": True,
            "orientation_metadata_invariant": True,
            "symbolic_channel_invariant": True,
        },
        "evidence_ceiling": (
            "crl_exact_geometry_component_not_full_cace_solver"
        ),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cases", type=int, default=5000)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("-o", "--output")
    args = p.parse_args()
    result = run(args.cases, args.repeats)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
