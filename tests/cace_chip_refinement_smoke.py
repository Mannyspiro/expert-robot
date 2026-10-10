#!/usr/bin/env python3
"""Offline exact chip-grid refinement checks; no CACE checkout or privileges."""
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from experiment_cace_chip_refinement import (run, run_case, grid, incident_matrix,
     edge_currents, BIAS_V, SIGMA_S_PER_M, FILM_THICKNESS_M,
     WIDTH_M, SINK_W_PER_M2K, ALLOWED_SIZES, solve)

for size in ALLOWED_SIZES:
    coords, ec, tc, sink = grid(size, False)
    assert len(coords)==size*size
    assert len(ec)==len(tc)==2*size*(size-1)
    assert sum(sink)==SINK_W_PER_M2K*WIDTH_M**2
    regular=run_case(size,False)
    assert F(regular['power_W'])==SIGMA_S_PER_M*FILM_THICKNESS_M*BIAS_V**2==F(1,1000)
    assert F(regular['current_A'])==F(1,100)
    assert F(regular['max_temperature_rise_K'])==F(1,9)
    assert all(regular[k] is True for k in (
      'electrical_kcl_exact_zero','thermal_local_residuals_exact_zero',
      'thermal_source_sink_exact_balance','energy_power_identity_exact'))
    for x,y in coords:
        i=y*size+x
        assert F(regular['voltages_V'][i])==BIAS_V*(1-F(x,size-1))
    broken=run_case(size,True)
    assert F(broken['power_W'])<F(regular['power_W'])
    assert all(F(x)>=0 for x in broken['temperature_rise_K'])
    # A changed network cannot silently reuse the uniform solution.
    a=incident_matrix(size*size, ec)
    assert all(sum(row)==0 for row in a)

for bad in (2,4,8,True,0,'7'):
    try: grid(bad)
    except ValueError: pass
    else: raise AssertionError('unsupported grid accepted')
for network in ([(0,0,F(1))],[(0,2,F(-1))],[(0,2,F(0))],[(0,99,F(1))]):
    try: incident_matrix(9,network)
    except ValueError: pass
    else: raise AssertionError('bad conductor accepted')
for a,b in (([[F(0)]],[F(1)]), ([[F(1)]],[F(1),F(1)])):
    try: solve(a,b)
    except ValueError: pass
    else: raise AssertionError('malformed/singular circuit accepted')
report=run()
assert report==run(), 'not deterministic'
assert report['model']=='bounded-2d-chip-sheet-electrothermal-refinement-v1'
assert report['uniform_analytic_voltage_checked'] is True
assert report['uniform_exact_power_refinement_invariant'] is True
assert report['open_trace_mutant_detected'] is True
assert len(report['cases'])==6
assert report['physical_calibration'] is False
assert report['cace_pde_solver_executed'] is False
assert report['cace_certificate'] is False
assert report['lean_kernel_checked'] is False
assert report['automatic_rsi_promotion_authorized'] is False
copied={k:v for k,v in report.items() if k!='result_sha256'}
canonical=json.dumps(copied,sort_keys=True,separators=(',',':'))
assert hashlib.sha256(canonical.encode()).hexdigest()==report['result_sha256']
print('Exact 2D electrothermal refinement PASS: 6 grids, 2 analytic invariants, fault controls')
