"""Deterministic, bounded graph reasoning for Merlin planning; no execution authority."""
from __future__ import annotations

import heapq
from collections.abc import Mapping


def dependency_order(graph: Mapping[str, tuple[str, ...]], *, limit: int = 10000) -> tuple[str, ...]:
    """Return a stable topological order; reject malformed, missing, or cyclic dependencies.

    graph maps each task to the prerequisite task identifiers. No task is executed.
    """
    if not isinstance(graph, Mapping) or type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError("invalid graph or bound")
    if len(graph) > limit:
        raise ValueError("graph exceeds bound")
    nodes = set(graph)
    if any(not isinstance(node, str) or not node for node in nodes):
        raise ValueError("invalid task identity")
    followers: dict[str, list[str]] = {node: [] for node in nodes}
    degrees: dict[str, int] = {}
    for node, dependencies in graph.items():
        if not isinstance(dependencies, (tuple, list)) or any(not isinstance(dep, str) for dep in dependencies):
            raise ValueError("invalid dependencies")
        if len(dependencies) != len(set(dependencies)):
            raise ValueError("duplicate dependencies")
        if any(dep not in nodes for dep in dependencies):
            raise ValueError("missing prerequisite")
        degrees[node] = len(dependencies)
        for dep in dependencies:
            followers[dep].append(node)
    ready = [node for node, degree in degrees.items() if degree == 0]
    heapq.heapify(ready)
    result = []
    while ready:
        node = heapq.heappop(ready)
        result.append(node)
        for follower in followers[node]:
            degrees[follower] -= 1
            if degrees[follower] == 0:
                heapq.heappush(ready, follower)
    if len(result) != len(nodes):
        raise ValueError("dependency cycle")
    return tuple(result)
