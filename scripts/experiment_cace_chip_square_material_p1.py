#!/usr/bin/env python3
"""Independent manufactured variable-material P1 FEM on a full unit-square chip.

Bounded synthetic continuum numerical experiment. Not yet executed through the
pinned CACE solver: its source-only Poisson contract cannot express variable
coefficient k(x,y)=1+x and the polynomial manufactured forcing f(x,y).
All material properties dimensionless and deliberately NOT calibrated silicon.
No physical chip, semiconductor transport, Lean proof or continuum certificate.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path

GRIDS=(5, 9, 13)
# Five-point Gauss-Legendre on [0,1]; exact for degrees <= 9 over each axis.
_X=(-0.906179845938664, -0.538469310105683, 0., 0.538469310105683, 0.906179845938664)
_W=(0.236926885056189, 0.478628670499366, 0.568888888888889, 0.478628670499366, 0.236926885056189)
Q=tuple(((x+1)/2,w/2) for x,w in zip(_X,_W))


def exact(x,y):
    return x*(1-x)*y*(1-y)


def grad_exact(x,y):
    return ((1-2*x)*y*(1-y), x*(1-x)*(1-2*y))


def conductivity(x,y):
    return 1+x


def forcing(x,y):
    # f = -div((1+x)grad u) = -(grad_x u + (1+x)laplacian u)
    return 2*(1+x)*(x*(1-x)+y*(1-y))-(1-2*x)*y*(1-y)


def geometry(n):
    if type(n) is not int or n not in GRIDS:
        raise ValueError('grid not allowlisted')
    points=[(i/(n-1),j/(n-1)) for j in range(n) for i in range(n)]
    tris=[]
    for j in range(n-1):
        for i in range(n-1):
            a=j*n+i;b=a+1;c=a+n;d=c+1
            tris.extend(((a,b,d),(a,d,c)))
    boundary={j*n+i for j in range(n) for i in range(n)
              if i in (0,n-1) or j in (0,n-1)}
    return points,tris,boundary


def element_data(p):
    (x0,y0),(x1,y1),(x2,y2)=p
    jac=(x1-x0)*(y2-y0)-(x2-x0)*(y1-y0)
    if jac<=0 or not math.isfinite(jac):
        raise ValueError('degenerate/inverted triangle')
    grads=(((y1-y2)/jac,(x2-x1)/jac),((y2-y0)/jac,(x0-x2)/jac),((y0-y1)/jac,(x1-x0)/jac))
    return jac/2,grads,jac


def quadrature(pts,jac):
    x0,y0=pts[0]
    dx1=pts[1][0]-x0;dy1=pts[1][1]-y0
    dx2=pts[2][0]-x0;dy2=pts[2][1]-y0
    for s,ws in Q:
        for t,wt in Q:
            u=s;v=(1-s)*t
            yield x0+u*dx1+v*dx2,y0+u*dy1+v*dy2,(1-u-v,u,v),ws*wt*jac*(1-s)


def assemble(points,tris,coefficient=conductivity,rhs_fn=forcing):
    n=len(points)
    a=[[0.0]*n for _ in range(n)]
    b=[0.0]*n
    area=0.0
    for tri in tris:
        pts=[points[i] for i in tri]
        ar,g,jac=element_data(pts);area+=ar
        kval=sum(coefficient(*pt) for pt in pts)/3.0
        if not math.isfinite(kval) or kval<=0:
            raise ValueError('nonpositive/invalid material')
        for z,i in enumerate(tri):
            for t,k in enumerate(tri):
                a[i][k]+=ar*kval*(g[z][0]*g[t][0]+g[z][1]*g[t][1])
        for x,y,shape,weight in quadrature(pts,jac):
            f=rhs_fn(x,y)
            if not math.isfinite(f):raise ValueError('invalid forcing')
            for z,i in enumerate(tri):b[i]+=f*shape[z]*weight
    return a,b,area


def solve(a,rhs):
    n=len(rhs)
    if len(a)!=n or any(len(row)!=n for row in a):raise ValueError('matrix shape')
    m=[[float(v) for v in row]+[float(rhs[i])] for i,row in enumerate(a)]
    for col in range(n):
        i=max(range(col,n),key=lambda k:abs(m[k][col]))
        if abs(m[i][col])<=1e-14:raise ValueError('singular matrix')
        m[i],m[col]=m[col],m[i]
        p=m[col][col]
        m[col]=[v/p for v in m[col]]
        for k in range(n):
            if k==col:continue
            c=m[k][col]
            if c:m[k]=[m[k][j]-c*m[col][j] for j in range(n+1)]
    return [row[-1] for row in m]


def evaluate(n, material=conductivity, source=forcing):
    pts,tris,boundary=geometry(n)
    A,rhs,area=assemble(pts,tris,material,source)
    free=[i for i in range(len(pts)) if i not in boundary]
    x=solve([[A[i][j] for j in free] for i in free],[rhs[i] for i in free])
    values=[0.0]*len(pts)
    for i,u in zip(free,x):values[i]=u
    r=max(abs(sum(A[i][j]*values[j] for j in range(len(pts)))-rhs[i]) for i in free)
    nodal_error=max(abs(v-exact(*pts[i])) for i,v in enumerate(values))
    e2=0.0
    energy=0.0
    for tri in tris:
        vv=[pts[i] for i in tri]
        _,g,jac=element_data(vv)
        gh=tuple(sum(values[tri[i]]*g[i][k] for i in range(3)) for k in range(2))
        for x,y,sh,w in quadrature(vv,jac):
            gx,gy=grad_exact(x,y)
            kv=material(x,y)
            e2+=w*kv*((gh[0]-gx)**2+(gh[1]-gy)**2)
            energy+=w*kv*(gx*gx+gy*gy)
    if abs(area-1)>1e-11:raise AssertionError('unit square does not tessellate')
    if r>1e-9 or e2<0:raise AssertionError('independent FEM residual/error failed')
    return dict(grid=n,vertices=len(pts),triangles=len(tris),interior_dofs=len(free),
                residual_inf=r,analytic_nodal_error_inf=nodal_error,
                energy_seminorm_error=math.sqrt(e2),analytic_energy_integral=energy,
                discrete_energy=sum(values[i]*rhs[i] for i in free),
                sampled_solution_at_center=values[(n*n)//2])


def run():
    cases=[evaluate(n) for n in GRIDS]
    nodal=[c['analytic_nodal_error_inf'] for c in cases]
    h1=[c['energy_seminorm_error'] for c in cases]
    if not all(nodal[i+1]<nodal[i] and h1[i+1]<h1[i] for i in range(len(cases)-1)):
        raise AssertionError('manufactured refinement trend failed')
    # Exact symbolic energy is ∫(1+x)|∇u|² dxdy = 1/30.
    if any(abs(c['analytic_energy_integral']-1/30)>1e-11 for c in cases):
        raise AssertionError('independent analytic energy identity violated')
    # Incorrect source without ∂k/∂x term must fail the manufactured model.
    bad=lambda x,y:2*(1+x)*(x*(1-x)+y*(1-y))
    wrong=evaluate(9,source=bad)
    if wrong['analytic_nodal_error_inf']<=cases[1]['analytic_nodal_error_inf']*1.1:
        raise AssertionError('missing-gradient forcing mutation escaped')
    # An incorrectly signed permeability must never enter a SPD FEM solve.
    try:assemble(*geometry(5)[:2],coefficient=lambda x,y:-1.0)
    except ValueError:bad_material_rejected=True
    else:raise AssertionError('negative coefficient accepted')
    report={'schema_version':1,'model':'square-chip-variable-material-manufactured-p1-v1',
       'domain':'normalized 200 um square',
       'manufactured_u':'x(1-x)y(1-y)',
       'conductivity':'k(x,y)=1+x (synthetic dimensionless)',
       'manufactured_f':'2(1+x)(x(1-x)+y(1-y))-(1-2x)y(1-y)',
       'boundary':'zero Dirichlet on four square edges',
       'symbolic_analytic_energy':'1/30',
       'cases':cases,'nodal_error_decreases':True,'h1_error_decreases':True,
       'independent_energy_checked':True,
       'missing_material_gradient_mutant_detected':True,
       'negative_material_mutant_rejected':bad_material_rejected,
       'offline_reference_only':True,'actual_cace_variable_coefficient_assembly_executed':False,
       'actual_cace_pde_solver_executed':False,'cace_continuum_bound_certified':False,
       'lean_kernel_checked':False,'physical_silicon_calibrated':False,
       'rsi_promotion_authorized':False,
       'qualification_limit':'Numeric reference in normalized coordinates; CACE variable coefficient interface not pinned or verified.'}
    serial=json.dumps(report,sort_keys=True,separators=(',',':'))
    report['receipt_sha256']=hashlib.sha256(serial.encode()).hexdigest()
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('-o','--output',type=Path)
    args=p.parse_args()
    r=run()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(r,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'model':r['model'],'cases':r['cases'],
          'actual_cace_variable_coefficient_assembly_executed':False,
          'receipt_sha256':r['receipt_sha256']},sort_keys=True))

if __name__=='__main__':main()
