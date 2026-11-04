"""Exact quaternion, SO(3) matrix and Cl(3,0) rotor correspondence.

Quaternion convention: q=(w,x,y,z), active rotation v' = q v q^{-1}.
Cl(3,0) convention: e1^2=e2^2=e3^2=+1 and
i -> -e23, j -> -e31 (= +e13), k -> -e12.
All arithmetic is exact over Fraction.
"""
from __future__ import annotations
from fractions import Fraction
from typing import Sequence

Q = tuple[Fraction, Fraction, Fraction, Fraction]
V3 = tuple[Fraction, Fraction, Fraction]
M3 = tuple[tuple[Fraction, Fraction, Fraction], ...]
GA3 = tuple[Fraction, Fraction, Fraction, Fraction, Fraction, Fraction, Fraction, Fraction]


def quaternion(values: Sequence[int | Fraction]) -> Q:
    if len(values) != 4:
        raise ValueError("quaternion requires (w, x, y, z)")
    return tuple(Fraction(x) for x in values)  # type: ignore[return-value]


def vector3(values: Sequence[int | Fraction]) -> V3:
    if len(values) != 3:
        raise ValueError("3D vector requires three components")
    return tuple(Fraction(x) for x in values)  # type: ignore[return-value]


def qmul(a: Q, b: Q) -> Q:
    w,x,y,z=a; v,a1,b1,c1=b
    return (w*v-x*a1-y*b1-z*c1,
            w*a1+x*v+y*c1-z*b1,
            w*b1-x*c1+y*v+z*a1,
            w*c1+x*b1-y*a1+z*v)


def qconj(q: Q) -> Q:
    return (q[0], -q[1], -q[2], -q[3])


def qnorm_sq(q: Q) -> Fraction:
    return sum((x*x for x in q), Fraction(0))


def _require_unit(q: Q) -> None:
    if qnorm_sq(q) != 1:
        raise ValueError("rotation quaternion must have unit norm")


def qrotate(q: Q, v: V3) -> V3:
    _require_unit(q)
    pure = (Fraction(0), *v)
    result = qmul(qmul(q, pure), qconj(q))
    if result[0] != 0:
        raise ArithmeticError("unit quaternion action did not preserve pure vectors")
    return (result[1], result[2], result[3])


def q_to_matrix(q: Q) -> M3:
    _require_unit(q)
    w,x,y,z=q
    return (
        (1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)),
        (2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)),
        (2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)),
    )


def matrix_rotate(m: M3, v: V3) -> V3:
    return tuple(sum(m[i][j]*v[j] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def _blade_sign(a: int, b: int) -> int:
    swaps=sum(1 for i in range(3) if a & (1<<i)
              for j in range(3) if (b & (1<<j)) and i>j)
    return -1 if swaps % 2 else 1


def gp(a: GA3, b: GA3) -> GA3:
    out=[Fraction(0) for _ in range(8)]
    for i,ai in enumerate(a):
        if not ai: continue
        for j,bj in enumerate(b):
            if not bj: continue
            out[i ^ j] += _blade_sign(i,j)*ai*bj
    return tuple(out)  # type: ignore[return-value]


def ga_reverse(a: GA3) -> GA3:
    out=[]
    for blade, coeff in enumerate(a):
        grade=blade.bit_count()
        sign=-1 if (grade*(grade-1)//2) % 2 else 1
        out.append(sign*coeff)
    return tuple(out)  # type: ignore[return-value]


def quaternion_to_rotor(q: Q) -> GA3:
    _require_unit(q)
    w,x,y,z=q
    # q = w + x(-e23) + y(e13) + z(-e12)
    return (w, Fraction(0), Fraction(0), -z, Fraction(0), y, -x, Fraction(0))


def ga_vector(v: V3) -> GA3:
    x,y,z=v
    return (Fraction(0),x,y,z*0,Fraction(0),Fraction(0),Fraction(0),Fraction(0)) if False else (
        Fraction(0), x, y, Fraction(0), z, Fraction(0), Fraction(0), Fraction(0)
    )


def rotor_rotate(q: Q, v: V3) -> V3:
    rotor=quaternion_to_rotor(q)
    result=gp(gp(rotor,ga_vector(v)),ga_reverse(rotor))
    if any(result[i] != 0 for i in (0,3,5,6,7)):
        raise ArithmeticError("rotor sandwich produced non-vector grades")
    return (result[1],result[2],result[4])
