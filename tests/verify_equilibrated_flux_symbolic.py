#!/usr/bin/env python3
"""Symbolic independent 1D Prager-Synge flux identity checks."""
import json
import sympy as S

def integrate_element(h,f,initial_flux,gradient):
    t=S.symbols("t",real=True)
    exact=S.integrate(S.expand((initial_flux-f*t-gradient)**2),(t,0,h))
    expression=h*(initial_flux-gradient)**2-f*h*h*(initial_flux-gradient)+f*f*h**3/3
    assert S.factor(exact-expression)==0
    return expression

def check():
    a,b,f1,f2,y,C=S.symbols("a b f1 f2 y C",real=True,nonzero=True)
    h=a
    # Mesh 0 < a < 1 with one arbitrary interior P1 nodal value y,
    # and independent forcing on the two cells.
    cstar=f1*h*h/2+f1*h*(1-h)+f2*(1-h)**2/2
    def majorant(c):
        return integrate_element(h,f1,c,y/h)+integrate_element(
            1-h,f2,c-f1*h,-y/(1-h))
    discrepancy=S.factor(majorant(C)-majorant(cstar)-(C-cstar)**2)
    if discrepancy!=0:raise AssertionError(str(discrepancy))
    # A flux not satisfying -sigma'=f lacks the hypothesis of the bound.
    bad_flux=integrate_element(h,0,C,y/h)+integrate_element(
         1-h,0,C,-y/(1-h))
    if S.factor(bad_flux-majorant(C))==0:
        raise AssertionError("non-equilibrated flux should not match")
    return {"schema_version":1,
            "experiment":"symbolic-1d-equilibrated-flux-prager-synge-v1",
            "exact_single_cell_integration":True,
            "independent_two_cell_hypercircle_gap_identity":"0",
            "non_equilibrated_flux_formula_rejected":True,
            "theorem_hypotheses":"1D Dirichlet, piecewise constant f, continuous piecewise linear v, continuous flux sigma with -sigma'=f",
            "lean_kernel_checked":False,
            "general_pde_bound_qualified":False,
            "authority_expanded":False}

if __name__=="__main__":
    print(json.dumps(check()))
