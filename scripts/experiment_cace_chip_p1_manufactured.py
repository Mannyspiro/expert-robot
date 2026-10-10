#!/usr/bin/env python3
"""Finite-element manufactured Poisson test on an inscribed circular chip patch.

Reference continuum solution is u(x,y)=1-x*x-y*y on a *unit disk* with
zero Dirichlet boundary and source f=4. The polygonal P1 triangulations
approximate the disk; compare nodal error and elementwise energy error using
independent assembly. With --cace-repo, invoke the exact-pinned CACE
SimplexMeshND, P1SimplexSpaceND, PoissonAssemblyND, LinearSolverND and
AlgebraicResidualND on identical vertices/elements, failing closed if the
actual CACE interfaces or their solution representation do not match.

This is not a silicon transistor solver, physical chip calibration, certified
continuum bound, or Lean proof. Radius 100 um merely maps normalized coordinates
to a circular test patch inside the previously modeled 200 um square chip.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

SEGMENTS = (8, 16, 32)
RADIUS_M = 1.0e-4


def mesh(segments):
    if type(segments) is not int or segments not in SEGMENTS:
        raise ValueError('unsupported mesh segments')
    vertices = [(0.0, 0.0)]
    rings = []
    radial_count = segments // 4
    for k in range(1, radial_count+1):
        radius = k / radial_count
        ids = []
        for i in range(segments):
            t = 2.0*math.pi*i/segments
            ids.append(len(vertices))
            vertices.append((radius*math.cos(t),radius*math.sin(t)))
        rings.append(ids)
    elements = []
    inner = rings[0]
    for i in range(segments):
        j = (i+1) % segments
        elements.append((0,inner[i],inner[j]))
    for inner,outer in zip(rings,rings[1:]):
        for i in range(segments):
            j=(i+1)%segments
            elements.append((inner[i],outer[i],outer[j]))
            elements.append((inner[i],outer[j],inner[j]))
    return vertices, elements, set(rings[-1])


def element_data(pts):
    (x0,y0),(x1,y1),(x2,y2) = pts
    det = (x1-x0)*(y2-y0)-(x2-x0)*(y1-y0)
    if det <= 0:
        raise ValueError('nonpositive or degenerate triangle')
    area = det/2
    grad = [((y1-y2)/det,(x2-x1)/det),
            ((y2-y0)/det,(x0-x2)/det),
            ((y0-y1)/det,(x1-x0)/det)]
    return area,grad


def independent_assemble(vertices,elements,source=4.0):
    n = len(vertices)
    a = [[0.0]*n for _ in range(n)]
    rhs = [0.0]*n
    total_area = 0.0
    for cells in elements:
        pts = [vertices[i] for i in cells]
        area,grads = element_data(pts)
        total_area += area
        for i,u in enumerate(cells):
            rhs[u] += source*area/3.0
            for j,v in enumerate(cells):
                a[u][v] += area*sum(grads[i][k]*grads[j][k] for k in (0,1))
    return a,rhs,total_area


def solve(a,b):
    n = len(b)
    if len(a)!=n or any(len(row)!=n for row in a):
        raise ValueError('bad system shape')
    m = [[float(v) for v in row]+[float(b[i])] for i,row in enumerate(a)]
    for col in range(n):
        piv = max(range(col,n), key=lambda k:abs(m[k][col]))
        if abs(m[piv][col]) < 1e-14:
            raise ValueError('singular system')
        m[col],m[piv] = m[piv],m[col]
        q = m[col][col]
        m[col] = [v/q for v in m[col]]
        for row in range(n):
            if row == col:continue
            f = m[row][col]
            if f:
                m[row] = [m[row][j]-f*m[col][j] for j in range(n+1)]
    return [row[-1] for row in m]


def independent_p1(vertices,elements,boundary):
    a,rhs,area = independent_assemble(vertices,elements)
    free = [i for i in range(len(vertices)) if i not in boundary]
    if not free:raise ValueError('no independent free unknowns')
    free_sol = solve([[a[i][j] for j in free] for i in free],[rhs[i] for i in free])
    out = [0.0]*len(vertices)
    for i,v in zip(free,free_sol):out[i]=v
    residual = max(abs(sum(a[i][j]*out[j] for j in range(len(out)))-rhs[i]) for i in free)
    # H^1 seminorm error against analytic grad u=(-2x,-2y), integral computed
    # exactly for each P1 element using barycentric quadratic moments.
    energy2 = 0.0
    for tri in elements:
        pts = [vertices[i] for i in tri]
        t_area,g = element_data(pts)
        grad_u = [sum(out[tri[i]]*g[i][j] for i in range(3)) for j in (0,1)]
        mx = sum(x for x,y in pts)/3.0
        my = sum(y for x,y in pts)/3.0
        # E[x^2]= (sum_i x_i^2 + sum_{i<j} x_i*x_j)/6.
        mx2 = (sum(x*x for x,y in pts) + sum(pts[i][0]*pts[j][0]
                  for i in range(3) for j in range(i+1,3)))/6.0
        my2 = (sum(y*y for x,y in pts) + sum(pts[i][1]*pts[j][1]
                  for i in range(3) for j in range(i+1,3)))/6.0
        energy2 += t_area * (sum(q*q for q in grad_u) +
                             4*(grad_u[0]*mx+grad_u[1]*my) + 4*(mx2+my2))
    if energy2 < -1e-9: raise AssertionError('negative energy error squared')
    max_err = max(abs(out[i]-(1-x*x-y*y)) for i,(x,y) in enumerate(vertices))
    return {'values':out,'matrix':a,'load':rhs,'area':area,
            'residual_inf':residual,'nodal_error_inf':max_err,
            'energy_seminorm_error':math.sqrt(max(0.0,energy2)),
            'free_dofs':len(free)}


def unpack_nodal(candidate,size):
    """Only typed explicit nodal vectors; unexpected CACE output fails closed."""
    if isinstance(candidate,dict):
        for name in ('values','coefficients','nodal_values','u','x','vector','solution'):
            if name in candidate:
                return unpack_nodal(candidate[name],size)
        raise ValueError('unknown CACE solution representation')
    if hasattr(candidate,'ndim') and getattr(candidate,'ndim',None)==1:
        candidate=candidate.tolist()
    if not isinstance(candidate,(list,tuple)) or len(candidate)!=size:
        raise ValueError('CACE solution is not a full nodal vector')
    if any(type(v) not in (int,float) or not math.isfinite(float(v)) for v in candidate):
        raise ValueError('CACE solution contains invalid values')
    return [float(v) for v in candidate]


def check_pin(cace_root,pin_path):
    if cace_root.is_symlink() or not cace_root.is_dir():
        raise ValueError('CACE checkout missing or symlinked')
    pin=json.loads(pin_path.read_text(encoding='utf-8'))
    sha=subprocess.check_output(['git','-C',str(cace_root),'rev-parse','HEAD'],text=True,timeout=10).strip()
    if (pin.get('repository')!='morganaspim/Cace-app' or sha!=pin.get('commit') or
            not (cace_root/'cace_studio/modules/fem_nd.py').is_file()):
        raise ValueError('CACE FEM-ND checkout does not match pin')
    rel='cace_studio/modules/fem_nd.py'
    local=(cace_root/rel).read_bytes()
    committed=subprocess.check_output(['git','-C',str(cace_root),'show','HEAD:'+rel], timeout=10)
    if local != committed:
        raise ValueError('pinned CACE FEM-ND module differs from Git HEAD')
    return sha


def run_cace(vertices,elements,reference,boundary,root):
    sys.path.insert(0,str(root))
    from cace_studio.modules.fem_nd import (SimplexMeshND,P1SimplexSpaceND,
          PoissonAssemblyND,LinearSolverND,AlgebraicResidualND)
    ctx={}
    mesh_o=SimplexMeshND().execute({},
               {'vertices':[list(v) for v in vertices], 'elements':[list(x) for x in elements]},ctx)['mesh']
    space_o=P1SimplexSpaceND().execute({'mesh':mesh_o},{},ctx)['space']
    system_o=PoissonAssemblyND().execute({'mesh':mesh_o,'space':space_o},{'source':4.0},ctx)['system']
    sol_o=LinearSolverND().execute({'system':system_o},{},ctx)['solution']
    residual_o=AlgebraicResidualND().execute({'system':system_o,'solution':sol_o},{},ctx)
    values=unpack_nodal(sol_o,len(vertices))
    discrepancy=max(abs(a-b) for a,b in zip(values,reference['values']))
    boundary_error=max(abs(values[i]) for i in boundary)
    nodal_error=max(abs(values[i]-(1-x*x-y*y)) for i,(x,y) in enumerate(vertices))
    free=[i for i in range(len(vertices)) if i not in boundary]
    independent_residual=max(abs(sum(reference['matrix'][i][j]*values[j]
                         for j in range(len(vertices)))-reference['load'][i]) for i in free)
    reported=residual_o.get('residual_inf')
    if type(reported) not in (int,float) or not math.isfinite(float(reported)):
        raise ValueError('missing finite CACE algebraic residual')
    if discrepancy>1e-7 or boundary_error>1e-8 or float(reported)>1e-7 or independent_residual>1e-7:
        raise AssertionError('actual CACE P1 FEM differs from independently assembled manufactured problem')
    return {'executed':True,'p1_space_used':True,'cace_poisson_assembly_used':True,
            'cace_linear_solver_used':True,'cace_residual_module_used':True,
            'cace_vs_independent_p1_nodal_inf':discrepancy,
            'cace_algebraic_residual_inf':float(reported),
            'independent_residual_of_cace_solution_inf':independent_residual,
            'cace_analytic_nodal_error_inf':nodal_error}


def run(cace_root=None,pin_path=None):
    if cace_root is not None:
        if pin_path is None:raise ValueError('pin required')
        sha=check_pin(cace_root,pin_path)
    else: sha=None
    trials=[]
    for count in SEGMENTS:
        vertices,elements,boundary=mesh(count)
        independent=independent_p1(vertices,elements,boundary)
        if independent['residual_inf']>1e-10 or independent['nodal_error_inf']>0.5:
            raise AssertionError('independent P1 manufactured gate failed')
        cace = run_cace(vertices,elements,independent,boundary,cace_root) if sha else None
        trials.append({'segments':count,'vertices':len(vertices),'elements':len(elements),
                       'disk_polygon_area':independent['area'],
                       'max_boundary_chord_error':1-math.cos(math.pi/count),
                       'independent_discrete_residual_inf':independent['residual_inf'],
                       'manufactured_solution':'u(x,y)=1-x^2-y^2, -laplacian u=4',
                       'analytic_nodal_error_inf':independent['nodal_error_inf'],
                       'h1_seminorm_error_on_polygon':independent['energy_seminorm_error'],
                       'free_dofs':independent['free_dofs'],'cace_actual':cace})
    # Diagnostic convergence gate on bounded meshes. The polygonal domain
    # approximates a circle; this trend is NOT a certified PDE error bound.
    error=[r['h1_seminorm_error_on_polygon'] for r in trials]
    if not all(error[i+1]<error[i] for i in range(len(error)-1)):
        raise AssertionError('H1 errors did not decrease under refinement')
    node_error=[r['analytic_nodal_error_inf'] for r in trials]
    if not all(node_error[i+1]<node_error[i] for i in range(len(node_error)-1)):
        raise AssertionError('nodal errors did not decrease under refinement')
    result={'schema_version':1,'model':'cace-manufactured-inscribed-chip-disk-p1-v1',
            'physical_chip_patch_radius_m':RADIUS_M,
            'normalization':'x_phys=R*x, physical Laplacian/source needs scale 1/R^2',
            'boundary':'zero Dirichlet on inscribed polygon; exact solution zero at circle nodes only',
            'source':'constant 4 on normalized disk approximation',
            'cases':trials,'independent_p1_stiffness_and_load_assembled':True,
            'independent_manufactured_solution_checked':True,
            'exact_cace_commit':sha,
            'actual_cace_p1_solver_executed': bool(sha),
            'formal_lean_kernel_checked':False,'cace_continuum_error_certified':False,
            'physical_semiconductor_materials_calibrated':False,
            'chip_transistor_physics_modeled':False,'rsi_promotion_authorized':False,
            'limitations':'Unit disk polygon surrogate within 200um die; no drift diffusion, PDK, interval bounds, or CACE continuum certification'}
    rendered=json.dumps(result,sort_keys=True,separators=(',',':'))
    result['receipt_sha256']=hashlib.sha256(rendered.encode()).hexdigest()
    return result


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--cace-repo',type=Path)
    a.add_argument('--pin',type=Path,default=Path('config/cace_fem_nd_contract_pin.json'))
    a.add_argument('-o','--output',type=Path)
    args=a.parse_args()
    report=run(args.cace_repo.resolve() if args.cace_repo else None,args.pin)
    text=json.dumps(report,sort_keys=True,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text)
    print(json.dumps({'cases':len(report['cases']),
                      'max_h1_error':max(v['h1_seminorm_error_on_polygon'] for v in report['cases']),
                      'actual_cace_p1_solver_executed':report['actual_cace_p1_solver_executed'],
                      'receipt_sha256':report['receipt_sha256']},sort_keys=True))


if __name__=='__main__':main()
