#!/usr/bin/env python3
"""Offline exact-rational Cartesian product-of-paths metric study.

This checks a possible CACE graph-feature bridge, not the CACE runtime itself.
An independent Bellman-Ford oracle evaluates the product graph.
"""
import argparse
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json


def path_coordinate(weights):
    point = Fraction(0)
    coords = [point]
    for w in weights:
        assert w > 0
        point += w
        coords.append(point)
    return coords


def graph_edges(xs, ys):
    graph = {}
    for i, j in product(range(len(xs)), range(len(ys))):
        links = []
        if i:
            links.append(((i-1, j), xs[i]-xs[i-1]))
        if i+1 < len(xs):
            links.append(((i+1, j), xs[i+1]-xs[i]))
        if j:
            links.append(((i, j-1), ys[j]-ys[j-1]))
        if j+1 < len(ys):
            links.append(((i, j+1), ys[j+1]-ys[j]))
        graph[(i, j)] = links
    return graph


def shortest_paths(graph, source):
    # Independent exhaustive Bellman-Ford relaxation; no distance formula reused.
    dist = {v: None for v in graph}
    dist[source] = Fraction(0)
    for _ in range(len(graph)-1):
        changed = False
        for u, links in graph.items():
            if dist[u] is None:
                continue
            for v, w in links:
                assert w > 0
                d = dist[u] + w
                if dist[v] is None or d < dist[v]:
                    dist[v] = d
                    changed = True
        if not changed:
            break
    assert all(d is not None for d in dist.values())
    return dist


def experiment():
    cases = [
        (["1/2"], ["3/2"]),
        (["1", "2"], ["3/4"]),
        (["1/3", "5/2", "1/4"], ["7/3", "2"]),
        (["2", "1/7"], ["1/5", "3/4", "2/3"]),
    ]
    rows = []
    checked = mutation_failures = 0
    for a, b in cases:
        xs = path_coordinate(list(map(Fraction, a)))
        ys = path_coordinate(list(map(Fraction, b)))
        g = graph_edges(xs, ys)
        for s in g:
            independent = shortest_paths(g, s)
            for t in g:
                dx = abs(xs[s[0]] - xs[t[0]])
                dy = abs(ys[s[1]] - ys[t[1]])
                if dx + dy != independent[t]:
                    raise AssertionError((s, t, dx, dy, independent[t]))
                if max(dx, dy) != independent[t]:
                    mutation_failures += 1
                checked += 1
        rows.append({"x_edges": a, "y_edges": b,
                     "vertices": len(g), "pairs": len(g)**2})
    assert checked == sum(row["pairs"] for row in rows)
    assert mutation_failures > 0
    return {
        "schema_version": 1, "experiment": "l1-product-graph-distance-v1",
        "cases": rows, "vertex_pairs_checked": checked,
        "exact_shortest_path_disagreements": 0,
        "max_instead_of_sum_mutation_failures": mutation_failures,
        "fixture_digest_sha256": sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
        "graph_class": "Cartesian products of finite positively weighted paths",
        "arithmetic": "exact Python Fraction", "shortest_path_oracle": "independent Bellman-Ford",
        "cace_runtime_executed": False, "lean_qualified": False,
        "general_graph_metric_claimed": False, "security_authority_expanded": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", required=True)
    args = parser.parse_args()
    record = experiment()
    with open(args.o, "w", encoding="utf-8") as out:
        json.dump(record, out, indent=2)
        out.write("\n")
    print(json.dumps(record))
