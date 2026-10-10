#!/usr/bin/env python3
"""Qualify experimental assembly against independent quadrature reference."""
from fractions import Fraction as F
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import cace_variable_coefficient_p1 as candidate
import experiment_cace_chip_square_material_p1 as reference

for n in (5,9,13):
    verts,tris,boundary=reference.geometry(n)
    res=candidate.manufactured_square(n)
    a=candidate.dense(res)
    refa,refb,area=reference.assemble(verts,tris)
    assert res['area']=='1'
    assert all(a[i][j]==a[j][i] for i in range(n*n) for j in range(n*n))
    assert all(sum(row)==0 for row in a)
    assert all(a[i][i]>0 for i in range(n*n))
    assert all(res['col_idx'][j]<res['col_idx'][j+1]
               for i in range(n*n) for j in range(res['row_ptr'][i],res['row_ptr'][i+1]-1))
    maxa=max(abs(float(a[i][j])-refa[i][j]) for i in range(n*n) for j in range(n*n))
    maxb=max(abs(float(F(res['rhs'][i]))-refb[i]) for i in range(n*n))
    print(n,'assembly difference',maxa,'rhs difference',maxb)
    assert maxa<1e-11 and maxb<1e-11
    free=[i for i in range(n*n) if i not in boundary]
    u=reference.solve([[float(a[i][j]) for j in free] for i in free],
                       [float(F(res['rhs'][i])) for i in free])
    ref=reference.evaluate(n)
    assert abs(u[len(u)//2]-ref['sampled_solution_at_center'])<1e-11

p=[[0,0],[1,0],[0,1]]
t=[[0,1,2]]
def check_reject(pts,tris,**changes):
    kw=dict(k0=1,kx=1,ky=0,forcing=candidate.MANUFACTURED_FORCING)
    kw.update(changes)
    try:candidate.assemble(pts,tris,**kw)
    except ValueError:return
    raise AssertionError('mutant was accepted: '+str(changes))
check_reject(p,[[0,2,1]])
check_reject(p,[[0,1,1]])
check_reject(p,[[0,1,9]])
check_reject(p,t,k0=-1)
check_reject(p,t,k0=True)
check_reject(p,t,k0=float('nan'))
check_reject([[0,0],[float('inf'),0],[0,1]],t)
check_reject(p,t,forcing=[{'x_power':5,'y_power':0,'coefficient':1}])
check_reject(p,t,forcing=[{'x_power':0,'y_power':0,'coefficient':'__import__'}])
check_reject(p,t,forcing=[{'x_power':0,'y_power':0,'coefficient':True}])
check_reject(p,t,forcing=[{'x_power':0,'y_power':0,'coefficient':'1/0'}])
check_reject(p,t,k0='1e30')
check_reject(p,t,k0='1/10000000000000')
assert candidate.manufactured_square(5)==candidate.manufactured_square(5)
assert candidate.manufactured_square(13)['cace_native_module_executed'] is False
assert candidate.manufactured_square(13)['cace_certificate'] is False
print('CACE variable material exact P1 assembler test PASS')
