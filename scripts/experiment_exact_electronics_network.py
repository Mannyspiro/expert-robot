#!/usr/bin/env python3
"""Offline exact resistor network experiment: graph conservation -> CACE math.

No hardware, SPICE, actual manufacturing, device flashing, secrets or network.
Fractions are exact. The independent oracle uses minors/Cramer's rule, while
the main solver uses rational Gaussian elimination. Finite examples are not
general formal proofs of Kirchhoff laws or FEM numerical correctness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

# Nodes: 0 grounded, 1..3 unknown; undirected conductance edges.
EDGES = ((0, 1, F(1)), (1, 2, F(2)), (2, 0, F(1)),
         (2, 3, F(3)), (3, 0, F(2)))
INPUTS = (F(1), F(0), F(-1))


def matrix(edges):
    a = [[F(0) for _ in range(3)] for _ in range(3)]
    for u, v, g in edges:
        if u == v or u not in range(4) or v not in range(4) or g <= 0:
            raise ValueError("invalid passive edge")
        for i, j in ((u, v), (v, u)):
            if i:
                a[i-1][i-1] += g
                if j:
                    a[i-1][j-1] -= g
    return a


def solve_gaussian(a, b):
    n = len(b)
    m = [[F(v) for v in row] + [F(b[i])] for i, row in enumerate(a)]
    if any(len(row) != n + 1 for row in m):
        raise ValueError("invalid matrix")
    for col in range(n):
        piv = next((k for k in range(col, n) if m[k][col] != 0), None)
        if piv is None:
            raise ValueError("singular or disconnected network")
        m[col], m[piv] = m[piv], m[col]
        factor = m[col][col]
        m[col] = [x / factor for x in m[col]]
        for row in range(n):
            if row == col:
                continue
            scale = m[row][col]
            m[row] = [m[row][i] - scale * m[col][i] for i in range(n + 1)]
    return tuple(m[i][-1] for i in range(n))


def determinant(a):
    n = len(a)
    if n == 0:
        return F(1)
    if n == 1:
        return a[0][0]
    return sum(
        ((-1) ** j) * a[0][j] *
        determinant([row[:j] + row[j+1:] for row in a[1:]])
        for j in range(n)
    )


def cramers_oracle(a, b):
    det = determinant(a)
    if det == 0:
        raise ValueError("singular matrix in independent oracle")
    return tuple(determinant([
        [b[i] if j == col else a[i][j] for j in range(len(b))]
        for i in range(len(b))
    ]) / det for col in range(len(b)))


def kcl_residual(edges, potentials, inputs):
    p = (F(0), *potentials)
    output = [F(0)] * 4
    for u, v, g in edges:
        f = g * (p[u] - p[v])
        output[u] += f
        output[v] -= f
    # Node 0's injection is the negative total external injection.
    demands = (-sum(inputs), *inputs)
    return tuple(output[i] - demands[i] for i in range(4))


def run():
    a = matrix(EDGES)
    x = solve_gaussian(a, INPUTS)
    if x != cramers_oracle(a, INPUTS):
        raise AssertionError("independent exact oracle mismatch")
    residuals = kcl_residual(EDGES, x, INPUTS)
    if any(residuals):
        raise AssertionError("Kirchhoff conservation violated")
    p = (F(0), *x)
    dissipated = sum(g * (p[u]-p[v])**2 for u,v,g in EDGES)
    injected_power = sum(x[i] * INPUTS[i] for i in range(3))
    if dissipated != injected_power:
        raise AssertionError("energy conservation mismatch")

    # Fault counterexample: retain the original solver output, then change
    # a board trace. A faulty as-built circuit must not inherit old approval.
    broken = tuple(e for e in EDGES if e[:2] != (1,2))
    open_trace_detected = any(kcl_residual(broken, x, INPUTS))
    swapped_polarity_detected = any(kcl_residual(
        EDGES, x, (INPUTS[0], INPUTS[1], -INPUTS[2])))
    # Remove *both* ground/reference paths from node 3 -> singular network.
    isolated = tuple(e for e in EDGES if 3 not in e[:2])
    try:
        solve_gaussian(matrix(isolated), INPUTS)
    except ValueError:
        island_detected = True
    else:
        island_detected = False

    if not all((open_trace_detected, swapped_polarity_detected, island_detected)):
        raise AssertionError("manufacturing/connection mutation escaped")
    result = {
        "schema_version": 1,
        "model": "four-node-exact-conductance-network-v1",
        "topology": [[u,v,str(g)] for u,v,g in EDGES],
        "inputs": [str(x) for x in INPUTS],
        "matrix": [[str(v) for v in row] for row in a],
        "grounded_voltages": [str(v) for v in x],
        "determinant": str(determinant(a)),
        "kcl_residuals": [str(r) for r in residuals],
        "dissipated_power": str(dissipated),
        "injected_power": str(injected_power),
        "independent_cramers_oracle_agrees": True,
        "open_trace_mutant_detected": open_trace_detected,
        "polarity_mutant_detected": swapped_polarity_detected,
        "floating_island_mutant_detected": island_detected,
        "offline_toy_only": True,
        "real_electronics_measured": False,
        "pdk_drc_lvs_run": False,
        "cace_sparse_solver_run": False,
        "lean_kernel_checked": False,
        "rsi_promotion_authorized": False,
    }
    encoded = json.dumps(result, sort_keys=True, separators=(',', ':')).encode()
    result["sha256"] = hashlib.sha256(encoded).hexdigest()
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()
    report = run()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered)
