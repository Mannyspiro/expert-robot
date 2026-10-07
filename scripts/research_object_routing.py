"""Deterministic 3D obstacle-aware route generation for CACE strut graph modeler.

Candidate centerlines are geometric hypotheses, not a solid, FEA result or a
certificate. Zero external runtime dependencies.
"""

import heapq
import math


def distance(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def inside(p, bounds):
    return all(bounds["min"][i] <= p[i] <= bounds["max"][i] for i in range(3))


def waypoint_nodes(terminals, points, obstacles, bounds, blocked):
    """Generate obstacle-inflated XY and XYZ detour corners inside the design box."""
    nodes = {k: list(v) for k, v in points.items()}
    size = max(bounds["max"][i] - bounds["min"][i] for i in range(3))
    epsilon = max(1e-7, size * 1e-6)
    heights = sorted(set(points[x][2] for x in terminals))
    for obs in sorted(obstacles, key=lambda o: o["id"]):
        lo = [obs["min_xyz_m"][i] - obs["clearance_m"] - epsilon
              for i in range(3)]
        hi = [obs["max_xyz_m"][i] + obs["clearance_m"] + epsilon
              for i in range(3)]
        positions = []
        for z in heights:
            positions += [[x, y, z] for x in (lo[0], hi[0])
                          for y in (lo[1], hi[1])]
        positions += [[x, y, z] for x in (lo[0], hi[0])
                      for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        distinct = sorted(set(tuple(p) for p in positions))
        for idx, p in enumerate(distinct):
            if inside(p, bounds) and blocked(p, p, obstacles) is None:
                nodes[f"__detour_{obs['id']}_{idx}"] = list(p)
    return nodes


def visibility(nodes, obstacles, bounds, blocked):
    graph = {x: [] for x in nodes}
    keys = sorted(nodes)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            pa, pb = nodes[a], nodes[b]
            if (distance(pa, pb) < 1e-12 or not inside(pa, bounds) or
                    not inside(pb, bounds) or blocked(pa, pb, obstacles) is not None):
                continue
            d = distance(pa, pb)
            graph[a].append((b, d))
            graph[b].append((a, d))
    return graph


def shortest(graph, a, b):
    queue = [(0.0, a, (a,))]
    visited = set()
    while queue:
        cost, node, route = heapq.heappop(queue)
        if node in visited:
            continue
        visited.add(node)
        if node == b:
            return cost, route
        for nxt, w in sorted(graph[node]):
            if nxt not in visited:
                heapq.heappush(queue, (cost + w, nxt, route + (nxt,)))
    return math.inf, ()


def routed_graph(terminals, points, obstacles, bounds, blocked, ring=False):
    """MST over obstacle-avoiding shortest paths or a full routed perimeter."""
    nodes = waypoint_nodes(terminals, points, obstacles, bounds, blocked)
    graph = visibility(nodes, obstacles, bounds, blocked)
    routes = []
    if ring:
        cx = sum(points[x][0] for x in terminals) / len(terminals)
        cy = sum(points[x][1] for x in terminals) / len(terminals)
        order = sorted(terminals, key=lambda x: (
            math.atan2(points[x][1] - cy, points[x][0] - cx), x
        ))
        pairs = [(order[i], order[(i + 1) % len(order)])
                 for i in range(len(order))]
        for a, b in pairs:
            _, route = shortest(graph, a, b)
            if not route:
                return {k: points[k] for k in terminals}, []
            routes.append(route)
    else:
        metric = []
        for i, a in enumerate(terminals):
            for b in terminals[i + 1:]:
                cost, route = shortest(graph, a, b)
                if route:
                    metric.append((cost, a, b, route))
        parent = {k: k for k in terminals}

        def find(x):
            while parent[x] != x:
                x = parent[x]
            return x

        for _, a, b, route in sorted(metric):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
                routes.append(route)
            if len(routes) == len(terminals) - 1:
                break

    edges = sorted(set(
        tuple(sorted((a, b))) for route in routes
        for a, b in zip(route, route[1:])
    ))
    used = set(terminals) | {x for edge in edges for x in edge}
    return {k: nodes[k] for k in sorted(used)}, edges


def bridge_count(nodes, edges):
    """Count graph bridge edges, a topology-only redundancy proxy."""
    graph = {n: set() for n in nodes}
    for a, b in edges:
        graph[a].add(b)
        graph[b].add(a)
    seen, low, parent = {}, {}, {}
    tick, count = 0, 0

    def visit(v):
        nonlocal tick, count
        seen[v] = low[v] = tick
        tick += 1
        for w in sorted(graph[v]):
            if w not in seen:
                parent[w] = v
                visit(w)
                low[v] = min(low[v], low[w])
                if low[w] > seen[v]:
                    count += 1
            elif w != parent.get(v):
                low[v] = min(low[v], seen[w])

    for node in sorted(nodes):
        if node not in seen:
            visit(node)
    return count


def pareto_ids(candidates):
    """Nondominated graph candidates by length and number of bridge edges."""
    out = []
    for a in candidates:
        dominated = any(
            (b["total_strut_length_m"] <= a["total_strut_length_m"] + 1e-12 and
             b["bridge_count"] <= a["bridge_count"] and
             (b["total_strut_length_m"] < a["total_strut_length_m"] - 1e-12
              or b["bridge_count"] < a["bridge_count"]))
            for b in candidates if a is not b
        )
        if not dominated:
            out.append(a["candidate_id"])
    return out
