"""Numerical spherical parallel transport and holonomy experiment.

The unit sphere uses its induced Levi-Civita connection. Along a shortest
great-circle segment p -> q, parallel transport is the ambient 3D rotation
taking p to q in their spanning plane. Floating-point tolerances are explicit.
"""
from __future__ import annotations
import math
from typing import Sequence

Vec3 = tuple[float, float, float]
TOL = 1e-10


def vec3(values: Sequence[float]) -> Vec3:
    if len(values) != 3:
        raise ValueError("expected a 3D vector")
    return (float(values[0]), float(values[1]), float(values[2]))


def dot(a: Vec3, b: Vec3) -> float:
    return sum(a[i] * b[i] for i in range(3))


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1]*b[2]-a[2]*b[1],
            a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0])


def norm(a: Vec3) -> float:
    return math.sqrt(dot(a, a))


def scale(a: Vec3, k: float) -> Vec3:
    return (k*a[0], k*a[1], k*a[2])


def add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])


def normalize(a: Vec3) -> Vec3:
    length = norm(a)
    if length <= TOL:
        raise ValueError("cannot normalize a zero vector")
    return scale(a, 1.0/length)


def parallel_transport_geodesic(p: Vec3, q: Vec3, tangent: Vec3) -> Vec3:
    """Levi-Civita parallel transport along the shorter great-circle arc."""
    if abs(norm(p)-1.0) > TOL or abs(norm(q)-1.0) > TOL:
        raise ValueError("sphere endpoints must be unit vectors")
    if abs(dot(p, tangent)) > TOL:
        raise ValueError("initial vector must be tangent at the start point")
    axis_raw = cross(p, q)
    sine = norm(axis_raw)
    cosine = max(-1.0, min(1.0, dot(p, q)))
    if sine <= TOL:
        if cosine > 0:
            return tangent
        raise ValueError("antipodal endpoints have no unique shorter geodesic")
    axis = scale(axis_raw, 1.0/sine)
    angle = math.atan2(sine, cosine)
    # Rodrigues rotation of the tangent vector about the great-circle normal.
    transported = add(
        add(scale(tangent, math.cos(angle)),
            scale(cross(axis, tangent), math.sin(angle))),
        scale(axis, dot(axis, tangent)*(1.0-math.cos(angle))),
    )
    if abs(dot(q, transported)) > 1e-8:
        raise ArithmeticError("transported vector is not tangent at endpoint")
    return transported


def transport_loop(vertices: Sequence[Vec3], tangent: Vec3) -> Vec3:
    if len(vertices) < 3:
        raise ValueError("a spherical loop requires at least three vertices")
    result = tangent
    for i in range(len(vertices)):
        result = parallel_transport_geodesic(vertices[i], vertices[(i+1) % len(vertices)], result)
    return result


def oriented_spherical_triangle_area(a: Vec3, b: Vec3, c: Vec3) -> float:
    """Signed area of the smaller oriented geodesic triangle on the unit sphere."""
    for p in (a, b, c):
        if abs(norm(p)-1.0) > TOL:
            raise ValueError("triangle vertices must be unit vectors")
    numerator = dot(a, cross(b, c))
    denominator = 1.0 + dot(a,b) + dot(b,c) + dot(c,a)
    if abs(numerator) <= TOL and abs(denominator) <= TOL:
        raise ValueError("degenerate or ambiguous spherical triangle")
    return 2.0 * math.atan2(numerator, denominator)


def signed_holonomy_angle(base: Vec3, initial: Vec3, final: Vec3) -> float:
    """Signed tangent-plane rotation from initial to final at base."""
    if abs(norm(base)-1.0) > TOL:
        raise ValueError("base point must be on the unit sphere")
    if abs(dot(base, initial)) > TOL or abs(dot(base, final)) > 1e-8:
        raise ValueError("vectors must be tangent at the base point")
    return math.atan2(dot(base, cross(initial, final)), dot(initial, final))
