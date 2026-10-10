#!/usr/bin/env python3
"""Experimental exact-integral affine-k P1 assembly for CACE research handoff.

This is NOT registered in CACE and is not a FEM certificate. Coordinates,
coefficients and polynomial forcing must be finite explicit rational values.
Assemble over CCW triangles with no implicit boundary conditions. Keep a
separate boundary/solver/certifier qualification before CACE promotion.
"""
from __future__ import annotations

from fractions import Fraction as F
from math import factorial, isfinite

MAX_VERTICES = 200
MAX_TRIANGLES = 400
MAX_SOURCE_DEGREE = 4


def rational(value):
    if isinstance(value, bool):
        raise ValueError('boolean cannot represent material or geometry')
    if isinstance(value, F):
        result=value
    elif isinstance(value, int):
        result=F(value)
    elif isinstance(value, float):
        if not isfinite(value):
            raise ValueError('nonfinite material or coordinate')
        result=F(str(value))
    elif isinstance(value, str) and 0 < len(value) <= 40:
        try:
            result=F(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError('invalid rational literal') from exc
    else:
        raise ValueError('unapproved numeric representation')
    if abs(result.numerator) > 10**12 or result.denominator > 10**12:
        raise ValueError('numeric rational complexity exceeds cap')
    return result



def clean(poly):
    return {k: v for k, v in poly.items() if v}


def add(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, F(0)) + v
    return clean(out)


def mul(a, b):
    out = {}
    for (i, j), x in a.items():
        for (k, l), y in b.items():
            key = i + k, j + l
            out[key] = out.get(key, F(0)) + x * y
    return clean(out)


def power(poly, degree):
    out = {(0, 0): F(1)}
    for _ in range(degree):
        out = mul(out, poly)
    return out


def integrate_reference(poly):
    """Exact integral on {(s,t):s>=0,t>=0,s+t<=1}."""
    return sum((c * F(factorial(i)*factorial(j), factorial(i+j+2))
                for (i, j), c in poly.items()), F(0))


def polynomial_source(items):
    """Strict list of {x_power,y_power,coefficient}; no evaluated strings."""
    if not isinstance(items, list) or not 1 <= len(items) <= 15:
        raise ValueError('invalid forcing term count')
    out = {}
    for item in items:
        if not isinstance(item, dict) or set(item) != {'x_power', 'y_power', 'coefficient'}:
            raise ValueError('invalid forcing polynomial term')
        i, j = item['x_power'], item['y_power']
        if (type(i) is not int or type(j) is not int or i < 0 or j < 0 or
                i+j > MAX_SOURCE_DEGREE):
            raise ValueError('polynomial degree out of range')
        key = i, j
        out[key] = out.get(key, F(0)) + rational(item['coefficient'])
    return clean(out)


def mesh_validation(vertices, triangles):
    if not isinstance(vertices, list) or not 3 <= len(vertices) <= MAX_VERTICES:
        raise ValueError('vertex cap or shape invalid')
    if not isinstance(triangles, list) or not 1 <= len(triangles) <= MAX_TRIANGLES:
        raise ValueError('triangle cap or shape invalid')
    pts = []
    for p in vertices:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError('only planar triangles supported')
        pts.append(tuple(rational(t) for t in p))
    tris = []
    for tri in triangles:
        if (not isinstance(tri, (list, tuple)) or len(tri) != 3 or
                any(type(i) is not int or i < 0 or i >= len(pts) for i in tri) or
                len(set(tri)) != 3):
            raise ValueError('triangle connectivity invalid')
        tris.append(tuple(tri))
    return pts, tris


def assemble(vertices, triangles, *, k0, kx, ky, forcing):
    """Return exact CSR and RHS plus area; no CACE native-module claim."""
    pts, tris = mesh_validation(vertices, triangles)
    a0, ax, ay = rational(k0), rational(kx), rational(ky)
    source = polynomial_source(forcing)
    # Positivity of affine k at all mesh vertices ensures k>0 on each element.
    if any(a0+ax*x+ay*y <= 0 for x, y in pts):
        raise ValueError('affine material must be strictly positive everywhere')
    entries = {}
    load = [F(0) for _ in pts]
    area_total = F(0)
    for tri in tris:
        v = [pts[i] for i in tri]
        (x0,y0),(x1,y1),(x2,y2) = v
        det = (x1-x0)*(y2-y0)-(x2-x0)*(y1-y0)
        if det <= 0:
            raise ValueError('inverted or zero-area triangle')
        area_total += det/2
        grads = (((y1-y2)/det,(x2-x1)/det),
                 ((y2-y0)/det,(x0-x2)/det),
                 ((y0-y1)/det,(x1-x0)/det))
        # Physical affine coordinate polynomials in reference (s,t).
        xpoly = {(0,0):x0,(1,0):x1-x0,(0,1):x2-x0}
        ypoly = {(0,0):y0,(1,0):y1-y0,(0,1):y2-y0}
        # ∫_K affine k dA = |K| average(k at vertices).
        kmean = sum((a0+ax*x+ay*y for x,y in v), F(0))/3
        stiffness_weight = det*kmean/2
        for i, u in enumerate(tri):
            for j, w in enumerate(tri):
                key=u,w
                dot=grads[i][0]*grads[j][0]+grads[i][1]*grads[j][1]
                entries[key]=entries.get(key,F(0))+stiffness_weight*dot
        fpoly = {}
        for (ex, ey), coeff in source.items():
            fpoly=add(fpoly, {k:coeff*v for k,v in mul(power(xpoly,ex),
                                                      power(ypoly,ey)).items()})
        shape=({(0,0):F(1),(1,0):F(-1),(0,1):F(-1)},
               {(1,0):F(1)}, {(0,1):F(1)})
        for i,u in enumerate(tri):
            load[u] += det*integrate_reference(mul(fpoly,shape[i]))
    # Deterministic sorted CSR; zeros omitted, diagonal may be zero on no edges.
    offsets=[0]
    cols=[]
    data=[]
    for u in range(len(pts)):
        row=sorted((v,q) for (i,v),q in entries.items() if i == u and q != 0)
        for v,q in row:
            cols.append(v); data.append(q)
        offsets.append(len(cols))
    return {'schema_version': 1, 'n':len(pts), 'row_ptr':offsets,
            'col_idx':cols, 'data':[str(v) for v in data],
            'rhs':[str(v) for v in load], 'area':str(area_total),
            'assembly':'affine-positive-k-exact-P1-triangle-integrals',
            'cace_native_module_executed':False,
            'cace_certificate':False, 'formal_proof_checked':False}


def dense(result):
    """Independent simple CSR decoder for downstream comparison/testing."""
    n=result['n']
    rows=[[F(0) for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(result['row_ptr'][i],result['row_ptr'][i+1]):
            rows[i][result['col_idx'][j]]=F(result['data'][j])
    return rows


MANUFACTURED_FORCING = [
    {'x_power':1,'y_power':0,'coefficient':2},
    {'x_power':3,'y_power':0,'coefficient':-2},
    {'x_power':0,'y_power':1,'coefficient':1},
    {'x_power':0,'y_power':2,'coefficient':-1},
    {'x_power':1,'y_power':1,'coefficient':4},
    {'x_power':1,'y_power':2,'coefficient':-4},
]


def manufactured_square(size):
    """One input case; reuse geometry but *not* independent assembly."""
    if type(size) is not int or size not in (5,9,13):
        raise ValueError('unqualified mesh size')
    pts=[[F(i,size-1),F(j,size-1)] for j in range(size) for i in range(size)]
    tris=[]
    for j in range(size-1):
        for i in range(size-1):
            a=j*size+i; b=a+1; c=a+size; d=c+1
            tris.extend([[a,b,d],[a,d,c]])
    return assemble(pts,tris,k0=1,kx=1,ky=0,forcing=MANUFACTURED_FORCING)


if __name__=='__main__':
    import json,sys
    n=int(sys.argv[1]) if len(sys.argv)>1 else 5
    print(json.dumps(manufactured_square(n),sort_keys=True))
