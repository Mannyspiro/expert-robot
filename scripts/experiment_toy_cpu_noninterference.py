#!/usr/bin/env python3
"""Finite two-trace noninterference experiment on a deliberately toy CPU.

Not a model of any real processor, Spectre mitigation, or hardware attestation.
No machine code, microarchitectural measurements, network, or host execution.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
from pathlib import Path

LINES = (0, 1, 2, 3)
MODES = ("leaky", "squash", "constant_line")


def cpu_run(secret: int, public: int, predict_taken: bool, cache: frozenset[int], mode: str):
    """Return (architectural output, observable final *set* of cache lines).

    The actual privilege/bounds check is always false. Only prediction may
    transiently touch cache. The intended public architectural output is the
    public bit. Squash unrealistically rolls back cache state; it is a
    counterfactual protection model, not a real-world mitigation claim.
    """
    if type(secret) is not int or secret not in (0, 1):
        raise ValueError("secret must be a bit")
    if type(public) is not int or public not in (0, 1):
        raise ValueError("public must be a bit")
    if type(predict_taken) is not bool or mode not in MODES:
        raise ValueError("invalid branch mode")
    if not isinstance(cache, frozenset) or not cache.issubset(LINES):
        raise ValueError("invalid cache set")
    touched = set(cache)
    if predict_taken:
        if mode == "constant_line":
            touched.add(2)
        else:
            touched.add(2 + secret)
    if mode == "squash":
        touched = set(cache)
    return public, frozenset(touched)


def independent_oracle(secret, public, prediction, cache, mode):
    """Independent set-based specification (not invoking cpu_run)."""
    if not prediction or mode == "squash":
        expected_cache = cache
    elif mode == "constant_line":
        expected_cache = cache | frozenset((2,))
    else:
        expected_cache = cache | frozenset((2 + secret,))
    return (public, expected_cache)


def enumerate_cache_states():
    for mask in range(1 << len(LINES)):
        yield frozenset(x for i, x in enumerate(LINES) if mask & (1 << i))


def evaluate():
    modes = {}
    for mode in MODES:
        arch_failures = []
        cache_failures = []
        transitions = 0
        for public, predict, initial in itertools.product((0, 1), (False, True), enumerate_cache_states()):
            trace0 = cpu_run(0, public, predict, initial, mode)
            trace1 = cpu_run(1, public, predict, initial, mode)
            for secret, actual in ((0, trace0), (1, trace1)):
                expected = independent_oracle(secret, public, predict, initial, mode)
                if actual != expected:
                    raise AssertionError("CPU implementation diverged from independent oracle")
                transitions += 1
            if trace0[0] != trace1[0]:
                arch_failures.append((public, predict, sorted(initial)))
            if trace0[1] != trace1[1]:
                cache_failures.append((public, predict, sorted(initial)))
        if arch_failures:
            raise AssertionError("architectural information-flow mismatch")
        modes[mode] = {
            "secret_pairs_checked": transitions // 2,
            "transitions_checked": transitions,
            "architectural_noninterference": True,
            "cache_observation_noninterference": len(cache_failures) == 0,
            "cache_counterexample_count": len(cache_failures),
            "minimal_example": (dict(public=cache_failures[0][0], predicted_taken=cache_failures[0][1],
                                    initially_cached=cache_failures[0][2]) if cache_failures else None),
        }
    # Exhaustive 2 public bits × 2 predictions × 2^4 initial cache sets.
    assert all(x["secret_pairs_checked"] == 64 for x in modes.values())
    assert modes["leaky"]["cache_counterexample_count"] == 24
    assert modes["squash"]["cache_counterexample_count"] == 0
    assert modes["constant_line"]["cache_counterexample_count"] == 0
    payload = {
        "schema_version": 1,
        "model": "synthetic-two-trace-cache-observer-v1",
        "input_domains": {"secret": 2, "public": 2, "branch_prediction": 2, "cache_states": 16},
        "total_secret_pairs_checked": sum(m["secret_pairs_checked"] for m in modes.values()),
        "modes": modes,
        "oracle_agreement": True,
        "offline_only": True,
        "cpu_hardware_tested": False,
        "formal_kernel_checked": False,
        "cace_certificate": False,
        "rsi_promotion_authorized": False,
        "external_targets_tested": False,
        "limits": "Finite set-observation toy; no timing, predictor state, eviction, coherency, faults, or real hardware claims",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {**payload, "model_report_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--output", type=Path)
    ns = ap.parse_args()
    report = evaluate()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if ns.output:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        ns.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
