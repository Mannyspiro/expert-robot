#!/usr/bin/env python3
"""Export a CACE Foundry strut graph as a triangulated OBJ concept preview.

Every edge becomes a capped cylinder with the selected preview diameter.
Overlapping joints are NOT boolean-unioned; output is not a manifold solid,
a validated CAD assembly, or suitable for manufacturing/FEA certification.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_modeler():
    path = ROOT / "scripts" / "generate_research_object_candidates.py"
    spec = importlib.util.spec_from_file_location("research_object_modeler", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


def unit(v):
    length = math.sqrt(dot(v, v))
    if length <= 1e-12:
        raise ValueError("zero length edge")
    return tuple(x/length for x in v)


def cylinder(a, b, radius, segments, offset):
    axis = unit(tuple(b[i] - a[i] for i in range(3)))
    reference = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = unit(cross(axis, reference))
    v = cross(axis, u)
    vertices = []
    for center in (a, b):
        for i in range(segments):
            angle = 2*math.pi*i/segments
            vertices.append(tuple(
                center[k] + radius*(
                    math.cos(angle)*u[k] + math.sin(angle)*v[k]
                )
                for k in range(3)
            ))

    faces = []
    for i in range(segments):
        j = (i+1) % segments
        faces.append((offset+i, offset+j, offset+segments+j))
        faces.append((offset+i, offset+segments+j, offset+segments+i))
    # Triangulate both end caps (fan); closed cylinders can overlap at joints.
    for i in range(1, segments-1):
        faces.append((offset, offset+i+1, offset+i))
        faces.append((offset+segments, offset+segments+i, offset+segments+i+1))
    return vertices, faces


def render(candidate, diameter, sides=12):
    if not candidate["feasible_geometric_graph"]:
        raise ValueError("refusing export of geometrically infeasible candidate")
    if not (3 <= sides <= 64):
        raise ValueError("sides must be between 3 and 64")
    if diameter <= 0 or not math.isfinite(diameter):
        raise ValueError("preview strut diameter must be positive")
    nodes = candidate["node_positions_m"]
    lines = [
        "# CACE Research Object Foundry preview mesh",
        "# Triangulated struts, non-booleaned overlapping joints",
        "# NOT a certified/manufacturing-ready solid or FEA mesh",
        "o " + candidate["candidate_id"],
    ]
    vertex_count = 0
    face_count = 0
    for edge_index, (a, b) in enumerate(candidate["edges"]):
        if a not in nodes or b not in nodes:
            raise ValueError("edge references unknown geometry node")
        vertices, faces = cylinder(
            nodes[a], nodes[b], diameter/2, sides, vertex_count+1
        )
        lines.append(f"g strut_{edge_index:03d}")
        for xyz in vertices:
            lines.append("v " + " ".join(f"{p:.12g}" for p in xyz))
        for face in faces:
            lines.append("f " + " ".join(str(idx) for idx in face))
        vertex_count += len(vertices)
        face_count += len(faces)
    return {
        "obj": "\n".join(lines) + "\n",
        "vertices": vertex_count,
        "triangles": face_count,
        "edges": len(candidate["edges"]),
        "evidence_ceiling": "visualization_only_nonunioned_cylinder_solid_proxy",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("spec", type=Path, help="research_object_spec JSON")
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--candidate", default=None)
    p.add_argument("--sides", type=int, default=12)
    args = p.parse_args()
    modeler = load_modeler()
    data = json.loads(args.spec.read_text(encoding="utf-8"))
    result = modeler.generate(data)
    if not result["ranked_survivors"]:
        raise SystemExit("No feasible geometric candidate to preview")
    candidate = (
        next((c for c in result["ranked_survivors"]
              if c["candidate_id"] == args.candidate), None)
        if args.candidate else result["ranked_survivors"][0]
    )
    if candidate is None:
        raise SystemExit(f"No feasible candidate named {args.candidate}")
    diameter = result["assumed_minimum_strut_diameter_m"]
    output = render(candidate, diameter, args.sides)
    args.output.write_text(output["obj"], encoding="utf-8")
    print(json.dumps({
        "candidate_id": candidate["candidate_id"],
        "edges": output["edges"],
        "vertices": output["vertices"],
        "triangles": output["triangles"],
        "evidence_ceiling": output["evidence_ceiling"],
        "output": str(args.output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
