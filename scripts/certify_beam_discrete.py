#!/usr/bin/env python3
"""Checked rational witnesses for error in a stored binary64 SPD system.

This bounds solver error only: no assembly, continuum, material or Lean claim.
L D L^T = A with positive D establishes SPD; A delta = b-Au identifies the
exact correction. Floating upper endpoints are checked as exact rationals.
"""
import hashlib
import json
import math
from fractions import Fraction as F

MAX_DOFS, MAX_BITS, MAX_BYTES = 32, 8192, 1048576
SCOPE = "exact-solution-of-stored-binary64-beam-system"


def bounded(x):
    if max(x.numerator.bit_length(), x.denominator.bit_length()) > MAX_BITS:
        raise ValueError("rational witness exceeds bit budget")
    return x


def inputs(matrix, rhs, solution):
    n = len(rhs)
    if not 1 <= n <= MAX_DOFS or len(matrix) != n or len(solution) != n or any(len(row) != n for row in matrix):
        raise ValueError("certificate requires a square system with 1–32 DOFs")
    def number(x):
        if type(x) not in (int, float):
            raise ValueError("binary64 numeric input required")
        try:
            x = float(x)
        except OverflowError as exc:
            raise ValueError("input overflow") from exc
        if not math.isfinite(x):
            raise ValueError("finite input required")
        return x
    a = [[number(x) for x in row] for row in matrix]
    b, u = [number(x) for x in rhs], [number(x) for x in solution]
    digest = hashlib.sha256(json.dumps([[x.hex() for row in a for x in row],
        [x.hex() for x in b], [x.hex() for x in u]], separators=(",",":")).encode()).hexdigest()
    a, b, u = [[F.from_float(x) for x in row] for row in a], list(map(F.from_float,b)), list(map(F.from_float,u))
    if any(a[i][j] != a[j][i] for i in range(n) for j in range(i)):
        raise ValueError("stored matrix is not exactly symmetric")
    return a, b, u, digest


def upper(x):
    if x < 0:
        raise ValueError("nonnegative upper endpoint required")
    try:
        result = float(x)
    except OverflowError as exc:
        raise ValueError("bound overflow") from exc
    for _ in range(8):
        if not math.isfinite(result):
            raise ValueError("finite bound required")
        if F.from_float(result) >= x:
            return result
        result = math.nextafter(result, math.inf)
    raise ValueError("failed to enclose rational bound")


def sqrt_upper(x):
    if x < 0:
        raise ValueError("negative squared norm")
    if not x:
        return 0.0
    power = (x.numerator.bit_length()-x.denominator.bit_length())//2
    scaled = x / F(2)**(2*power)
    try:
        result = math.ldexp(math.sqrt(float(scaled)), power)
    except OverflowError as exc:
        raise ValueError("root bound overflow") from exc
    for _ in range(8):
        if not math.isfinite(result):
            raise ValueError("finite root bound required")
        if F.from_float(result)**2 >= x:
            return result
        result = math.nextafter(result, math.inf)
    raise ValueError("failed to enclose rational root")


def encode(x):
    bounded(x)
    return [str(x.numerator), str(x.denominator)]


def decode(value):
    if not isinstance(value,list) or len(value) != 2 or any(type(x) is not str or not 1 <= len(x) <= 2500 for x in value):
        raise ValueError("invalid rational witness encoding")
    try:
        if int(value[1]) <= 0:
            raise ValueError("positive denominator required")
        return bounded(F(int(value[0]),int(value[1])))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("invalid rational witness") from exc


def certify(matrix, rhs, solution):
    a, b, u, digest = inputs(matrix,rhs,solution)
    n = len(b)
    lower = [[F(int(i==j)) for j in range(n)] for i in range(n)]
    diagonal = []
    for j in range(n):
        d = bounded(a[j][j]-sum(lower[j][k]**2*diagonal[k] for k in range(j)))
        if d <= 0:
            raise ValueError("stored operator is not SPD")
        diagonal.append(d)
        for i in range(j+1,n):
            lower[i][j] = bounded((a[i][j]-sum(lower[i][k]*diagonal[k]*lower[j][k] for k in range(j)))/d)
    residual = [bounded(b[i]-sum(a[i][j]*u[j] for j in range(n))) for i in range(n)]
    y = []
    for i in range(n):
        y.append(bounded(residual[i]-sum(lower[i][j]*y[j] for j in range(i))))
    z = [bounded(y[i]/diagonal[i]) for i in range(n)]
    delta = [F(0)]*n
    for i in reversed(range(n)):
        delta[i] = bounded(z[i]-sum(lower[j][i]*delta[j] for j in range(i+1,n)))
    energy2 = bounded(sum(residual[i]*delta[i] for i in range(n)))
    certificate = {
        "schema_version":"0.1", "scope":SCOPE, "dofs":n, "system_sha256":digest,
        "promotion_authority":False, "continuum_error_certified":False,
        "lower":[[i,j,encode(lower[i][j])] for i in range(n) for j in range(i) if lower[i][j]],
        "diagonal":list(map(encode,diagonal)), "correction":list(map(encode,delta)),
        "exact_residual_inf_upper_n":upper(max(map(abs,residual))),
        "scaled_dof_linf_error_upper_m":upper(max(map(abs,delta))),
        "energy_error_squared_j":encode(energy2), "energy_error_sqrt_j_upper":sqrt_upper(energy2),
        "checker":"exact LDL reconstruction, correction identity and rational endpoint inequalities",
    }
    verify_certificate(matrix,rhs,solution,certificate)
    return certificate


def verify_certificate(matrix, rhs, solution, certificate):
    """Check witnesses without calling the factorizer or solving a system."""
    a, b, u, digest = inputs(matrix,rhs,solution)
    n = len(b)
    c = certificate
    if c.get("scope") != SCOPE or c.get("schema_version") != "0.1" or c.get("dofs") != n or c.get("system_sha256") != digest:
        raise ValueError("certificate binding mismatch")
    if c.get("promotion_authority") is not False or c.get("continuum_error_certified") is not False:
        raise ValueError("certificate scope/authority mismatch")
    if not isinstance(c.get("lower"),list) or len(c["lower"]) > n*(n-1)//2 or len(c.get("diagonal",[])) != n or len(c.get("correction",[])) != n:
        raise ValueError("invalid witness dimensions")
    if len(json.dumps(c)) > MAX_BYTES:
        raise ValueError("certificate exceeds byte budget")
    lower = [[F(int(i==j)) for j in range(n)] for i in range(n)]
    seen = set()
    for row in c["lower"]:
        if not isinstance(row,list) or len(row) != 3:
            raise ValueError("invalid lower-triangle entry")
        i,j,value = row
        if type(i) is not int or type(j) is not int or not 0 <= j < i < n or (i,j) in seen:
            raise ValueError("invalid/duplicate witness coordinates")
        seen.add((i,j))
        lower[i][j] = decode(value)
    diagonal, delta = list(map(decode,c["diagonal"])), list(map(decode,c["correction"]))
    if any(d <= 0 for d in diagonal):
        raise ValueError("nonpositive SPD witness")
    for i in range(n):
        for j in range(n):
            reconstructed = bounded(sum(lower[i][k]*diagonal[k]*lower[j][k] for k in range(min(i,j)+1)))
            if reconstructed != a[i][j]:
                raise ValueError("LDL witness does not reconstruct stored matrix")
    residual = [bounded(b[i]-sum(a[i][j]*u[j] for j in range(n))) for i in range(n)]
    if any(bounded(sum(a[i][j]*delta[j] for j in range(n))) != residual[i] for i in range(n)):
        raise ValueError("correction identity fails")
    energy2 = bounded(sum(delta[i]*a[i][j]*delta[j] for i in range(n) for j in range(n)))
    if energy2 < 0 or decode(c["energy_error_squared_j"]) != energy2:
        raise ValueError("energy witness mismatch")
    for key, exact, squared in [
        ("exact_residual_inf_upper_n",max(map(abs,residual)),False),
        ("scaled_dof_linf_error_upper_m",max(map(abs,delta)),False),
        ("energy_error_sqrt_j_upper",energy2,True)]:
        value = c.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or value < 0:
            raise ValueError("invalid upper endpoint")
        rational = F.from_float(float(value))
        if (rational**2 if squared else rational) < exact:
            raise ValueError("upper endpoint does not enclose exact error")
    return True
