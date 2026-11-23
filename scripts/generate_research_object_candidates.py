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
import hashlib
import importlib.util
from pathlib import Path
from typing import Any


_ROUTING_FILE = Path(__file__).resolve().parent / "research_object_routing.py"
_ROUTING_SPEC = importlib.util.spec_from_file_location("research_object_routing", _ROUTING_FILE)
_routing = importlib.util.module_from_spec(_ROUTING_SPEC)
assert _ROUTING_SPEC.loader is not None
_ROUTING_SPEC.loader.exec_module(_routing)

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

    bounds_raw = spec["design_space"]["bounds"]
    bounds = {
        "min": [float(x) for x in bounds_raw["min"]],
        "max": [float(x) for x in bounds_raw["max"]],
    }
    if any(not math.isfinite(x) for vec in bounds.values() for x in vec):
        raise ValueError("nonfinite design bounds")
    if any(bounds["min"][i] >= bounds["max"][i] for i in range(3)):
        raise ValueError("invalid design bounds")

    ids = sorted(set(preserve_ids))
    if len(ids) < 2 or len(ids) != len(preserve_ids):
        raise ValueError("preserve refs must identify at least two distinct points")
    if any(not _routing.inside(point_map[x], bounds) for x in ids):
        raise ValueError("preserved interface outside design bounds")
    if any(not all(math.isfinite(v) for v in p) for p in point_map.values()):
        raise ValueError("nonfinite point coordinates")
    if any(dist(point_map[a], point_map[b]) < 1e-12
           for i,a in enumerate(ids) for b in ids[i+1:]):
        raise ValueError("coincident preserved interfaces")

    feature = spec.get("constraints", {}).get("minimum_feature_m")
    diameter = float(feature) if feature is not None else 0.0
    if not math.isfinite(diameter) or diameter < 0:
        raise ValueError("invalid minimum feature diameter")
    radius = diameter / 2
    material = next((m for m in spec.get("materials", [])
                     if m.get("density_kg_m3") is not None), None)
    density = float(material["density_kg_m3"]) if material else None
    if density is not None and (not math.isfinite(density) or density <= 0):
        raise ValueError("invalid density")

    catalog_boxes = catalog.get("obstacle_boxes", [])
    obstacle_catalog = {x["id"]:x for x in catalog_boxes}
    if len(obstacle_catalog) != len(catalog_boxes):
        raise ValueError("obstacle IDs must be unique")
    obstacles = []
    for ref in spec.get("obstacle_geometry", []):
        oid = ref["geometry_ref"]
        if oid not in obstacle_catalog:
            raise ValueError(f"unknown obstacle ref {oid!r}")
        row = dict(obstacle_catalog[oid])
        low, high = row["min_xyz_m"], row["max_xyz_m"]
        if any(not all(math.isfinite(float(v)) for v in coords)
               for coords in (low, high)):
            raise ValueError("nonfinite obstacle bounds")
        if any(low[i] >= high[i] for i in range(3)):
            raise ValueError("inverted obstacle bounds")
        # Strut-centerline exclusion expands requested clearance by the
        # assumed minimum solid radius. A full joint/solid check remains due.
        clearance = float(ref["clearance_m"])
        if not math.isfinite(clearance) or clearance < 0:
            raise ValueError("invalid obstacle clearance")
        row["clearance_m"] = clearance + radius
        obstacles.append(row)
    if any(blocked(point_map[x], point_map[x], obstacles) for x in ids):
        raise ValueError("preserved interface intersects an expanded keep-out")

    maximum_mass = spec.get("constraints", {}).get("maximum_mass_kg")
    candidates = []

    def append(name, points, edges):
        result = candidate(name, points, edges, obstacles)
        used = set(ids) | {v for e in edges for v in e}
        # Restrict connectivity to used nodes, retaining all required terminals.
        valid_nodes = sorted(used)
        outside = [x for x in valid_nodes if not _routing.inside(points[x], bounds)]
        result["connected"] = connectivity(valid_nodes, result["edges"])
        result["preserves_all_interfaces"] = all(x in valid_nodes for x in ids)
        result["out_of_bounds_nodes"] = outside
        result["node_positions_m"] = {k: points[k] for k in valid_nodes}
        result["bridge_count"] = _routing.bridge_count(valid_nodes, result["edges"])
        length = result["total_strut_length_m"]
        result["estimated_cylinder_volume_m3"] = length * math.pi * radius ** 2
        result["mass_proxy_kg"] = (
            result["estimated_cylinder_volume_m3"] * density
            if density is not None else None
        )
        result["mass_proxy_below_maximum"] = (
            None if maximum_mass is None or density is None
            else result["mass_proxy_kg"] <= float(maximum_mass)
        )
        result["feasible_geometric_graph"] = (
            result["connected"] and result["preserves_all_interfaces"]
            and not outside and result["obstacle_violation_count"] == 0
        )
        candidates.append(result)

    append("complete_graph", point_map, pairwise_edges(ids))
    append("nearest_tree", point_map, nearest_tree(ids, point_map))
    if len(ids) >= 3:
        append("ring", point_map, ring_edges(ids, point_map))
    star_map, star_edges = star_with_centroid(ids, point_map)
    append("centroid_star", star_map, star_edges)
    routed_points, routed_edges = _routing.routed_graph(
        ids, point_map, obstacles, bounds, blocked, ring=False
    )
    append("obstacle_aware_tree", routed_points, routed_edges)
    if len(ids) >= 3:
        loop_points, loop_edges = _routing.routed_graph(
            ids, point_map, obstacles, bounds, blocked, ring=True
        )
        append("obstacle_aware_loop", loop_points, loop_edges)

    survivors = [x for x in candidates if x["feasible_geometric_graph"]]
    survivors.sort(key=lambda x: (
        x["total_strut_length_m"], x["bridge_count"],
        x["edge_count"], x["candidate_id"]
    ))
    for c in survivors:
        signature = json.dumps(
            [c["node_positions_m"], c["edges"]],
            sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        c["topology_sha256"] = hashlib.sha256(signature).hexdigest()

    return {
        "schema_version": 2,
        "object_id": spec["object_id"],
        "generator": "cace_research_object_topology_v0.2",
        "candidate_count": len(candidates),
        "survivor_count": len(survivors),
        "candidates": candidates,
        "ranked_survivors": survivors,
        "pareto_candidate_ids": _routing.pareto_ids(survivors),
        "assumed_minimum_strut_diameter_m": diameter,
        "next_stage": [
            "solidify graph and recheck complete tube/joint geometry",
            "mesh and solve with CACE FEM/multiphysics",
            "compute certified residual and a-posteriori error",
            "evaluate load cases, actual mass, manufacturability and holdout",
        ],
        "evidence_ceiling": "pre_fea_topology_generation",
        "limitations": [
            "mass proxy treats struts as cylinders without joint overlap",
            "3D obstacle exclusion applies to strut centerlines with radius margin",
            "not yet a structural or manufacturing certificate",
        ],
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
