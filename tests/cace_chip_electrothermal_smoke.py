#!/usr/bin/env python3
"""Local exact toy chip physics smoke: no network, CACE checkout or hardware."""
import copy
from fractions import Fraction as F
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from experiment_cace_chip_electrothermal import (model,gaussian,laplacian,
                                                  independent_kcl,edges,BIAS_V)

x=model()
assert x["model"]=="nine-node-electrothermal-film-v1"
assert len(x["geometry_nodes_xy_um"])==9
assert len(x["electrical_conductance_S"])==12
assert F(x["electrical_power_W"])==F(7,6000)
assert F(x["total_supply_current_A"])==F(7,600)
assert F(x["electrical_power_W"])==BIAS_V*F(x["total_supply_current_A"])
assert x["maximum_temperature_rise_K"]>0
assert x["maximum_temperature_rise_K"]<1  # for THESE assumed heat sinks
assert all(F(v)==0 for v in x["exact_free_node_kcl_residuals"])
assert all(F(v)==0 for v in x["exact_thermal_residuals"])
assert x["open_trace_mutant_detected"] and x["conductivity_mutant_detected"]
assert not x["physical_material_parameters_calibrated"]
assert not x["transistor_carriers_or_quantum_modeled"]
assert not x["physical_chip_fabricated_or_tested"]
assert not x["cace_pde_solver_executed"]
assert not x["lean_kernel_checked"]
assert not x["cace_certificate"]
assert not x["rsi_promotion_authorized"]
assert model()==x, "nondeterministic physics model"
# Independent conservation and matrix symmetry / row sum or sink contract.
a=[[F(v) for v in row] for row in x["electrical_matrix"]]
t=[[F(v) for v in row] for row in x["thermal_matrix"]]
assert all(a[i][j]==a[j][i] and t[i][j]==t[j][i] for i in range(9) for j in range(9))
assert all(sum(row)==0 for row in a)
assert all(sum(row)==F(1,1000) for row in t)
assert len(edges())==12
for bad in ([(0,0,F(1))],[(0,9,F(1))],[(0,1,F(0))],[(0,1,F(-1))]):
    try:laplacian(bad)
    except ValueError:pass
    else:raise AssertionError("invalid conductance accepted")
try:gaussian([[F(0),F(0)],[F(0),F(0)]],[F(1),F(1)])
except ValueError:pass
else:raise AssertionError("disconnected chip segment accepted")
# An independent current balance computes a zero net source at every circuit node.
v=tuple(F(z) for z in x["voltages_V"])
flows=independent_kcl(edges(),v)
assert sum(flows)==0
print("Exact toy electrothermal chip network: PASS (9 nodes, 12 bonds, mutations rejected)")
