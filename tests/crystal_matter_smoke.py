#!/usr/bin/env python3
"""Crystal unit-cell validator geometric and periodic regression tests."""
import copy
import importlib.util
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/"scripts"/"validate_crystal_matter.py"
spec=importlib.util.spec_from_file_location("crystal",path)
crystal=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(crystal)

fixture=json.loads(
    (ROOT/"config"/"examples"/"crystal_cscl_unit_cell.json").read_text()
)
result=crystal.validate(fixture)
assert result["formula_per_listed_unit_cell"]=="ClCs"
assert math.isclose(result["cell_volume_angstrom3"],4.12**3,rel_tol=1e-12)
assert math.isclose(result["nearest_periodic_distance_angstrom"],
                    4.12*math.sqrt(3)/2,rel_tol=1e-12)
assert result["readiness"]["unit_cell_geometry_screened"]
assert result["readiness"]["production_release"] is False
assert result["evidence_ceiling"]=="periodic_crystallographic_geometry_only_not_material_stability"
cif=crystal.cif_text(result)
assert "data_cace_crystal" in cif
assert "_atom_site_fract_z" in cif
assert "Cs" in cif and "Cl" in cif
assert "P 1" in cif
assert crystal.cif_text(crystal.validate(fixture))==cif

def reject(change):
    obj=copy.deepcopy(fixture)
    change(obj)
    try:
        crystal.validate(obj)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid unit cell accepted")

reject(lambda p:p["sites"].append({
    "id":"Cs-copy","element":"Cs","fractional_position":[1,0,0]
}))
reject(lambda p:p["sites"].append({
    "id":"Cs-collision","element":"Cs","fractional_position":[0.001,0,0]
}))
reject(lambda p:p["sites"][0].update(element="NotAnElement"))
reject(lambda p:p.update(lattice_vectors_angstrom=[[4.12,0,0],[4.12,0,0],[0,0,4.12]]))
reject(lambda p:p.update(lattice_vectors_angstrom=[[4.12,0,0],[0,-4.12,0],[0,0,4.12]]))
reject(lambda p:p["sites"][1].update(fractional_position=[float("nan"),0,0]))
print("crystal matter geometry: PASS")
