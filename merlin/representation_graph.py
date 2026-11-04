"""Exact-arithmetic prototype for multi-representation linear algebra.

Convention: each frame matrix P_i maps canonical coordinates to frame-i
coordinates. Thus T_{i->j} = P_j * inverse(P_i).
The implementation supports finite-dimensional square rational matrices.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Sequence

Scalar = Fraction
Matrix = tuple[tuple[Scalar, ...], ...]


def matrix(rows: Sequence[Sequence[int | Fraction]]) -> Matrix:
    if not rows or any(len(row) != len(rows) for row in rows):
        raise ValueError("expected a non-empty square matrix")
    return tuple(tuple(Fraction(x) for x in row) for row in rows)


def identity(n: int) -> Matrix:
    if n < 1:
        raise ValueError("matrix dimension must be positive")
    return tuple(tuple(Fraction(int(i == j)) for j in range(n))
                 for i in range(n))


def _same_shape(a: Matrix, b: Matrix) -> None:
    if not a or len(a) != len(b) or any(len(x) != len(y) for x, y in zip(a, b)):
        raise ValueError("matrix dimensions must agree")


def multiply(a: Matrix, b: Matrix) -> Matrix:
    if not a or not b or len(a[0]) != len(b):
        raise ValueError("incompatible matrix dimensions")
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(len(b)))
                       for j in range(len(b[0]))) for i in range(len(a)))


def determinant(a: Matrix) -> Scalar:
    n = len(a)
    if n == 0 or any(len(row) != n for row in a):
        raise ValueError("determinant requires a non-empty square matrix")
    work = [list(row) for row in a]
    sign, result = 1, Fraction(1)
    for col in range(n):
        pivot = next((r for r in range(col, n) if work[r][col] != 0), None)
        if pivot is None:
            return Fraction(0)
        if pivot != col:
            work[col], work[pivot] = work[pivot], work[col]
            sign *= -1
        value = work[col][col]
        result *= value
        for row in range(col + 1, n):
            factor = work[row][col] / value
            for j in range(col + 1, n):
                work[row][j] -= factor * work[col][j]
    return result * sign


def inverse(a: Matrix) -> Matrix:
    n = len(a)
    if n == 0 or any(len(row) != n for row in a):
        raise ValueError("inverse requires a non-empty square matrix")
    work = [list(a[i]) + list(identity(n)[i]) for i in range(n)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if work[r][col] != 0), None)
        if pivot is None:
            raise ValueError("frame matrix must be invertible")
        work[col], work[pivot] = work[pivot], work[col]
        scale = work[col][col]
        work[col] = [x / scale for x in work[col]]
        for row in range(n):
            if row == col:
                continue
            factor = work[row][col]
            work[row] = [work[row][j] - factor * work[col][j] for j in range(2 * n)]
    return tuple(tuple(work[i][n:]) for i in range(n))


def trace(a: Matrix) -> Scalar:
    if not a or any(len(row) != len(a) for row in a):
        raise ValueError("trace requires a non-empty square matrix")
    return sum((a[i][i] for i in range(len(a))), Fraction(0))


@dataclass(frozen=True)
class Frame:
    frame_id: str
    canonical_to_frame: Matrix

    def __post_init__(self) -> None:
        if not self.frame_id:
            raise ValueError("frame_id must be non-empty")
        if determinant(self.canonical_to_frame) == 0:
            raise ValueError("frame matrix must be invertible")


@dataclass(frozen=True)
class PathAudit:
    path: tuple[str, ...]
    composed: Matrix
    direct: Matrix
    consistent: bool


class RepresentationGraph:
    """A finite family of coordinate frames for one vector space."""

    def __init__(self, frames: Iterable[Frame]):
        items = tuple(frames)
        self.frames = {item.frame_id: item for item in items}
        if not self.frames:
            raise ValueError("at least one frame is required")
        if len(self.frames) != len(items):
            raise ValueError("frame IDs must be unique")
        dimensions = {len(item.canonical_to_frame) for item in items}
        if len(dimensions) != 1:
            raise ValueError("all frames must have the same dimension")
        self.dimension = dimensions.pop()

    def transition(self, source: str, target: str) -> Matrix:
        """Return the exact coordinate map source -> target."""
        try:
            src = self.frames[source].canonical_to_frame
            dst = self.frames[target].canonical_to_frame
        except KeyError as exc:
            raise KeyError(f"unknown frame: {exc.args[0]}") from exc
        return multiply(dst, inverse(src))

    def compose_path(self, path: Sequence[str]) -> Matrix:
        if len(path) < 2:
            raise ValueError("path must contain at least two frame IDs")
        result = identity(self.dimension)
        for source, target in zip(path, path[1:]):
            result = multiply(self.transition(source, target), result)
        return result

    def audit_path(self, path: Sequence[str]) -> PathAudit:
        if len(path) < 3:
            raise ValueError("audit path must include an intermediate frame")
        direct = self.transition(path[0], path[-1])
        composed = self.compose_path(path)
        return PathAudit(tuple(path), composed, direct, composed == direct)

    def represented_operator(self, operator: Matrix, frame_id: str) -> Matrix:
        """Conjugate an operator into the selected frame."""
        if len(operator) != self.dimension or any(len(row) != self.dimension for row in operator):
            raise ValueError("operator dimension must match frame dimension")
        p = self.frames[frame_id].canonical_to_frame
        return multiply(multiply(p, operator), inverse(p))

    def spectral_signature(self, operator: Matrix, frame_id: str) -> tuple[Scalar, Scalar]:
        """Return trace and determinant invariants (not the full characteristic polynomial for n > 2)."""
        represented = self.represented_operator(operator, frame_id)
        return trace(represented), determinant(represented)


def cycle_is_identity(graph: RepresentationGraph, cycle: Sequence[str]) -> bool:
    if len(cycle) < 2 or cycle[0] != cycle[-1]:
        raise ValueError("cycle must start and end at the same frame")
    return graph.compose_path(cycle) == identity(graph.dimension)
