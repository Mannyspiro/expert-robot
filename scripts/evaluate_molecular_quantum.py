#!/usr/bin/env python3
"""Conservative small-molecule quantum baseline: two restricted HF bases.

Consumes only the CACE sanitized molecular Matter Graph (NOT crystals).
Single neutral closed-shell small molecule, <=16 atoms, 2 basis sets.
Convergence plus basis sensitivity are reported as approximations, not
independent chemistry validation or synthetic/manufacturing evidence.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path


ATOMIC_NUMBER={"H":1,"C":6,"N":7,"O":8,"F":9,"P":15,"S":16,"Cl":17}
BASIS=("sto-3g","6-31g")


def baseline(matter_graph):
    try:
        from pyscf import gto, scf, __version__ as pyscf_version
    except ImportError as exc:
        raise RuntimeError("PySCF 2.14.0 required") from exc

    if matter_graph.get("schema_version")!="0.1":
        raise ValueError("unsupported matter graph version")
    nodes=matter_graph.get("nodes",[])
    bonds=[e for e in matter_graph.get("edges",[]) if e.get("relation")=="bonded_to"]
    if not 2 <= len(nodes) <= 16 or not bonds:
        raise ValueError("only bonded 2..16-atom molecules supported")
    if any(a.get("kind")!="atom" for a in nodes):
        raise ValueError("only molecular atomic nodes supported; not a crystal")
    if not matter_graph.get("verification",{}).get("chemistry_validity"):
        raise ValueError("upstream molecule sanitization must pass")
    if not matter_graph.get("verification",{}).get("geometry_validity"):
        raise ValueError("upstream molecular coordinates not qualified")

    atoms=[]
    charge=0
    for atom in nodes:
        symbol=atom.get("element")
        if symbol not in ATOMIC_NUMBER:
            raise ValueError("unsupported atom for HF baseline")
        charge+=int(atom.get("formal_charge") or 0)
        pos=atom.get("position")
        if not isinstance(pos,list) or len(pos)!=3 or atom.get("metadata",{}).get("position_unit")!="angstrom":
            raise ValueError("quantum input requires 3D angstrom coordinates")
        point=[float(x) for x in pos]
        if not all(math.isfinite(x) for x in point):
            raise ValueError("nonfinite quantum geometry")
        atoms.append((symbol,tuple(point)))
    if charge != 0:
        raise ValueError("charged molecules need separate electronic qualification")
    electrons=sum(ATOMIC_NUMBER[sym] for sym,_ in atoms)
    if electrons % 2:
        raise ValueError("open-shell systems need separate spin qualification")

    values=[]
    for basis in BASIS:
        mol=gto.M(
            atom=atoms,
            basis=basis,
            charge=0,
            spin=0,
            unit="Angstrom",
            verbose=0,
            max_memory=384,
        )
        solver=scf.RHF(mol)
        solver.conv_tol=1e-9
        solver.max_cycle=50
        solver.verbose=0
        energy=float(solver.kernel())
        if not solver.converged or not math.isfinite(energy):
            raise ValueError("RHF failed to converge with "+basis)
        values.append({
            "method":"RHF",
            "basis":basis,
            "total_electronic_energy_hartree":energy,
            "converged":True,
            "basis_functions":int(mol.nao_nr()),
            "electrons":int(mol.nelectron),
        })
    if not values[1]["basis_functions"] > values[0]["basis_functions"]:
        raise ValueError("basis function count unexpectedly did not increase")
    result={
        "schema_version":1,
        "matter_id":matter_graph["matter_id"],
        "input_graph_sha256":hashlib.sha256(json.dumps(
            matter_graph,sort_keys=True,separators=(",",":")
        ).encode()).hexdigest(),
        "pyscf_version":str(pyscf_version),
        "scf_results":values,
        "basis_energy_difference_hartree":values[1]["total_electronic_energy_hartree"]-values[0]["total_electronic_energy_hartree"],
        "energy_unit":"Hartree (total electronic plus nuclear-repulsion RHF energy)",
        "epistemic_status":"converged_closed_shell_hf_baseline_not_validated_thermochemistry",
        "readiness":{
            "quantum_calculation_performed":True,
            "independent_methods_agree":False,
            "basis_limit_converged":False,
            "vibrational_stability_qualified":False,
            "thermodynamics_kinetics_qualified":False,
            "synthesizable":False,
            "production_release":False,
        },
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("matter_graph",type=Path)
    p.add_argument("-o","--output",type=Path,required=True)
    args=p.parse_args()
    payload=json.loads(args.matter_graph.read_text(encoding="utf-8"))
    result=baseline(payload)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",
                           encoding="utf-8")
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
