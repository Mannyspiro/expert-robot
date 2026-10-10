#!/usr/bin/env python3
"""Bounded 2D nodal-FV chip-sheet electrothermal refinement experiment.

Synthetic conductive film over a lumped thermal substrate. Exact Fraction
solver, no silicon carrier model, foundry calibration, FEM certification, or
physical hardware claim. Fixed physical dimensions across grid refinements.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

WIDTH_M=F(1,5000)             # 200 um square sheet
FILM_THICKNESS_M=F(1,1000000)
THERMAL_THICKNESS_M=F(1,10000)
SIGMA_S_PER_M=F(100000)       # *synthetic* effective film material
SILICON_K_W_PER_MK=F(130)
SINK_W_PER_M2K=F(225000)     # *synthetic* effective heat transfer coefficient
BIAS_V=F(1,10)
ALLOWED_SIZES=(3,5,7)


def solve(a,b):
    n=len(b)
    if len(a)!=n or any(len(row)!=n for row in a):
        raise ValueError('invalid matrix')
    m=[[F(q) for q in row]+[F(b[i])] for i,row in enumerate(a)]
    for col in range(n):
        row=next((k for k in range(col,n) if m[k][col]),None)
        if row is None:
            raise ValueError('singular conductance system')
        m[col],m[row]=m[row],m[col]
        pivot=m[col][col]
        m[col]=[q/pivot for q in m[col]]
        for k in range(n):
            if k!=col:
                mul=m[k][col]
                m[k]=[m[k][j]-mul*m[col][j] for j in range(n+1)]
    return [r[-1] for r in m]


def incident_matrix(n, network, sink=None):
    a=[[F(0) for _ in range(n)] for _ in range(n)]
    for u,v,g in network:
        if type(u)!=int or type(v)!=int or u==v or not (0<=u<n and 0<=v<n) or g<=0:
            raise ValueError('invalid conductance edge')
        a[u][u]+=g;a[v][v]+=g;a[u][v]-=g;a[v][u]-=g
    if sink is not None:
        if len(sink)!=n or any(h<=0 for h in sink):
            raise ValueError('invalid thermal sink')
        for i,h in enumerate(sink):
            a[i][i]+=h
    return a


def edge_currents(n, network, solution):
    currents=[F(0)]*n
    for u,v,g in network:
        flow=g*(solution[u]-solution[v])
        currents[u]+=flow; currents[v]-=flow
    return currents


def grid(size, defect=False):
    if type(size)!=int or size not in ALLOWED_SIZES or type(defect)!=bool:
        raise ValueError('unsupported bounded grid')
    n=size*size
    dx=WIDTH_M/(size-1)
    coords=tuple((x,y) for y in range(size) for x in range(size))
    index={point:i for i,point in enumerate(coords)}
    sigma=[]
    for x,y in coords:
        # Fixed physical region: central 50 um square; material synthetic.
        in_defect=(abs(F(x)*dx-WIDTH_M/2)<=WIDTH_M/8 and
                   abs(F(y)*dx-WIDTH_M/2)<=WIDTH_M/8)
        sigma.append(SIGMA_S_PER_M/(5 if defect and in_defect else 1))
    ec=[];tc=[]
    for x,y in coords:
        for xx,yy in ((x+1,y),(x,y+1)):
            if (xx,yy) not in index:continue
            u=index[(x,y)];v=index[(xx,yy)]
            face_width=dx*(F(1,2) if (y in (0,size-1) if yy==y else x in (0,size-1)) else 1)
            geom=face_width/dx
            effective_sigma=2*sigma[u]*sigma[v]/(sigma[u]+sigma[v])
            ec.append((u,v,effective_sigma*FILM_THICKNESS_M*geom))
            tc.append((u,v,SILICON_K_W_PER_MK*THERMAL_THICKNESS_M*geom))
    # Each node's nodal control volume has half width at each boundary.
    areas=[dx*dx * (F(1,2) if x in (0,size-1) else 1)
                  * (F(1,2) if y in (0,size-1) else 1) for x,y in coords]
    assert sum(areas)==WIDTH_M*WIDTH_M
    sink=[SINK_W_PER_M2K*a for a in areas]
    return coords,tuple(ec),tuple(tc),tuple(sink)


def run_case(size, defect=False):
    coords,ec,tc,sink=grid(size,defect)
    n=len(coords)
    a=incident_matrix(n,ec)
    fixed={i:(BIAS_V if x==0 else F(0)) for i,(x,y) in enumerate(coords) if x in (0,size-1)}
    free=[i for i in range(n) if i not in fixed]
    b=[-sum(a[i][j]*val for j,val in fixed.items()) for i in free]
    free_v=solve([[a[i][j] for j in free] for i in free],b)
    volts=[F(0)]*n
    for i,val in fixed.items():volts[i]=val
    for i,val in zip(free,free_v):volts[i]=val
    flux=edge_currents(n,ec,volts)
    if any(flux[i] for i in free) or sum(flux):
        raise AssertionError('KCL failed')
    current=sum(flux[i] for i,(x,y) in enumerate(coords) if x==0)
    power=[F(0)]*n
    for u,v,g in ec:
        diss=g*(volts[u]-volts[v])**2
        power[u]+=diss/2;power[v]+=diss/2
    electrical_watts=sum(power)
    if electrical_watts!=BIAS_V*current:
        raise AssertionError('electrical power != IV')
    thermal=incident_matrix(n,tc,sink)
    temp=solve(thermal,power)
    # Independent flux summation, separate from nodal matrix multiply.
    flowed=edge_currents(n,tc,temp)
    if any(flowed[i]+sink[i]*temp[i]-power[i] for i in range(n)):
        raise AssertionError('thermal flux residual')
    if sum(sink[i]*temp[i] for i in range(n))!=electrical_watts:
        raise AssertionError('thermal power balance')
    if any(T<0 for T in temp):
        raise AssertionError('negative temperature rise')
    if not defect:
        expected=[BIAS_V*(1-F(x,size-1)) for x,y in coords]
        if volts!=expected:
            raise AssertionError('uniform planar voltage analytic failure')
        if electrical_watts!=SIGMA_S_PER_M*FILM_THICKNESS_M*BIAS_V**2:
            raise AssertionError('uniform sheet power refinement failure')
    return {
        'size':size,'material_defect':defect,'nodes':n,'edges':len(ec),
        'mesh_spacing_m':str(WIDTH_M/(size-1)),
        'bias_V':str(BIAS_V),
        'current_A':str(current),'power_W':str(electrical_watts),
        'max_temperature_rise_K':str(max(temp)),
        'temperature_rise_K':[str(v) for v in temp],
        'voltages_V':[str(v) for v in volts],
        'electrical_kcl_exact_zero':True,
        'thermal_local_residuals_exact_zero':True,
        'thermal_source_sink_exact_balance':True,
        'energy_power_identity_exact':True,
        'electrical_matrix':[[str(v) for v in row] for row in a],
        'thermal_matrix':[[str(v) for v in row] for row in thermal],
    }


def run():
    rows=[run_case(n,defect) for defect in (False,True) for n in ALLOWED_SIZES]
    # Positive reference: fixed dimensions ensure analytic solution independent
    # of mesh for uniform sheet, but hotspot thermals need not be monotone.
    p={r['power_W'] for r in rows if not r['material_defect']}
    if len(p)!=1:
        raise AssertionError('uniform refinement power not invariant')
    if not all(F(v['power_W']) < F(p0) for v in rows if v['material_defect'] for p0 in p):
        raise AssertionError('synthetic resistive defect failed to reduce power')
    # Fault injection: reusing the original voltage after changing a live trace
    # must break KCL; do not call a broken board certified.
    coord,ec,_,_=grid(3,False)
    known=run_case(3,False)
    vv=[F(x) for x in known['voltages_V']]
    altered=tuple(edge for edge in ec if set(edge[:2])!={0,1})
    residual=edge_currents(len(coord),altered,vv)
    if residual==edge_currents(len(coord),ec,vv):
        raise AssertionError('open trace mutation not detected')
    if not any(residual[i] for i,(x,y) in enumerate(coord) if x not in (0,2)):
        raise AssertionError('open trace KCL mutant undetected')
    report={
        'schema_version':1,'model':'bounded-2d-chip-sheet-electrothermal-refinement-v1',
        'cases':rows,'uniform_analytic_voltage_checked':True,
        'uniform_exact_power_refinement_invariant':True,
        'open_trace_mutant_detected':True,
        'geometry':'200 um square, 1 um conductor film, 100 um effective heat sheet',
        'model_limits':'synthetic σ and sink; nodal finite volume, no drift diffusion, no calibrated PDK, no transient heat',
        'physical_calibration':False,'physical_hardware_tested':False,
        'cace_pde_solver_executed':False,'cace_certificate':False,'lean_kernel_checked':False,
        'automatic_rsi_promotion_authorized':False,
    }
    encoded=json.dumps(report,sort_keys=True,separators=(',',':'))
    report['result_sha256']=hashlib.sha256(encoded.encode()).hexdigest()
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cace-repo',type=Path)
    p.add_argument('--pin',type=Path,default=Path('config/cace_fem_nd_contract_pin.json'))
    p.add_argument('-o','--output',type=Path)
    args=p.parse_args()
    result=run()
    result['actual_cace_csr_codec_executed']=False
    if args.cace_repo:
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from experiment_cace_chip_electrothermal import verify_cace_codec
        for case in result['cases']:
            verify_cace_codec(case,args.cace_repo.resolve(),args.pin)
        result['actual_cace_csr_codec_executed']=True
    encoded=json.dumps({k:v for k,v in result.items() if k!='result_sha256'},
                       sort_keys=True,separators=(',',':'))
    result['result_sha256']=hashlib.sha256(encoded.encode()).hexdigest()
    rendered=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(rendered)
    print(json.dumps({k:result[k] for k in ('model','actual_cace_csr_codec_executed',
          'result_sha256')},sort_keys=True))

if __name__=='__main__':
    main()
