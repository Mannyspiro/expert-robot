#!/usr/bin/env python3
"""Deterministic workload model for symmetric pair-cache canonicalization.

This is not a wall-clock benchmark. It quantifies the maximum duplicate-key
reduction available when a binary quantity is formally proven symmetric.
"""

import argparse
import json


def pair_work(n: int) -> dict:
    if n < 2:
        raise ValueError("n must be >= 2")
    ordered = n * (n - 1)
    canonical = ordered // 2
    return {
        "points": n,
        "ordered_nonself_pairs": ordered,
        "canonical_nonself_pairs": canonical,
        "duplicate_key_elimination_fraction": 1.0 - canonical / ordered,
        "theoretical_pair_work_reduction": ordered / canonical,
        "evidence_ceiling": "deterministic_work_count_not_runtime_speedup"
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--points", type=int, default=1000)
    args = p.parse_args()
    print(json.dumps(pair_work(args.points), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
