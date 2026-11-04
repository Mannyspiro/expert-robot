"""Exact-arithmetic prototype for multi-representation linear algebra.

Convention: each frame matrix P_i maps canonical coordinates to frame-i
coordinates. Thus T_{i->j} = P_j * inverse(P_i).
This v0.1 module covers invertible 2x2 rational linear frames only.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Sequence

Scalar = Fraction
Matrix2 = tuple[tuple[Scalar, Scalar], tuple[Scalar, Scalar]]
IDENTITY: Matrix2 = ((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1)))


def matrix(a: Sequence[Sequence[int | Fraction]]) -> Matrix2:
    if len(a) != 2 or any(len(row) != 2 for row in a):
        raise ValueError("expected a 2x2 matrix")
    return tuple(tuple(Fraction(x) for x in row) for row in a)  # type: ignore[return-value]


def multiply(a: Matrix2, b: Matrix2) -> Matrix2:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(2))
                       for j in range(2)) for i in range(2))  # type: ignore[return-value]


def determinant(a: Matrix2) -> Scalar:
    return a[0][0] * a[1][1] - a[0][1] * a[1][0]


def inverse(a: Matrix2) -> Matrix2:
    d = determinant(a)
    if d == 0:
        raise ValueError("frame matrix must be invertible")
    return ((a[1][1] / d, -a[0][1] / d),
            (-a[1][0] / d, a[0][0] / d))


def subtract(a: Matrix2, b: Matrix2) -> Matrix2:
    return tuple(tuple(a[i][j] - b[i][j] for j in range(2))
                 for i in range(2))  # type: ignore[return-value]


def trace(a: Matrix2) -> Scalar:
    return a[0][0] + a[1][1]


@dataclass(frozen=True)
class Frame:
    frame_id: str
    canonical_to_frame: Matrix2

    def __post_init__(self) -> None:
        if not self.frame_id:
            raise ValueError("frame_id must be non-empty")
        if determinant(self.canonical_to_frame) == 0:
            raise ValueError("frame matrix must be invertible")


@dataclass(frozen=True)
class PathAudit:
    path: tuple[str, ...]
    composed: Matrix2
    direct: Matrix2
    consistent: bool


class RepresentationGraph:
    """A finite family of coordinate frames for one underlying vector space."""

    def __init__(self, frames: Iterable[Frame]):
        items = tuple(frames)
        self.frames = {item.frame_id: item for item in items}
        if not self.frames:
            raise ValueError("at least one frame is required")
        if len(self.frames) != len(items):
            raise ValueError("frame IDs must be unique")

    def transition(self, source: str, target: str) -> Matrix2:
        """Return the exact coordinate map source -> target."""
        try:
            src = self.frames[source].canonical_to_frame
            dst = self.frames[target].canonical_to_frame
        except KeyError as exc:
            raise KeyError(f"unknown frame: {exc.args[0]}") from exc
        return multiply(dst, inverse(src))

    def compose_path(self, path: Sequence[str]) -> Matrix2:
        if len(path) < 2:
            raise ValueError("path must contain at least two frame IDs")
        result = IDENTITY
        for source, target in zip(path, path[1:]):
            result = multiply(self.transition(source, target), result)
        return result

    def audit_path(self, path: Sequence[str]) -> PathAudit:
        if len(path) < 3:
            raise ValueError("audit path must include an intermediate frame")
        direct = self.transition(path[0], path[-1])
        composed = self.compose_path(path)
        return PathAudit(tuple(path), composed, direct, composed == direct)

    def represented_operator(self, operator: Matrix2, frame_id: str) -> Matrix2:
        """Conjugate an operator into the selected frame."""
        p = self.frames[frame_id].canonical_to_frame
        return multiply(multiply(p, operator), inverse(p))

    def spectral_signature(self, operator: Matrix2, frame_id: str) -> tuple[Scalar, Scalar]:
        """Return (trace, determinant), the coefficients of the 2x2 characteristic polynomial."""
        represented = self.represented_operator(operator, frame_id)
        return trace(represented), determinant(represented)


def cycle_is_identity(graph: RepresentationGraph, cycle: Sequence[str]) -> bool:
    if len(cycle) < 2 or cycle[0] != cycle[-1]:
        raise ValueError("cycle must start and end at the same frame")
    return graph.compose_path(cycle) == IDENTITY
