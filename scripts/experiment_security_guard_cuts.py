#!/usr/bin/env python3
"""Offline finite guard-placement experiment. No network or executable targets.

Enumerates all 512 forward DAGs on five abstract vertices, excluding the
uncuttable direct source-to-sink edge. Source=0, sensitive sink=4. Costs are
prespecified (1,5,1). Graph completeness and guard enforcement are assumptions.
"""
import argparse
from collections import deque
from itertools import combinations
import json
import os
from pathlib import Path

COSTS = {1: 1, 2: 5, 3: 1}
EDGES = [(i, j) for i in range(5) for j in range(i + 1, 5) if (i, j) != (0, 4)]


def route(edges, blocked):
    queue = deque([(0,)])
    visited = {0}
    while queue:
        path = queue.popleft()
        if path[-1] == 4:
            return path
        for a, b in edges:
            if a == path[-1] and b not in visited and b not in blocked:
                visited.add(b)
                queue.append(path + (b,))
    return None


def subsets():
    for size in range(4):
        yield from combinations(COSTS, size)


def optimum(edges):
    feasible = [s for s in subsets() if route(edges, set(s)) is None]
    return min(feasible, key=lambda s: (sum(COSTS[v] for v in s), len(s), s))


def greedy(edges):
    guards = set()
    while (path := route(edges, guards)) is not None:
        guards.add(path[1])
    return tuple(sorted(guards))


def verify(edges, guards, claimed_cost):
    # Independent DFS path enumeration, not the producer's reachability BFS.
    try:
        edges = [tuple(e) for e in edges]
        if len(edges) > len(EDGES) or len(set(edges)) != len(edges):
            return False
        if any(e not in EDGES or any(type(v) is not int for v in e) for e in edges):
            return False
        if any(type(v) is not int for v in guards) or type(claimed_cost) is not int:
            return False
    except TypeError:
        return False
    if len(set(guards)) != len(guards) or any(v not in COSTS for v in guards):
        return False
    if claimed_cost != sum(COSTS[v] for v in guards):
        return False
    paths = []
    def walk(vertex, path):
        if vertex == 4:
            paths.append(path)
        for a, b in edges:
            if a == vertex:
                walk(b, path + (b,))
    walk(0, (0,))
    if any(not set(guards).intersection(p) for p in paths):
        return False
    # Check every cheaper candidate, including the empty set.
    for candidate in subsets():
        if sum(COSTS[v] for v in candidate) < claimed_cost:
            if all(set(candidate).intersection(p) for p in paths):
                return False
    return True


def experiment():
    rows = []
    for mask in range(1 << len(EDGES)):
        edges = [e for i, e in enumerate(EDGES) if mask & (1 << i)]
        exact, heuristic = optimum(edges), greedy(edges)
        cost = sum(COSTS[v] for v in exact)
        heuristic_cost = sum(COSTS[v] for v in heuristic)
        if not verify(edges, exact, cost):
            raise ValueError('independent witness rejected')
        rows.append({'mask': mask, 'edges': edges, 'optimal_guards': exact,
                     'optimal_cost': cost, 'greedy_guards': heuristic,
                     'greedy_cost': heuristic_cost,
                     'savings': heuristic_cost - cost})
    worse = [r for r in rows if r['savings'] > 0]
    return {'schema_version': 1, 'experiment': 'security-guard-cuts-v1',
            'source_head_sha': os.environ.get('RESEARCH_HEAD_SHA'),
            'producer_run_id': os.environ.get('GITHUB_RUN_ID'),
            'graphs_checked': len(rows), 'witnesses_verified': len(rows),
            'graphs_where_greedy_costs_more': len(worse),
            'maximum_cost_savings': max(r['savings'] for r in rows),
            'counterexample': max(rows, key=lambda r: r['savings']),
            'all_results': rows, 'network_operations': 0,
            'novel_mathematics_claimed': False, 'real_system_security_certified': False,
            'promotion_authority': False,
            'scope': 'Complete enumeration of this bounded abstract DAG family; not executable-program security.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('-o', '--output', type=Path, required=True)
    args = p.parse_args()
    report = experiment()
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'all_results'}))


if __name__ == '__main__':
    main()
