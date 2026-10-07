#!/usr/bin/env python3
"""CACE crystalline-matter prototype: periodic geometry + CIF, no stability claim.

Verifies 3D lattice basis, finite fractional atomic sites, periodic duplicates,
short-range obvious collisions and composition. Writes crystallographic CIF
with P1 symmetry only (no inferred space group). This is NOT an electronic
structure, stability, phonon, synthesis, process, or production certificate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ELEMENTS = set(("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co "
                "Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb "
                "Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re "
                "Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf "
                "Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og").split())
MAX_SITES = 256
MIN_BASIS_ANGLE_DEG = 60.0
MAX_BASIS_ANGLE_DEG = 120.0


def dot(u,v):
    return sum(a*b for a,b in zip(u,v))


def cross(u,v):
    return [u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]


def norm(u):
    return math.sqrt(dot(u,u))


def angle(u,v):
    c=dot(u,v)/(norm(u)*norm(v))
    return math.degrees(math.acos(max(-1,min(1,c))))


def cart(frac,basis):
    return [sum(frac[k]*basis[k][d] for k in range(3)) for d in range(3)]


def validate(payload):
    if payload.get("schema_version") != 1 or not payload.get("crystal_id"):
        raise ValueError("crystal schema_version=1 and crystal_id required")
    basis=payload.get("lattice_vectors_angstrom")
    if not isinstance(basis,list) or len(basis)!=3 or any(
            not isinstance(row,list) or len(row)!=3 for row in basis):
        raise ValueError("three 3D lattice vectors are required")
    try:
        basis=[[float(x) for x in row] for row in basis]
    except (TypeError,ValueError) as exc:
        raise ValueError("lattice vectors must be numerical") from exc
    if any(not math.isfinite(x) for v in basis for x in v):
        raise ValueError("nonfinite lattice vector")
    lengths=[norm(v) for v in basis]
    if any(x < 2.0 or x>1000.0 for x in lengths):
        raise ValueError("unsupported lattice length; expected 2..1000 Å")
    alpha,beta,gamma=(
        angle(basis[1],basis[2]),
        angle(basis[0],basis[2]),
        angle(basis[0],basis[1]),
    )
    if not all(MIN_BASIS_ANGLE_DEG <= a <= MAX_BASIS_ANGLE_DEG
               for a in (alpha,beta,gamma)):
        raise ValueError("extremely skewed cells require a separate image search")
    volume=dot(basis[0],cross(basis[1],basis[2]))
    if volume <= 1e-5:
        raise ValueError("lattice must be right-handed and nonsingular")
    sites=payload.get("sites")
    if not isinstance(sites,list) or not (1<=len(sites)<=MAX_SITES):
        raise ValueError("expected 1..256 crystallographic sites")
    ids=set()
    normalized=[]
    for i,site in enumerate(sites):
        if not isinstance(site,dict) or "id" not in site or "element" not in site:
            raise ValueError("site requires id and element")
        ident,element=site["id"],site["element"]
        if not isinstance(ident,str) or not ident or ident in ids:
            raise ValueError("duplicate or invalid crystallographic site ID")
        ids.add(ident)
        if element not in ELEMENTS:
            raise ValueError("invalid element symbol")
        position=site.get("fractional_position")
        if not isinstance(position,list) or len(position)!=3:
            raise ValueError("site requires a 3D fractional position")
        f=[float(x) for x in position]
        if not all(math.isfinite(x) for x in f):
            raise ValueError("nonfinite fractional position")
        # Allow input on periodic boundary, normalize 1.0 to 0.0;
        # coordinates wildly outside cell are rejected to avoid silent errors.
        if any(x < -1e-9 or x > 1.0+1e-9 for x in f):
            raise ValueError("fractional positions must lie in [0,1]")
        f=[x%1.0 for x in f]
        normalized.append({"id":ident,"element":element,
                           "fractional_position":f,
                           "cartesian_position_angstrom":cart(f,basis)})
    min_distance=math.inf
    for i,a in enumerate(normalized):
        for j,b in enumerate(normalized):
            for x in (-1,0,1):
                for y in (-1,0,1):
                    for z in (-1,0,1):
                        if i==j and (x,y,z)==(0,0,0):
                            continue
                        offset=[a["fractional_position"][k] -
                                b["fractional_position"][k] + (x,y,z)[k]
                                for k in range(3)]
                        distance=norm(cart(offset,basis))
                        min_distance=min(min_distance,distance)
                        if distance < 0.6:
                            raise ValueError(
                                "periodic site overlap or implausible <0.6 Å separation"
                            )
    counts=Counter(x["element"] for x in normalized)
    formula="".join(f"{el}{counts[el] if counts[el]!=1 else ''}"
                    for el in sorted(counts))
    result={
        "schema_version":1,
        "crystal_id":payload["crystal_id"],
        "lattice_vectors_angstrom":basis,
        "cell_lengths_angstrom":lengths,
        "cell_angles_degrees":[alpha,beta,gamma],
        "cell_volume_angstrom3":volume,
        "sites":normalized,
        "formula_per_listed_unit_cell":formula,
        "nearest_periodic_distance_angstrom":min_distance,
        "space_group":"P 1 (export only; no symmetry inference)",
        "readiness":{
            "unit_cell_geometry_screened":True,
            "periodic_site_uniqueness_screened":True,
            "electronic_structure_qualified":False,
            "thermodynamic_phase_stability_qualified":False,
            "phonon_stability_qualified":False,
            "defect_and_surface_models_qualified":False,
            "synthesis_route_verified":False,
            "material_characterization_verified":False,
            "production_release":False,
        },
        "evidence_ceiling":"periodic_crystallographic_geometry_only_not_material_stability",
    }
    return result


def cif_text(result):
    a,b,c=result["cell_lengths_angstrom"]
    alpha,beta,gamma=result["cell_angles_degrees"]
    lines=[
        "data_cace_crystal",
        "_audit_creation_method 'CACE computational geometric prototype'",
        "_symmetry_space_group_name_H-M 'P 1'",
        "_cell_length_a "+f"{a:.9f}",
        "_cell_length_b "+f"{b:.9f}",
        "_cell_length_c "+f"{c:.9f}",
        "_cell_angle_alpha "+f"{alpha:.9f}",
        "_cell_angle_beta "+f"{beta:.9f}",
        "_cell_angle_gamma "+f"{gamma:.9f}",
        "_cell_volume "+f"{result['cell_volume_angstrom3']:.9f}",
        "loop_",
        "_atom_site_label",
        "_atom_site_type_symbol",
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
    ]
    for site in result["sites"]:
        x,y,z=site["fractional_position"]
        # Site id is not arbitrary CIF content: only generated labels.
        label="X"+str(len(lines))
        lines.append(f"{label} {site['element']} {x:.9f} {y:.9f} {z:.9f}")
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("input",type=Path)
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--cif",type=Path,required=True)
    args=p.parse_args()
    result=validate(json.loads(args.input.read_text(encoding="utf-8")))
    cif=cif_text(result)
    result["cif_sha256"]=hashlib.sha256(cif.encode()).hexdigest()
    args.report.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",
                           encoding="utf-8")
    args.cif.write_text(cif,encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items()
                      if k in ("crystal_id","formula_per_listed_unit_cell",
                               "cell_volume_angstrom3","evidence_ceiling",
                               "nearest_periodic_distance_angstrom")},sort_keys=True))


if __name__=="__main__":
    main()
