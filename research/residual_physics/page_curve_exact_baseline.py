#!/usr/bin/env python3
"""Exact finite-dimensional Page-curve baseline; not a lattice-gauge simulation.

For a Haar-random pure state on C^m tensor C^n, m <= n, the mean
von Neumann entropy of the m-dimensional subsystem is
H_(mn) - H_n - (m-1)/(2n), in nats. We use harmonic numbers, so no
third-party dependency is required. The N-qubit bipartition is symmetric.
"""
from __future__ import annotations
import json
import math


def harmonic(n: int) -> float:
    return sum(1.0 / j for j in range(1, n + 1))


def mean_page_entropy(m: int, n: int) -> float:
    if not (1 <= m <= n):
        raise ValueError("Require 1 <= m <= n")
    return harmonic(m * n) - harmonic(n) - (m - 1) / (2 * n)


def page_curve(total_qubits: int = 8) -> dict:
    if total_qubits < 1:
        raise ValueError("total_qubits must be positive")
    points = []
    for q in range(total_qubits + 1):
        dim_a, dim_b = 2**q, 2**(total_qubits - q)
        m, n = sorted((dim_a, dim_b))
        entropy = mean_page_entropy(m, n)
        points.append({
            "total_qubits": total_qubits,
            "subsystem_qubits": q,
            "dim_A": dim_a,
            "dim_B": dim_b,
            "expected_entropy_nats": entropy,
            "max_entropy_nats": math.log(m),
            "deficit_from_max_nats": math.log(m) - entropy,
        })
    # Checks for the exact formula's numerical evaluation and symmetry.
    symmetry_error = max(
        abs(points[q]["expected_entropy_nats"] -
            points[total_qubits-q]["expected_entropy_nats"])
        for q in range(total_qubits + 1)
    )
    peak_q = max(range(len(points)),
                 key=lambda q: points[q]["expected_entropy_nats"])
    return {
        "schema_version": 1,
        "scope": "exact finite-dimensional Haar-random-state Page curve; not a dynamical lattice Page curve",
        "formula": "H_(m*n) - H_n - (m-1)/(2*n), where m=min(dim_A,dim_B), n=max(dim_A,dim_B)",
        "entropy_unit": "nats",
        "total_qubits": total_qubits,
        "points": points,
        "checks": {
            "left_right_symmetry_max_abs_error": symmetry_error,
            "peak_subsystem_qubits": peak_q,
            "peak_is_balanced_partition": peak_q == total_qubits // 2,
            "endpoint_entropies_zero": points[0]["expected_entropy_nats"] == 0.0 and points[-1]["expected_entropy_nats"] == 0.0,
        },
        "limitations": [
            "This is an exact ensemble-average formula, not a sampled lattice calculation.",
            "It does not reproduce a Hamiltonian, time evolution, black-hole evaporation, or an SU(2) lattice-gauge model.",
            "Floating-point harmonic sums are used to evaluate the closed formula."
        ]
    }


if __name__ == "__main__":
    print(json.dumps(page_curve(), indent=2, sort_keys=True))
