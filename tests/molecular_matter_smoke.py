#!/usr/bin/env python3
"""Molecular matter modeler chemical graph, reproducibility, rejection gates."""
import importlib.util
import json
from pathlib import Path

from rdkit import Chem

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "generate_molecular_matter.py"
spec = importlib.util.spec_from_file_location("molecular_modeler", path)
mol = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mol)

cases = [
    ("O", "H2O", 3, 2, 0),
    ("CCO", "C2H6O", 9, 8, 0),
    ("c1ccccc1", "C6H6", 12, 12, 0),
    ("[NH4+]", "H4N+", 5, 4, 1),
]
for smiles, formula, atoms, bonds, charge in cases:
    result = mol.generate(smiles, "smoke-"+str(atoms)+"-"+str(charge),
                          conformers=3, seed=1729)
    graph = result["matter_graph"]
    meta = result["metadata"]
    assert meta["formula"] == formula, (smiles, meta["formula"])
    assert meta["atom_count_with_hydrogens"] == atoms
    assert meta["bond_count_with_hydrogens"] == bonds
    assert meta["formal_charge"] == charge
    assert graph["verification"]["chemistry_validity"] is True
    assert graph["verification"]["wet_lab_instructions_allowed"] is False
    assert all(len(a["position"])==3 for a in graph["nodes"])
    assert all(a["metadata"]["position_unit"]=="angstrom" for a in graph["nodes"])
    assert len(set(n["id"] for n in graph["nodes"])) == atoms
    assert not meta["readiness"]["production_release"]
    from_block = Chem.MolFromMolBlock(result["molblock"],removeHs=False)
    assert from_block is not None
    assert from_block.GetNumAtoms() == atoms

reference = mol.generate("CCO","ethanol",conformers=3,seed=1729)
repeat = mol.generate("CCO","ethanol",conformers=3,seed=1729)
assert reference["metadata"]["molblock_sha256"] == repeat["metadata"]["molblock_sha256"]
assert json.dumps(reference["matter_graph"],sort_keys=True) == json.dumps(
    repeat["matter_graph"],sort_keys=True
)

for bad in ("", "C(F)(F)(F)(F)F", "C.C", "[Na+].[Cl-]"):
    try:
        mol.generate(bad,"bad",conformers=2)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid/disconnected molecule accepted: "+repr(bad))

try:
    mol.generate("CCO","limit",conformers=500)
except ValueError:
    pass
else:
    raise AssertionError("unbounded conformer request accepted")

print("molecular matter modeler (RDKit): PASS")
