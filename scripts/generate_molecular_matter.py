#!/usr/bin/env python3
"""CACE molecular Matter Graph v0.2 — bounded RDKit small-molecule route.

This creates computational molecular structures, NOT synthetic recipes,
quantum-chemical certificates, stable compounds, or physical atoms/materials.
Only sanitized single-component organic molecules with an explicit 3D conformer
are accepted. Conformer optimization is an approximate force-field calculation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ALLOWED_ELEMENTS = {"H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"}
MAX_HEAVY_ATOMS = 48
MAX_CONFORMERS = 8


def generate(smiles: str, matter_id: str, conformers: int = 8, seed: int = 1729):
    try:
        from rdkit import Chem, rdBase
        from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
    except ImportError as exc:
        raise RuntimeError("RDKit is required: pip install rdkit==2026.3.6") from exc

    if not isinstance(smiles, str) or len(smiles) > 256 or not smiles.strip():
        raise ValueError("SMILES must be a nonempty string of at most 256 characters")
    if not matter_id:
        raise ValueError("matter_id is required")
    if not (1 <= conformers <= MAX_CONFORMERS):
        raise ValueError("conformers must be 1..8")
    if not (1 <= seed < 2**31):
        raise ValueError("seed must be a positive 31-bit integer")
    if "." in smiles:
        raise ValueError("disconnected mixtures, salts, and counterions are not supported")
    mol = Chem.MolFromSmiles(smiles, sanitize=True)
    if mol is None:
        raise ValueError("SMILES failed RDKit chemistry sanitization")
    if len(Chem.GetMolFrags(mol)) != 1:
        raise ValueError("only one connected molecular component is supported")
    if mol.GetNumHeavyAtoms() > MAX_HEAVY_ATOMS or mol.GetNumHeavyAtoms() == 0:
        raise ValueError("unsupported heavy atom count")
    if any(atom.GetSymbol() not in ALLOWED_ELEMENTS for atom in mol.GetAtoms()):
        raise ValueError("unsupported element")
    if any(atom.GetNumRadicalElectrons() > 0 for atom in mol.GetAtoms()):
        raise ValueError("radicals require a separate electronic-structure route")
    if any(atom.GetIsAromatic() and atom.GetSymbol() not in {"C","N","O","S"}
           for atom in mol.GetAtoms()):
        raise ValueError("unqualified aromatic atom")
    stereos = Chem.FindMolChiralCenters(mol, includeUnassigned=True)
    if any(tag == "?" for _, tag in stereos):
        raise ValueError("unassigned chiral centers; specify stereochemistry")
    canonical = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    # Ensure canonical molecular graph survives round-trip sanitization.
    clean = Chem.MolFromSmiles(canonical, sanitize=True)
    if clean is None or Chem.MolToSmiles(clean, isomericSmiles=True) != canonical:
        raise ValueError("canonical structure round-trip failed")

    with_h = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    params.numThreads = 1
    params.clearConfs = True
    params.pruneRmsThresh = -1.0
    identifiers = list(AllChem.EmbedMultipleConfs(with_h, numConfs=conformers,
                                                    params=params))
    if not identifiers:
        raise ValueError("no valid 3D geometry could be embedded")
    use_mmff = bool(AllChem.MMFFHasAllMoleculeParams(with_h))
    if not use_mmff and not AllChem.UFFHasAllMoleculeParams(with_h):
        raise ValueError("no qualified small-molecule force-field parameters")

    candidates = []
    for cid in identifiers:
        if use_mmff:
            ff = AllChem.MMFFGetMoleculeForceField(
                with_h, AllChem.MMFFGetMoleculeProperties(with_h), confId=cid
            )
            model = "MMFF94"
        else:
            ff = AllChem.UFFGetMoleculeForceField(with_h, confId=cid)
            model = "UFF"
        if ff is None:
            continue
        status = ff.Minimize(maxIts=500)
        energy = float(ff.CalcEnergy())
        if status != 0 or not math.isfinite(energy):
            continue
        conf = with_h.GetConformer(cid)
        atoms = [conf.GetAtomPosition(i) for i in range(with_h.GetNumAtoms())]
        if any(not all(math.isfinite(x) for x in (p.x,p.y,p.z)) for p in atoms):
            continue
        # Flag near-overlaps between non-bonded atom pairs. This is only a
        # gross geometry-screen, not a force-field or QM stability certificate.
        bonded = {
            tuple(sorted((b.GetBeginAtomIdx(),b.GetEndAtomIdx())))
            for b in with_h.GetBonds()
        }
        overlap = False
        for i in range(len(atoms)):
            for j in range(i+1,len(atoms)):
                if (i,j) in bonded:
                    continue
                p,q = atoms[i],atoms[j]
                d2=(p.x-q.x)**2+(p.y-q.y)**2+(p.z-q.z)**2
                if d2 < 0.36:  # < 0.6 Å is an obvious gross clash
                    overlap = True
                    break
            if overlap:
                break
        if not overlap:
            candidates.append((energy,int(cid)))

    if not candidates:
        raise ValueError("no minimized and gross-clash-free conformer")
    best_energy, best_conf_id = min(candidates)
    best = with_h.GetConformer(best_conf_id)
    bond_orders = {
        Chem.BondType.SINGLE:1.0,
        Chem.BondType.DOUBLE:2.0,
        Chem.BondType.TRIPLE:3.0,
        Chem.BondType.AROMATIC:1.5,
    }
    nodes=[]
    for atom in with_h.GetAtoms():
        i=atom.GetIdx()
        p=best.GetAtomPosition(i)
        nodes.append({
            "id":f"a{i}",
            "kind":"atom",
            "element":atom.GetSymbol(),
            "isotope": atom.GetIsotope() or None,
            "formal_charge":atom.GetFormalCharge(),
            "position":[f"{p.x:.9f}",f"{p.y:.9f}",f"{p.z:.9f}"],
            "metadata":{
                "position_unit":"angstrom",
                "atom_index":i,
                "is_aromatic":atom.GetIsAromatic(),
            },
        })
    edges=[]
    for bond in with_h.GetBonds():
        order=bond_orders.get(bond.GetBondType())
        if order is None:
            raise ValueError("unsupported bond order")
        edges.append({
            "source":f"a{bond.GetBeginAtomIdx()}",
            "target":f"a{bond.GetEndAtomIdx()}",
            "relation":"bonded_to",
            "bond_order":order,
            "bond_type":str(bond.GetBondType()),
        })

    output_mol = Chem.Mol(with_h)
    for conf in list(output_mol.GetConformers()):
        if conf.GetId() != best_conf_id:
            output_mol.RemoveConformer(conf.GetId())
    sdf = Chem.MolToMolBlock(output_mol, confId=best_conf_id)
    # Re-import exported explicit-H connection table and validate graph.
    roundtrip = Chem.MolFromMolBlock(sdf, sanitize=True, removeHs=False)
    if roundtrip is None or roundtrip.GetNumAtoms()!=len(nodes) or roundtrip.GetNumBonds()!=len(edges):
        raise ValueError("SDF/MolBlock chemical graph round-trip failed")

    payload = {
        "schema_version":"0.1",
        "matter_id":matter_id,
        "description":"RDKit-sanitized small molecule computational conformer",
        "nodes":nodes,
        "edges":edges,
        "scales":["atomic","molecular"],
        "verification":{
            "chemistry_validity":True,
            "geometry_validity":True,
            "physics_models":[model],
            "provenance_required":True,
            "formal_constraints":[
                "canonical SMILES sanitization and roundtrip passed",
                "single connected component; allowed elements only",
                "explicit hydrogen and bond graph conserved in MolBlock",
                "nonbonded gross clash screen (0.6 angstrom)",
            ],
            "wet_lab_instructions_allowed":False,
        },
    }
    metadata = {
        "schema_version":1,
        "matter_id":matter_id,
        "canonical_isomeric_smiles":canonical,
        "formula":rdMolDescriptors.CalcMolFormula(mol),
        "molecular_weight_g_mol":Descriptors.MolWt(mol),
        "formal_charge":sum(a.GetFormalCharge() for a in with_h.GetAtoms()),
        "atom_count_with_hydrogens":len(nodes),
        "bond_count_with_hydrogens":len(edges),
        "conformer_candidates_requested":conformers,
        "conformer_candidates_accepted":len(candidates),
        "force_field":model,
        "minimized_forcefield_energy_kcal_mol":best_energy,
        "random_seed":seed,
        "rdkit_version":rdBase.rdkitVersion,
        "molblock_sha256":hashlib.sha256(sdf.encode()).hexdigest(),
        "evidence_ceiling":"sanitized_forcefield_conformer_not_stability_or_synthesis_verified",
        "readiness":{
            "molecular_graph_validated":True,
            "candidate_3d_conformation_generated":True,
            "electronic_structure_qualified":False,
            "thermodynamics_kinetics_qualified":False,
            "synthesis_route_verified":False,
            "lab_identity_purity_and_properties_verified":False,
            "production_release":False,
        },
    }
    return {"matter_graph":payload, "metadata":metadata, "molblock":sdf}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--smiles",required=True)
    parser.add_argument("--id",required=True)
    parser.add_argument("--conformers",type=int,default=8)
    parser.add_argument("--seed",type=int,default=1729)
    parser.add_argument("--matter-graph",type=Path,required=True)
    parser.add_argument("--metadata",type=Path,required=True)
    parser.add_argument("--molblock",type=Path,required=True)
    args=parser.parse_args()
    result=generate(args.smiles,args.id,args.conformers,args.seed)
    args.matter_graph.write_text(
        json.dumps(result["matter_graph"],indent=2,sort_keys=True)+"\n",encoding="utf-8"
    )
    args.metadata.write_text(
        json.dumps(result["metadata"],indent=2,sort_keys=True)+"\n",encoding="utf-8"
    )
    args.molblock.write_text(result["molblock"],encoding="utf-8")
    print(json.dumps(result["metadata"],sort_keys=True))


if __name__=="__main__":
    main()
