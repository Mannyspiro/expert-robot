#!/usr/bin/env python3
"""Exhaustive finite directed graph evidence for transfer-walk Lean candidates.

Checks n=1..4 vertices, 0..3 directed edges (including repetitions), all
0/1 vertex weights, an independent SymPy nullspace and undirected BFS.
Not a Lean theorem proof or production CACE benchmark.
"""
import itertools, json
from collections import defaultdict
from sympy import Matrix


def bfs_components(n, edges):
    neighbors=[set() for _ in range(n)]
    for a,b in edges:
        neighbors[a].add(b)
        neighbors[b].add(a)
    visited=set()
    groups=[]
    for vertex in range(n):
        if vertex in visited:
            continue
        stack=[vertex]
        group=set()
        while stack:
            u=stack.pop()
            if u in group:
                continue
            group.add(u)
            stack.extend(neighbors[u]-group)
        visited.update(group)
        groups.append(group)
    return groups


def run():
    counts=defaultdict(int)
    for n in (1,2,3,4):
        all_edges=[(i,j) for i in range(n) for j in range(n) if i!=j]
        for m in range(4):
            for edges in itertools.product(all_edges,repeat=m):
                groups=bfs_components(n,edges)
                stoich=Matrix.zeros(n,m)
                for index,(src,dst) in enumerate(edges):
                    stoich[src,index]=-1
                    stoich[dst,index]=1
                assert len(stoich.T.nullspace())==len(groups)==n-stoich.rank()
                for weights in itertools.product((0,1),repeat=n):
                    edgewise=all(weights[a]==weights[b] for a,b in edges)
                    walkwise=all(len({weights[v] for v in group})==1 for group in groups)
                    all_flux=Matrix([weights])*stoich==Matrix.zeros(1,m)
                    assert edgewise==walkwise==all_flux
                    counts["weight_checks"]+=1
                counts["graph_cases"]+=1
                counts["transfer_edges"]+=m
    assert dict(counts)=={"weight_checks":32294,"graph_cases":2160,"transfer_edges":6244}
    result=dict(counts)
    result.update({"schema_version":1,
                   "experiment":"transfer-walk-exhaustive-small-graph-v1",
                   "max_vertices":4,"max_edges":3,
                   "independent_rank_oracle":"SymPy Matrix.T.nullspace",
                   "distinct_model_scope":"strict directed unit transfers",
                   "lean_kernel_checked":False,
                   "production_cace_qualified":False,
                   "authority_expanded":False})
    return result


if __name__=="__main__":
    print(json.dumps(run()))
