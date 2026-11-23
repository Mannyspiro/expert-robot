#!/usr/bin/env python3
"""Reproducible bounded RHF quantum-baseline smoke on water."""
import copy
import importlib.util
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s)
    assert s.loader is not None
    s.loader.exec_module(m)
    return m

molecule=load("molecule",ROOT/"scripts"/"generate_molecular_matter.py")
quantum=load("quantum",ROOT/"scripts"/"evaluate_molecular_quantum.py")

g=molecule.generate("O","water-hf-smoke",conformers=2,seed=1729)["matter_graph"]
result=quantum.baseline(g)
values=result["scf_results"]
assert len(values)==2
assert values[0]["basis"]=="sto-3g"
assert values[1]["basis"]=="6-31g"
assert all(x["converged"] for x in values)
assert all(x["electrons"]==10 for x in values)
assert values[1]["basis_functions"]>values[0]["basis_functions"]
assert -100 < values[0]["total_electronic_energy_hartree"] < -50
assert values[1]["total_electronic_energy_hartree"]<values[0]["total_electronic_energy_hartree"]
assert math.isfinite(result["basis_energy_difference_hartree"])
assert result["readiness"]["quantum_calculation_performed"]
assert not result["readiness"]["basis_limit_converged"]
assert not result["readiness"]["production_release"]
assert "not_validated_thermochemistry" in result["epistemic_status"]

bad=copy.deepcopy(g)
bad["nodes"][0]["metadata"]["position_unit"]="meters"
try:
    quantum.baseline(bad)
except ValueError:
    pass
else:
    raise AssertionError("unit mismatch accepted")

charged=molecule.generate("[NH4+]","ammonium",conformers=2,seed=1729)["matter_graph"]
try:
    quantum.baseline(charged)
except ValueError:
    pass
else:
    raise AssertionError("charged molecule accepted as neutral RHF")

print("quantum baseline water RHF 2 bases: PASS")
