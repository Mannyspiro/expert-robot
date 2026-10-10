#!/usr/bin/env python3
"""Offline and deterministic tests of the independent variable-coefficient P1 reference."""
import hashlib
import json
import math
from fractions import Fraction as F
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from experiment_cace_chip_square_material_p1 import (run,evaluate,geometry,
    assemble,element_data,exact,forcing,conductivity,grad_exact,solve,GRIDS)

report=run()
assert report == run()
assert report['offline_reference_only'] is True
assert report['actual_cace_variable_coefficient_assembly_executed'] is False
assert report['actual_cace_pde_solver_executed'] is False
assert report['cace_continuum_bound_certified'] is False
assert report['lean_kernel_checked'] is False
assert report['physical_silicon_calibrated'] is False
assert report['rsi_promotion_authorized'] is False
assert report['missing_material_gradient_mutant_detected']
assert report['negative_material_mutant_rejected']
assert len(report['cases'])==3
assert [c['grid'] for c in report['cases']]==list(GRIDS)
for case in report['cases']:
    n=case['grid']
    points,tris,boundary=geometry(n)
    assert len(points)==n*n
    assert len(tris)==2*(n-1)**2
    assert len(boundary)==4*(n-1)
    a,b,area=assemble(points,tris)
    assert abs(area-1)<1e-12
    assert abs(sum(b)-sum(forcing(*p) for p in points)/(n*n))<0.6  # loose only sign/magnitude
    assert all(abs(sum(row))<1e-12 for row in a)  # Neumann operator before BC
    assert all(abs(a[i][j]-a[j][i])<1e-13 for i in range(len(points)) for j in range(len(points)))
    assert case['residual_inf']<1e-11
    assert case['analytic_nodal_error_inf']>0
    assert case['energy_seminorm_error']>0
    assert abs(case['analytic_energy_integral']-float(F(1,30)))<1e-12
    assert 0<case['sampled_solution_at_center']<exact(.5,.5)

assert (report['cases'][0]['analytic_nodal_error_inf']>
        report['cases'][1]['analytic_nodal_error_inf']>
        report['cases'][2]['analytic_nodal_error_inf'])
assert (report['cases'][0]['energy_seminorm_error']>
        report['cases'][1]['energy_seminorm_error']>
        report['cases'][2]['energy_seminorm_error'])
assert abs(exact(.5,.5)-.0625)<1e-12
assert grad_exact(.5,.5)==(0.,0.)
# Independent finite-difference derivative of k grad u against analytic source.
for x,y in ((.23,.39),(.7,.28),(.41,.64)):
    h=1e-5
    fx=(conductivity(x+h,y)*grad_exact(x+h,y)[0]-conductivity(x-h,y)*grad_exact(x-h,y)[0])/(2*h)
    fy=(conductivity(x,y+h)*grad_exact(x,y+h)[1]-conductivity(x,y-h)*grad_exact(x,y-h)[1])/(2*h)
    assert abs(-(fx+fy)-forcing(x,y))<1e-8
for bad in (2,4,6,8,True,'5'):
    try:geometry(bad)
    except ValueError:pass
    else:raise AssertionError('unsupported grid accepted')
points,tris,_=geometry(5)
for t in ((points[tris[0][1]],points[tris[0][0]],points[tris[0][2]]),
          (points[0],points[0],points[1])):
    try:element_data(t)
    except ValueError:pass
    else:raise AssertionError('inverted/degenerate triangle accepted')
for a,b in (([[0.]],[1.]),([[1.]],[1.,2.])):
    try:solve(a,b)
    except ValueError:pass
    else:raise AssertionError('bad linear system accepted')
for coefficient in (lambda x,y:-1, lambda x,y:float('nan')):
    try:assemble(points,tris,coefficient=coefficient)
    except ValueError:pass
    else:raise AssertionError('invalid material accepted')
try:assemble(points,tris,rhs_fn=lambda x,y:float('inf'))
except ValueError:pass
else:raise AssertionError('invalid source accepted')
payload=dict(report)
sha=payload.pop('receipt_sha256')
assert hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()==sha
print('Square chip variable-material P1: PASS (5/9/13 grids; analytic energy 1/30; independent PDE oracle; faults)')
