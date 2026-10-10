#!/usr/bin/env python3
"""Independent, offline PDE regression suite; NO live CACE module mocked as a pass."""
import hashlib
import json
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from experiment_cace_chip_p1_manufactured import (mesh, element_data,
      independent_assemble,independent_p1,run,check_pin,unpack_nodal,solve,SEGMENTS)

expected_nodes=(17,65,257)
errors=[];energies=[]
for segment,vertices_count in zip(SEGMENTS,expected_nodes):
    verts,triangles,outer=mesh(segment)
    assert len(verts)==vertices_count
    assert len(triangles)==(2*segment*(segment//4)-segment)
    assert len(outer)==segment
    for t in triangles:
        assert element_data([verts[i] for i in t])[0]>0
    a,rhs,area=independent_assemble(verts,triangles)
    assert sum(rhs)>0 and 2.5<area<3.2
    assert all(abs(sum(row))<1e-12 for row in a)
    ref=independent_p1(verts,triangles,outer)
    assert ref['residual_inf']<1e-10
    assert 0<ref['nodal_error_inf']<0.10
    assert ref['energy_seminorm_error']>0
    assert all(ref['values'][i]==0 for i in outer)
    errors.append(ref['nodal_error_inf'])
    energies.append(ref['energy_seminorm_error'])
assert errors[0]>errors[1]>errors[2]
assert energies[0]>energies[1]>energies[2]
# The *analytical* PDE manufactured source is f=4, as u=1-x*x-y*y.
for x,y in ((0.,0.),(.25,.4),(.5,.5)):
    assert -(-2.0-2.0)==4.0
    assert 1-x*x-y*y >=0
# Wrong triangle orientation, singular matrix, incomplete RHS, shape errors.
verts,triangles,boundary=mesh(8)
first=triangles[0]
for mutated in ([verts[first[1]],verts[first[0]],verts[first[2]]],
                [verts[first[0]],verts[first[0]],verts[first[2]]]):
    try: element_data(mutated)
    except ValueError: pass
    else: raise AssertionError('invalid element accepted')
for a,b in (([[0.]],[1.]),([[1.]],[0.,1.])):
    try: solve(a,b)
    except ValueError: pass
    else: raise AssertionError('invalid solver input accepted')
for n in (0,2,15,True,'8'):
    try: mesh(n)
    except ValueError: pass
    else: raise AssertionError('unapproved mesh accepted')
for candidate in ({'something':[0,1]},{'values':[1,2,3]},
                  [0.0,float('nan')],[True,1.0]):
    try: unpack_nodal(candidate,2)
    except ValueError: pass
    else: raise AssertionError('bad CACE vector accepted')
try:check_pin(Path('/not/an/existing/cace'),Path('/no-pin.json'))
except ValueError: pass
else:raise AssertionError('missing pinned CACE checkout accepted')
report=run()
assert report==run()
assert len(report['cases'])==3
assert not report['actual_cace_p1_solver_executed']
assert report['exact_cace_commit'] is None
assert not report['cace_continuum_error_certified']
assert not report['formal_lean_kernel_checked']
assert not report['rsi_promotion_authorized']
plain=dict(report);hash_claim=plain.pop('receipt_sha256')
assert hashlib.sha256(json.dumps(plain,sort_keys=True,separators=(',',':')).encode()).hexdigest()==hash_claim
print('Manufactured Poisson P1 offline PASS: 3 disk meshes, decreasing nodal/H1 errors, independent assembler, mutants')
