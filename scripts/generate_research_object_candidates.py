#!/usr/bin/env python3
"""Generate topology candidates for CACE Research Object Foundry.

This is an independent, permissive-core implementation inspired by public
preserve/obstacle/requirements workflows. It does not copy proprietary
generative-design algorithms.

Current alpha scope:
- preserve points;
- axis-aligned obstacle boxes with clearance;
- candidate strut graphs;
- deterministic legality/connectivity/length proxies;
- CACE-ready candidate records.

Real structural validity still requires CACE FEA/certification.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def dist(a,b):
    return math.sqrt(sum((a[i]-b[i])**2 for i in range(3)))


def centroid(points):
    n=len(points)
    return [sum(p[i] for p in points)/n for i in range(3)]


def segment_intersects_box(a,b,lo,hi,clearance=0.0):
    """3D slab test; touching expanded obstacle counts as blocked."""
    lo=[lo[i]-clearance for i in range(3)]
    hi=[hi[i]+clearance for i in range(3)]
    t0,t1=0.0,1.0
    for i in range(3):
        d=b[i]-a[i]
        if abs(d)<1e-15:
            # Parallel to a slab: outside one axis excludes the box,
            # inside this axis imposes no additional t constraint.
            if a[i]<lo[i] or a[i]>hi[i]:
                return False
            continue
        inv=1.0/d
        ta=(lo[i]-a[i])*inv
        tb=(hi[i]-a[i])*inv
        if ta>tb: ta,tb=tb,ta
        t0=max(t0,ta)
        t1=min(t1,tb)
        if t0>t1:
            return False
    return True


def blocked(a,b,obstacles):
    for obs in obstacles:
        if segment_intersects_box(
            a,b,obs["min_xyz_m"],obs["max_xyz_m"],float(obs.get("clearance_m",0.0))
        ):
            return obs["id"]
    return None


def connectivity(nodes,edges):
    if not nodes:
        return False
    graph={n:set() for n in nodes}
    for a,b in edges:
        graph[a].add(b); graph[b].add(a)
    seen={nodes[0]}
    stack=[nodes[0]]
    while stack:
        x=stack.pop()
        for y in graph[x]:
            if y not in seen:
                seen.add(y); stack.append(y)
    return len(seen)==len(nodes)


def candidate(name,point_map,edges,obstacles):
    legal=[]
    violations=[]
    length=0.0
    for a,b in edges:
        pa,pb=point_map[a],point_map[b]
        hit=blocked(pa,pb,obstacles)
        if hit:
            violations.append({"edge":[a,b],"obstacle":hit})
        else:
            legal.append([a,b])
            length += dist(pa,pb)
    nodes=sorted(point_map)
    return {
        "candidate_id":name,
        "edges":legal,
        "rejected_edges":violations,
        "connected":connectivity(nodes,legal),
        "total_strut_length_m":length,
        "edge_count":len(legal),
        "obstacle_violation_count":len(violations),
        "evidence_ceiling":"topology_and_geometric_filter_only_not_structural_validation",
    }


def pairwise_edges(ids):
    return [(ids[i],ids[j]) for i in range(len(ids)) for j in range(i+1,len(ids))]


def nearest_tree(ids,point_map):
    if not ids: return []
    connected={ids[0]}
    remaining=set(ids[1:])
    edges=[]
    while remaining:
        best=None
        for a in connected:
            for b in remaining:
                score=dist(point_map[a],point_map[b])
                item=(score,a,b)
                if best is None or item<best:
                    best=item
        _,a,b=best
        edges.append((a,b))
        connected.add(b)
        remaining.remove(b)
    return edges


def ring_edges(ids,point_map):
    c=centroid([point_map[x] for x in ids])
    ordered=sorted(ids,key=lambda x: math.atan2(point_map[x][1]-c[1],point_map[x][0]-c[0]))
    return [(ordered[i],ordered[(i+1)%len(ordered)]) for i in range(len(ordered))]


def star_with_centroid(ids,point_map):
    c=centroid([point_map[x] for x in ids])
    out=dict(point_map)
    out["__centroid__"]=c
    edges=[("__centroid__",x) for x in ids]
    return out,edges


def generate(spec:dict[str,Any])->dict[str,Any]:
    catalog=spec.get("geometry_catalog") or {}
    pts=catalog.get("points") or []
    if len(pts)<2:
        raise ValueError("geometry_catalog.points requires at least two points")
    point_map={x["id"]:[float(v) for v in x["xyz_m"]] for x in pts}
    if len(point_map)!=len(pts):
        raise ValueError("point ids must be unique")

    preserves=spec.get("preserve_geometry",[])
    preserve_ids=[p["geometry_ref"] for p in preserves]
    missing=[x for x in preserve_ids if x not in point_map]
    if missing:
        raise ValueError(f"unknown preserve point refs: {missing}")

    obstacle_catalog={x["id"]:x for x in catalog.get("obstacle_boxes",[])}
    obstacles=[]
    for ref in spec.get("obstacle_geometry",[]):
        oid=ref["geometry_ref"]
        if oid not in obstacle_catalog:
            raise ValueError(f"unknown obstacle ref {oid!r}")
        row=dict(obstacle_catalog[oid])
        row["clearance_m"]=float(ref["clearance_m"])
        obstacles.append(row)

    ids=preserve_ids
    candidates=[]
    candidates.append(candidate("complete_graph",point_map,pairwise_edges(ids),obstacles))
    candidates.append(candidate("nearest_tree",point_map,nearest_tree(ids,point_map),obstacles))
    if len(ids)>=3:
        candidates.append(candidate("ring",point_map,ring_edges(ids,point_map),obstacles))
    star_map,star_edges=star_with_centroid(ids,point_map)
    candidates.append(candidate("centroid_star",star_map,star_edges,obstacles))

    survivors=[c for c in candidates if c["connected"] and c["obstacle_violation_count"]==0]
    survivors.sort(key=lambda c:(c["total_strut_length_m"],c["edge_count"],c["candidate_id"]))

    return {
        "schema_version":1,
        "object_id":spec["object_id"],
        "generator":"cace_research_object_topology_v0.1",
        "candidate_count":len(candidates),
        "survivor_count":len(survivors),
        "candidates":candidates,
        "ranked_survivors":survivors,
        "next_stage":[
            "convert candidate graph to exact/parametric solid geometry",
            "mesh candidate",
            "run CACE structural/multiphysics solve",
            "compute residual and certified error bound",
            "apply manufacturing constraints",
        ],
        "evidence_ceiling":"pre_fea_topology_generation",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("spec",type=Path)
    p.add_argument("-o","--output",type=Path)
    args=p.parse_args()
    spec=json.loads(args.spec.read_text(encoding="utf-8"))
    result=generate(spec)
    rendered=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.write_text(rendered,encoding="utf-8")
    else:
        print(rendered,end="")


if __name__=="__main__":
    main()
