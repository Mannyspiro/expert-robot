"""Weighted local-constant versus local-linear *reference*, inspired by Parallax.

This scalar least-squares sketch is not the Parallax attention kernel, neural
training, or an implementation of query/key covariance probing. It isolates the
classical local-linear correction and exposes degenerate fitting cases.
"""
from __future__ import annotations

import math
from typing import Sequence

MAX_POINTS = 4096

def _prepare(xs:Sequence[float], ys:Sequence[float], query:float, bandwidth:float):
    if not isinstance(xs,(tuple,list)) or not isinstance(ys,(tuple,list)) or not 1<=len(xs)==len(ys)<=MAX_POINTS:
        raise ValueError("finite paired source samples required")
    if (type(query) not in (float,int) or not math.isfinite(query)
            or type(bandwidth) not in (float,int) or not math.isfinite(bandwidth)
            or bandwidth <= 0):
        raise ValueError("finite query and positive bandwidth required")
    entries=[]
    for x,y in zip(xs,ys):
        if type(x) not in (float,int) or type(y) not in (float,int) or not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("nonfinite or nonnumeric sample")
        delta=(x-query)/bandwidth
        weight=math.exp(-0.5*delta*delta)
        if weight>0:
            entries.append((x-query,y,weight))
    if not entries:
        raise ValueError("all Gaussian weights underflowed to zero")
    return entries

def local_constant(xs,ys,query,bandwidth):
    data=_prepare(xs,ys,query,bandwidth)
    total=sum(w for _,_,w in data)
    return {"schema":"merlin-local-constant-reference/1",
            "estimate":sum(w*y for _,y,w in data)/total,
            "status":"local_constant","nonzero_weights":len(data),
            "neural_model_evaluated":False,"production_qualified":False}

def local_linear(xs,ys,query,bandwidth,*,singularity_tolerance=1e-12):
    """Weighted degree-one regression centered on the query coordinate.

    Fit y ~= intercept + slope*(x-query); return intercept. Positive
    weights and at least two distinct local sample coordinates are necessary
    for a uniquely determined weighted slope/intercept.
    """
    if (type(singularity_tolerance) not in (float,int)
            or not math.isfinite(singularity_tolerance)
            or not 0<=singularity_tolerance<=1e-4):
        raise ValueError("finite bounded singularity tolerance required")
    data=_prepare(xs,ys,query,bandwidth)
    s0=sum(w for _,_,w in data)
    s1=sum(w*dx for dx,_,w in data)
    s2=sum(w*dx*dx for dx,_,w in data)
    t0=sum(w*y for _,y,w in data)
    t1=sum(w*dx*y for dx,y,w in data)
    determinant=s0*s2-s1*s1
    if (not math.isfinite(determinant) or determinant<=singularity_tolerance*s0*s2):
        return {"schema":"merlin-local-linear-reference/1",
                "estimate":t0/s0,"status":"fallback_local_constant",
                "nonzero_weights":len(data),"determinant":determinant,
                "neural_model_evaluated":False,"production_qualified":False}
    intercept=(s2*t0-s1*t1)/determinant
    if not math.isfinite(intercept):
        raise ArithmeticError("nonfinite local linear fit")
    return {"schema":"merlin-local-linear-reference/1",
            "estimate":intercept,"status":"local_linear",
            "nonzero_weights":len(data),"determinant":determinant,
            "neural_model_evaluated":False,"production_qualified":False}

def affine_boundary_experiment():
    """A synthetic boundary case; establishes no general architecture gain."""
    xs=list(range(16))
    y=[2.5+0.7*x for x in xs]
    constant=local_constant(xs,y,0.0,2.2)
    linear=local_linear(xs,y,0.0,2.2)
    target=2.5
    return {"schema":"merlin-parallax-inspired-affine-boundary/1",
            "query":0.0,"bandwidth":2.2,"samples":len(xs),
            "target":target,
            "local_constant":constant,"local_linear":linear,
            "absolute_errors":{"constant":abs(constant["estimate"]-target),
                               "linear":abs(linear["estimate"]-target)},
            "expected_theoretical_property":"affine reproduction for positive-variance weighted local linear regression in exact arithmetic",
            "parallax_kernel_executed":False,"trained_model_evaluated":False,
            "novel_math_proven":False,"production_qualified":False}
