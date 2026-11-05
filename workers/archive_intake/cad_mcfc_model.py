#!/usr/bin/env python3
"""CAD/MCFC metadata, affine frame transforms, simulation provenance and wiring graph."""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path

def validate_matrix(m):
    if not isinstance(m,list) or len(m)!=4 or any(not isinstance(r,list) or len(r)!=4 for r in m):
        raise ValueError("transform must be a 4x4 matrix")
    if any(not isinstance(x,(int,float)) or not math.isfinite(x) for row in m for x in row):
        raise ValueError("transform entries must be finite numbers")
    if any(abs(m[3][i]-(1.0 if i==3 else 0.0))>1e-9 for i in range(4)):
        raise ValueError("transform must be affine with homogeneous final row [0,0,0,1]")
    return m

def determinant3(a):
    return (a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])
      -a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])
      +a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))

def validate_rigid(m,tol=1e-7):
    validate_matrix(m); r=[row[:3] for row in m[:3]]
    for i in range(3):
        for j in range(3):
            dot=sum(r[k][i]*r[k][j] for k in range(3))
            if abs(dot-(1 if i==j else 0))>tol: raise ValueError("rotation block is not orthonormal")
    if abs(determinant3(r)-1)>tol: raise ValueError("rigid transform must be proper rotation (determinant +1)")
    return m

def multiply(a,b):
    validate_matrix(a); validate_matrix(b)
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

def transform_point(m,p):
    validate_matrix(m)
    if len(p)!=3 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in p):
        raise ValueError("point must contain three finite coordinates")
    v=[*p,1.0]; out=[sum(m[i][j]*v[j] for j in range(4)) for i in range(4)]
    if abs(out[3])<1e-12: raise ValueError("point mapped to infinity")
    return [x/out[3] for x in out[:3]]

def validate_simulation(meta):
    required=("solver","solver_version","model_sha256","input_sha256","units","parameters","boundary_conditions")
    if any(k not in meta for k in required): raise ValueError("simulation metadata missing required fields")
    for k in ("model_sha256","input_sha256"):
        if len(meta[k])!=64 or any(c not in "0123456789abcdef" for c in meta[k]): raise ValueError("invalid "+k)
    return {**meta,"metadata_version":"1.0","status":"not_verified"}

def validate_wiring(connections):
    seen=set(); nets={}
    for c in connections:
        for k in ("connection_id","from_node","from_pin","to_node","to_pin","net_name"):
            if not isinstance(c.get(k),str) or not c[k].strip(): raise ValueError("missing wiring field "+k)
        key=(c["from_node"],c["from_pin"])
        if key in seen: raise ValueError("output/input pin reused; declare a junction or bus explicitly")
        seen.add(key); nets.setdefault(c["net_name"],[]).append([c["from_node"],c["from_pin"],c["to_node"],c["to_pin"]])
    return {"wiring_version":"1.0","connections":connections,"nets":nets}

def main():
    p=argparse.ArgumentParser(); p.add_argument("metadata",type=Path); p.add_argument("--out",type=Path,required=True)
    a=p.parse_args(); data=json.loads(a.metadata.read_text())
    if data.get("kind")=="simulation": result=validate_simulation(data["metadata"])
    elif data.get("kind")=="wiring": result=validate_wiring(data["connections"])
    elif data.get("kind")=="transform":
        m=validate_matrix(data["matrix"]); result={"transform":m,"mapped_point":transform_point(m,data["point"])}
    else: raise SystemExit("kind must be simulation, wiring or transform")
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":"validated_metadata_only","out":str(a.out)}))
if __name__=="__main__": main()
