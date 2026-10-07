#!/usr/bin/env python3
"""Counterexample search for CACE UniformRefinementND h_max recurrence.

Runs multiple deterministic conforming 1D/2D meshes through the actual CACE
UniformRefinementND implementation and checks whether h_max(refine M)=h_max(M)/2.
This is empirical screening, not proof.
"""

from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path


def edge_key(a,b):
    return tuple(sorted((int(a),int(b))))


def mesh_edges(mesh):
    edges=set()
    for cell in mesh["elements"]:
        if len(cell)==2:
            edges.add(edge_key(cell[0],cell[1]))
        elif len(cell)==3:
            edges.add(edge_key(cell[0],cell[1]))
            edges.add(edge_key(cell[1],cell[2]))
            edges.add(edge_key(cell[2],cell[0]))
        else:
            raise ValueError("only 1D segments and 2D triangles are supported")
    return sorted(edges)


def hmax(mesh):
    vertices=mesh["vertices"]
    best=0.0
    for a,b in mesh_edges(mesh):
        pa,pb=vertices[a],vertices[b]
        d=math.sqrt(sum((float(x)-float(y))**2 for x,y in zip(pa,pb)))
        best=max(best,d)
    return best


def cases():
    return [
      ("segment_unit", [[0.0],[1.0]], [[0,1]]),
      ("segment_shifted", [[-3.0],[5.0]], [[0,1]]),
      ("triangle_right", [[0.0,0.0],[1.0,0.0],[0.0,1.0]], [[0,1,2]]),
      ("triangle_scalene", [[0.0,0.0],[3.0,0.0],[0.4,1.7]], [[0,1,2]]),
      ("triangle_obtuse", [[0.0,0.0],[4.0,0.0],[0.5,0.2]], [[0,1,2]]),
      ("square_two_triangles", [[0.0,0.0],[2.0,0.0],[2.0,1.0],[0.0,1.0]], [[0,1,2],[0,2,3]]),
      ("irregular_fan", [[0.0,0.0],[3.0,0.0],[2.2,1.8],[-0.2,1.3],[1.1,0.7]], [[0,1,4],[1,2,4],[2,3,4],[3,0,4]]),
      ("nonuniform_patch", [[0.0,0.0],[4.0,0.0],[4.0,1.0],[1.0,1.0],[0.0,3.0]], [[0,1,3],[1,2,3],[0,3,4]]),
    ]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("cace_root",type=Path)
    p.add_argument("-o","--output",type=Path)
    args=p.parse_args()

    sys.path.insert(0,str(args.cace_root))
    from cace_studio.modules.fem_nd import SimplexMeshND, UniformRefinementND

    rows=[]
    failures=[]
    for name,vertices,elements in cases():
        mesh_mod=SimplexMeshND()
        mesh_out=mesh_mod.execute({},{"vertices":vertices,"elements":elements},{})
        mesh=mesh_out["mesh"]
        refined=UniformRefinementND().execute({"mesh":mesh},{},{})["refined_mesh"]
        h0=hmax(mesh)
        h1=hmax(refined)
        ratio=h1/h0
        passed=math.isclose(ratio,0.5,rel_tol=1e-12,abs_tol=1e-12)
        row={"case":name,"dimension":mesh["dimension"],"h0":h0,"h1":h1,"ratio":ratio,"passed":passed}
        rows.append(row)
        if not passed:
            failures.append(row)

    result={
      "schema_version":1,
      "cace_commit":"0e7aa229d3bb57174e281b883ee8af5445f15f75",
      "candidate":"hmax(uniform_refine(mesh)) = hmax(mesh)/2",
      "cases":rows,
      "counterexamples_found":len(failures),
      "failures":failures,
      "epistemic_status":"counterexample_search_not_proof"
    }
    rendered=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.write_text(rendered,encoding="utf-8")
    else:
        print(rendered,end="")
    if failures:
        raise SystemExit(1)


if __name__=="__main__":
    main()
