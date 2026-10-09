#!/usr/bin/env python3
"""Falsifiable graph shortcut for exact conservative one-to-one transfers.

The stoichiometric columns must each have exactly one -1, one +1, and no
other nonzero entries. In that restricted class ker(S.T) is spanned by
undirected connected-component indicator vectors. No formal Lean/CACE claims.
"""
import argparse
import json
import random
from fractions import Fraction as F
from pathlib import Path
from sympy import Matrix


def components(n, edges):
    parent = list(range(n))
    size = [1] * n

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            if size[ra] < size[rb]:
                ra, rb = rb, ra
            parent[rb] = ra
            size[ra] += size[rb]
    unique = sorted(set(find(i) for i in range(n)))
    names = {r: j for j, r in enumerate(unique)}
    return [names[find(i)] for i in range(n)]


def incidence(n, edges):
    if not 1 <= n <= 64 or len(edges) > 1024:
        raise ValueError("bounded reaction graph required")
    if any(not (0 <= a < n and 0 <= b < n) or a == b for a, b in edges):
        raise ValueError("malformed transfer")
    a = Matrix.zeros(n, len(edges))
    for col, (source, target) in enumerate(edges):
        a[source, col] -= 1
        a[target, col] += 1
    return a


def strict_unit_transfer_columns(a):
    if a.rows == 0:
        return False
    # Comparing exact fractions matters: int(Fraction(3, 2)) == 1
    # must NOT turn an invalid coefficient into a valid transfer.
    return all(
        sorted(F(a[i, j]) for i in range(a.rows) if a[i, j] != 0)
        == [F(-1), F(1)]
        for j in range(a.cols)
    )


def experiment():
    rng = random.Random(20261009)
    rows = []
    edge_count = 0
    for n in (3, 5, 9, 13, 20, 32):
        for density in (0.02, 0.10, 0.33, 0.66):
            pairs = [(i, j) for i in range(n) for j in range(n) if i != j]
            edges = [pair for pair in pairs if rng.random() < density]
            matrix = incidence(n, edges)
            assert strict_unit_transfer_columns(matrix)
            classes = components(n, edges)
            count = len(set(classes))
            # Independent exact SymPy Gaussian rank/nullspace check.
            rank = matrix.rank() if matrix.cols else 0
            assert rank == n - count
            for c in sorted(set(classes)):
                witness = Matrix([[int(x == c) for x in classes]])
                assert witness * matrix == Matrix.zeros(1, matrix.cols)
            if matrix.cols:
                independent = matrix.T.nullspace()
                assert len(independent) == count
                assert all(w[a] == w[b] for w in independent for a, b in edges)
            rows.append({
                "species": n, "reactions": len(edges),
                "components": count, "stoichiometric_rank": rank,
                "component_invariants": count
            })
            edge_count += len(edges)
    bad = [
        ("nonunit_input", [-2, 1, 0]),
        ("branching_output", [-1, 1, 1]),
        ("unmodeled_sink", [-1, 0, 0]),
        ("zero_change", [0, 0, 0]),
        ("half_transfer", [-1, F(1, 2), 0]),
        ("three_halves_transfer", [-1, F(3, 2), 0])
    ]
    for name, column in bad:
        assert not strict_unit_transfer_columns(Matrix(3, 1, column)), name
    return {
        "schema_version": 1,
        "experiment": "unimolecular_component_conservation_v1",
        "cases": len(rows),
        "species_sizes": [3, 5, 9, 13, 20, 32],
        "total_directed_transfers": edge_count,
        "rank_equals_species_minus_components": True,
        "negative_controls_rejected": [name for name, _ in bad],
        "case_results": rows,
        "candidate_theorem": "For a signed graph incidence matrix S, ker(S.T) is exactly the span of the connected-component indicators.",
        "only_strict_unit_transfers": True,
        "general_reaction_networks_supported": False,
        "lean_kernel_checked": False,
        "actual_cace_backend_executed": False,
        "speedup_measured": False,
        "authority_expanded": False
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", required=True)
    options = parser.parse_args()
    result = experiment()
    Path(options.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "case_results"}))
