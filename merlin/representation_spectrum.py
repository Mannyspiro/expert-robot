"""Exact generalized eigenspaces with explicit scalar-field provenance.

The executable backend is currently Q (Fractions). Metadata may describe
other fields, but this implementation refuses to silently compute over them.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal
from merlin.representation_graph import Matrix, Scalar, identity, multiply

FieldKind = Literal["Q", "R", "C", "algebraic_extension"]

@dataclass(frozen=True)
class ScalarFieldMetadata:
    kind: FieldKind
    field_id: str
    characteristic: int = 0
    algebraic_closure_id: str | None = None
    exact_backend: str = "python-fractions"

    def __post_init__(self) -> None:
        if not self.field_id:
            raise ValueError("field_id must be non-empty")
        if self.characteristic < 0:
            raise ValueError("field characteristic cannot be negative")
        if self.kind == "algebraic_extension" and not self.algebraic_closure_id:
            raise ValueError("algebraic extensions require a closure identifier")

@dataclass(frozen=True)
class GeneralizedEigenspace:
    field: ScalarFieldMetadata
    eigenvalue: Scalar
    exponent: int
    basis: tuple[tuple[Scalar, ...], ...]
    dimension: int

def _subtract(a: Matrix, b: Matrix) -> Matrix:
    if len(a) != len(b) or any(len(x) != len(y) for x, y in zip(a, b)):
        raise ValueError("matrix dimensions must agree")
    return tuple(tuple(x-y for x,y in zip(ar,br)) for ar,br in zip(a,b))

def _power(a: Matrix, n: int) -> Matrix:
    if n < 0:
        raise ValueError("matrix exponent must be non-negative")
    result = identity(len(a))
    for _ in range(n):
        result = multiply(result, a)
    return result

def nullspace_basis(a: Matrix) -> tuple[tuple[Scalar, ...], ...]:
    """Exact RREF nullspace basis; basis vectors are returned as rows."""
    if not a or any(len(row) != len(a[0]) for row in a):
        raise ValueError("nullspace requires a non-empty rectangular matrix")
    work = [list(row) for row in a]
    rows, cols = len(work), len(work[0])
    pivots, pivot_row = [], 0
    for col in range(cols):
        candidate = next((r for r in range(pivot_row, rows) if work[r][col]), None)
        if candidate is None:
            continue
        work[pivot_row], work[candidate] = work[candidate], work[pivot_row]
        scale = work[pivot_row][col]
        work[pivot_row] = [x/scale for x in work[pivot_row]]
        for r in range(rows):
            if r != pivot_row and work[r][col]:
                factor = work[r][col]
                work[r] = [work[r][j]-factor*work[pivot_row][j] for j in range(cols)]
        pivots.append(col)
        pivot_row += 1
        if pivot_row == rows:
            break
    free = [c for c in range(cols) if c not in pivots]
    vectors = []
    for free_col in free:
        vector = [Fraction(0) for _ in range(cols)]
        vector[free_col] = Fraction(1)
        for r, pivot_col in enumerate(pivots):
            vector[pivot_col] = -work[r][free_col]
        vectors.append(tuple(vector))
    return tuple(vectors)

def generalized_eigenspace(a: Matrix, eigenvalue: Scalar, exponent: int,
                           field: ScalarFieldMetadata) -> GeneralizedEigenspace:
    """Compute ker((A-lambda I)^exponent) exactly over Q.

    The exponent is explicit and bounded by matrix dimension. This computes
    the generalized-eigenspace filtration, not a Jordan canonical form.
    """
    if field.kind != "Q" or field.exact_backend != "python-fractions":
        raise NotImplementedError("the current exact backend supports Q only")
    n = len(a)
    if n == 0 or any(len(row) != n for row in a):
        raise ValueError("generalized eigenspace requires a non-empty square matrix")
    if exponent < 1 or exponent > n:
        raise ValueError("exponent must be between 1 and matrix dimension")
    shifted = _subtract(a, tuple(tuple(Fraction(eigenvalue) if i == j else Fraction(0)
                                       for j in range(n)) for i in range(n)))
    basis = nullspace_basis(_power(shifted, exponent))
    return GeneralizedEigenspace(field, Fraction(eigenvalue), exponent, basis, len(basis))
