#!/usr/bin/env python3
"""Independent exact symbolic derivation of the benchmark 1D P1 energy error.

For u=x(1-x)/2, nodal-linear uh through u(a)+d0 and u(a+h)+d1,
int_a^(a+h) |u'-uh'|² dx = h³/12+(d1-d0)²/h.

This is a theorem about a fixed one-dimensional analytic fixture,
not a general FEM a posteriori reliability bound or a Lean kernel proof.
"""
import json,math
from fractions import Fraction as Q
import sympy as S

def symbolic_identity():
    x,a,h,d0,d1=S.symbols("x a h d0 d1",real=True)
    u=lambda t:t*(1-t)/2
    left=a
    right=a+h
    uh=((right-x)*(u(left)+d0)+(x-left)*(u(right)+d1))/h
    derivative=S.diff(u(x)-uh,x)
    actual=S.integrate(S.expand(derivative**2),(x,a,right))
    expected=h**3/S.Integer(12)+(d1-d0)**2/h
    discrepancy=S.factor(actual-expected)
    if discrepancy!=0:
        raise AssertionError("independent energy identity mismatch")
    # Independently verify a wrong claimed identity is *not* equal.
    if S.factor(actual-h**3/S.Integer(12))==0:
        raise AssertionError("ignored nodal perturbation erroneously certified")
    if S.factor(actual-(d1-d0)**2/h)==0:
        raise AssertionError("ignored interpolation truncation erroneously certified")
    return str(discrepancy)

def exact_bracket(q,places=12):
    if q<=0:raise ValueError("expected positive energy squared")
    scale=10**places
    k=math.isqrt((q.numerator*scale*scale)//q.denominator)
    low=Q(k,scale);high=Q(k+1,scale)
    if not(low**2<=q<high**2):
        raise AssertionError("integer-isqrt proof obligation failed")
    flo=0. if k==0 else math.nextafter(float(low),-math.inf)
    fhi=math.nextafter(float(high),math.inf)
    if not Q.from_float(flo)**2<=q<=Q.from_float(fhi)**2:
        raise AssertionError("floating output failed outward enclosure")
    if fhi-flo>1e-10:
        raise AssertionError("interval too wide")
    return flo,fhi

def run():
    discrepancy=symbolic_identity()
    tested=0
    for n in (2,3,5,9,17,33):
        xs=[Q(i,n-1) for i in range(n)]
        for noise in (Q(0),Q(1,10**7),Q(-1,10**7)):
            d=[Q(0)]*n
            for i in range(1,n-1):d[i]=noise if i%2 else -noise
            error2=sum(((xs[i+1]-xs[i])**3/12 for i in range(n-1)),Q(0))
            error2+=sum(((d[i+1]-d[i])**2/(xs[i+1]-xs[i])
                         for i in range(n-1)),Q(0))
            lo,hi=exact_bracket(error2)
            assert 0<=lo<=hi and hi-lo<=1e-10
            tested+=1
    return {
      "schema_version":1,
      "experiment":"exact-quadratic-p1-energy-identity-v1",
      "independent_symbolic_oracle":"sympy==1.14.0",
      "symbolic_difference":discrepancy,
      "exact_rational_interval_cases":tested,
      "intentional_wrong_identities_rejected":2,
      "bound_specificity":"-u''=1, u(0)=u(1)=0, P1 on a mesh",
      "general_pde_reliability_proven":False,
      "lean_kernel_proof_of_energy_identity":False,
      "authority_expanded":False,
    }

if __name__=="__main__":
    print(json.dumps(run()))
