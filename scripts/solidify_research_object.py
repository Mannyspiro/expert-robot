#!/usr/bin/env python3
"""Watertight voxel-proxy solidification for CACE Research Object Foundry.

Union of capped axial struts in a regular grid. Boundary quads are triangulated,
shared vertices are welded by integer grid coordinates, and manifold topology,
orientation, six-connected occupancy, keep-outs and design bounds are checked
independently. This solid is a *voxel approximation* of intended round struts,
not exact curved CAD, a manufacturing approval, or a structural certificate.

Only Python standard library; no NASA/proprietary dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FACES = (
    ((-1, 0, 0), ((0,0,0), (0,0,1), (0,1,1), (0,1,0))),
    ((1, 0, 0), ((1,0,0), (1,1,0), (1,1,1), (1,0,1))),
    ((0,-1, 0), ((0,0,0), (1,0,0), (1,0,1), (0,0,1))),
    ((0, 1, 0), ((0,1,0), (0,1,1), (1,1,1), (1,1,0))),
    ((0, 0,-1), ((0,0,0), (0,1,0), (1,1,0), (1,0,0))),
    ((0, 0, 1), ((0,0,1), (1,0,1), (1,1,1), (0,1,1))),
)


def load_modeler():
    script = ROOT / "scripts" / "generate_research_object_candidates.py"
    spec = importlib.util.spec_from_file_location("object_modeler_v2", script)
    if not spec or not spec.loader:
        raise RuntimeError("cannot load modeler")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def squared_distance_to_segment(point, a, b):
    direction = [b[d] - a[d] for d in range(3)]
    den = sum(x*x for x in direction)
    if den <= 1e-24:
        raise ValueError("zero-length centerline")
    u = max(0.0, min(1.0, sum((point[d]-a[d])*direction[d]
                               for d in range(3)) / den))
    return sum((point[d] - a[d] - u*direction[d])**2 for d in range(3))


def rasterize(candidate, bounds, radius, pitch, max_tests=2500000,
              max_occupied=200000):
    if radius <= 0 or pitch <= 0 or not math.isfinite(pitch):
        raise ValueError("radius and pitch must be finite and positive")
    origin = [float(x) for x in bounds["min"]]
    occupied = set()
    tests = 0
    for first, last in candidate["edges"]:
        a, b = candidate["node_positions_m"][first], candidate["node_positions_m"][last]
        extent_lo = [min(a[d], b[d]) - radius for d in range(3)]
        extent_hi = [max(a[d], b[d]) + radius for d in range(3)]
        intervals = [
            range(math.floor((extent_lo[d]-origin[d])/pitch)-1,
                  math.ceil((extent_hi[d]-origin[d])/pitch)+1)
            for d in range(3)
        ]
        product = math.prod(len(r) for r in intervals)
        tests += product
        if tests > max_tests:
            raise ValueError("voxel candidate exceeds maximum cell-test budget")
        for i in intervals[0]:
            x = origin[0] + (i+0.5)*pitch
            for j in intervals[1]:
                y = origin[1] + (j+0.5)*pitch
                for k in intervals[2]:
                    z = origin[2] + (k+0.5)*pitch
                    if squared_distance_to_segment((x,y,z), a,b) <= radius**2:
                        occupied.add((i,j,k))
                        if len(occupied) > max_occupied:
                            raise ValueError("voxel occupancy exceeds safety limit")
    if not occupied:
        raise ValueError("voxel pitch too coarse to represent struts")
    return occupied, origin


def face_mesh(occupied):
    vertices = []
    vertex_ids = {}
    triangles = []
    for cell in sorted(occupied):
        i,j,k = cell
        for delta, quad in FACES:
            other = (i+delta[0],j+delta[1],k+delta[2])
            if other in occupied:
                continue
            qids = []
            for ox,oy,oz in quad:
                p = (i+ox,j+oy,k+oz)
                if p not in vertex_ids:
                    vertex_ids[p] = len(vertices)
                    vertices.append(p)
                qids.append(vertex_ids[p])
            triangles.append((qids[0],qids[1],qids[2]))
            triangles.append((qids[0],qids[2],qids[3]))
    return vertices, triangles


def connected_cells(occupied):
    first = next(iter(occupied))
    seen, queue = {first}, deque([first])
    while queue:
        i,j,k = queue.popleft()
        for delta, _ in FACES:
            nxt=(i+delta[0],j+delta[1],k+delta[2])
            if nxt in occupied and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return len(seen)==len(occupied)


def check_surface(vertices, triangles):
    if not vertices or not triangles:
        raise ValueError("empty surface")
    directed, edges = Counter(), Counter()
    link = defaultdict(lambda: defaultdict(set))
    for a,b,c in triangles:
        if len({a,b,c}) != 3:
            raise ValueError("degenerate surface triangle")
        for u,v in ((a,b),(b,c),(c,a)):
            directed[(u,v)] += 1
            edges[tuple(sorted((u,v)))] += 1
        for v,u,w in ((a,b,c),(b,a,c),(c,a,b)):
            link[v][u].add(w)
            link[v][w].add(u)
    if any(count!=2 for count in edges.values()):
        raise ValueError("surface has open or nonmanifold edges")
    if any(directed[(b,a)]!=1 or count!=1
           for (a,b),count in directed.items()):
        raise ValueError("surface has non-opposed triangle winding")
    # Each vertex link must form ONE cycle; two objects touching only at a
    # vertex are not a 2-manifold even if all edge incidences look correct.
    for vertex, neighbors in link.items():
        if any(len(v)!=2 for v in neighbors.values()):
            raise ValueError(f"nonmanifold vertex {vertex}: invalid link degree")
        seed=next(iter(neighbors))
        visited={seed}
        stack=[seed]
        while stack:
            current=stack.pop()
            for nxt in neighbors[current]-visited:
                visited.add(nxt)
                stack.append(nxt)
        if len(visited)!=len(neighbors):
            raise ValueError(f"nonmanifold vertex {vertex}: split vertex link")
    six_vol = 0
    for a,b,c in triangles:
        u,v,w=vertices[a],vertices[b],vertices[c]
        six_vol += (u[0]*(v[1]*w[2]-v[2]*w[1]) +
                    u[1]*(v[2]*w[0]-v[0]*w[2]) +
                    u[2]*(v[0]*w[1]-v[1]*w[0]))
    if six_vol<=0:
        raise ValueError("incorrect surface orientation / nonpositive volume")
    return {"surface_closed_and_oriented":True,
            "manifold_vertex_links":True,
            "signed_voxel_volume":six_vol/6}


def box_intersect(cell, origin, pitch, lo, hi):
    # Inclusive AABB intersection: touching a keep-out counts as intrusion.
    for axis in range(3):
        a=origin[axis]+cell[axis]*pitch
        b=a+pitch
        if b<lo[axis]-1e-14 or a>hi[axis]+1e-14:
            return False
    return True


def validate_cells(occupied, origin, pitch, spec, candidate):
    bounds=spec["design_space"]["bounds"]
    eps=1e-13
    for cell in occupied:
        for d in range(3):
            lo=origin[d]+cell[d]*pitch
            if lo < bounds["min"][d]-eps or lo+pitch > bounds["max"][d]+eps:
                raise ValueError("voxelized solid extends beyond design bounds")
    catalog={x["id"]:x for x in spec.get("geometry_catalog",{}).get("obstacle_boxes",[])}
    for ref in spec.get("obstacle_geometry",[]):
        box=catalog[ref["geometry_ref"]]
        clearance=float(ref["clearance_m"])
        lo=[box["min_xyz_m"][i]-clearance for i in range(3)]
        hi=[box["max_xyz_m"][i]+clearance for i in range(3)]
        if any(box_intersect(cell,origin,pitch,lo,hi) for cell in occupied):
            raise ValueError("voxelized solid intrudes on expanded obstacle")
    # A preserved interface must lie in the actual union of occupied cells,
    # not merely appear in the original strut graph.
    for ref in spec["preserve_geometry"]:
        p=candidate["node_positions_m"][ref["geometry_ref"]]
        idx=tuple(math.floor((p[d]-origin[d])/pitch) for d in range(3))
        neighboring=[(idx[0]+i,idx[1]+j,idx[2]+k)
                     for i in (-1,0,1) for j in (-1,0,1) for k in (-1,0,1)]
        if not any(all(origin[d]+v[d]*pitch-eps <= p[d] <=
                       origin[d]+(v[d]+1)*pitch+eps for d in range(3))
                   for v in neighboring if v in occupied):
            raise ValueError("preserved interface not contained in voxelized solid")


def obj_text(vertices, triangles, origin, pitch, candidate_name):
    out=["# CACE watertight voxel proxy (manifold validated)",
         "# This is an approximate cubic solid, NOT certified for fabrication or FEA",
         "o voxel_"+candidate_name]
    for grid in vertices:
        xyz=[origin[d]+grid[d]*pitch for d in range(3)]
        out.append("v "+" ".join(f"{x:.12g}" for x in xyz))
    for tri in triangles:
        out.append("f "+" ".join(str(i+1) for i in tri))
    return "\n".join(out)+"\n"


def build(spec, candidate=None, pitch=None):
    modeler=load_modeler()
    candidates=modeler.generate(spec)
    diameter=candidates["assumed_minimum_strut_diameter_m"]
    if diameter<=0:
        raise ValueError("minimum_feature_m > 0 required to form a solid")
    spacing=float(pitch) if pitch is not None else diameter/3
    if spacing>diameter/2 or spacing<=0 or not math.isfinite(spacing):
        raise ValueError("pitch must be positive and at most half the diameter")
    selected=candidates["ranked_survivors"]
    if candidate is not None:
        selected=[c for c in selected if c["candidate_id"]==candidate]
        if not selected:
            raise ValueError("requested candidate is not geometrically feasible")
    failures=[]
    for c in selected:
        try:
            occupied, origin=rasterize(
                c,spec["design_space"]["bounds"],diameter/2,spacing
            )
            validate_cells(occupied,origin,spacing,spec,c)
            if not connected_cells(occupied):
                raise ValueError("voxelized solid is disconnected")
            vertices,triangles=face_mesh(occupied)
            topology=check_surface(vertices,triangles)
            if not math.isclose(topology["signed_voxel_volume"],len(occupied),
                                rel_tol=1e-10,abs_tol=1e-7):
                raise ValueError("surface integral does not match voxel occupancy")
            volume=len(occupied)*spacing**3
            mat=next((m for m in spec["materials"]
                      if m.get("density_kg_m3") is not None),None)
            mass=volume*float(mat["density_kg_m3"]) if mat else None
            limit=spec.get("constraints",{}).get("maximum_mass_kg")
            if mass is not None and limit is not None and mass>float(limit):
                raise ValueError("solid voxel mass exceeds specified maximum")
            mesh=obj_text(vertices,triangles,origin,spacing,c["candidate_id"])
            return {
                "schema_version":1,
                "object_id":spec["object_id"],
                "candidate_id":c["candidate_id"],
                "pitch_m":spacing,
                "assumed_strut_diameter_m":diameter,
                "occupied_voxels":len(occupied),
                "vertex_count":len(vertices),
                "triangle_count":len(triangles),
                "watertight":True,
                "six_connected":True,
                "oriented_manifold":True,
                "bounds_and_keepouts_checked":True,
                "preserve_points_contained":True,
                "signed_volume_m3":volume,
                "mass_kg":mass,
                "sha256_obj":hashlib.sha256(mesh.encode()).hexdigest(),
                "evidence_ceiling":"watertight_voxel_proxy_not_load_or_manufacturing_certified",
                "candidate_failures":failures,
                "obj":mesh,
            }
        except ValueError as exc:
            failures.append({"candidate_id":c["candidate_id"],"reason":str(exc)})
            if candidate is not None:
                raise
    raise ValueError("No candidate passed solid checks: "+json.dumps(failures))


def main():
    p=argparse.ArgumentParser()
    p.add_argument("spec",type=Path)
    p.add_argument("--candidate")
    p.add_argument("--pitch",type=float)
    p.add_argument("-o","--output",type=Path,required=True)
    p.add_argument("--report",type=Path)
    args=p.parse_args()
    report=build(json.loads(args.spec.read_text(encoding="utf-8")),
                 args.candidate,args.pitch)
    args.output.write_text(report["obj"],encoding="utf-8")
    summary={k:v for k,v in report.items() if k!="obj"}
    if args.report:
        args.report.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",
                               encoding="utf-8")
    print(json.dumps(summary,sort_keys=True))


if __name__=="__main__":
    main()
