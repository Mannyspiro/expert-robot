import Mathlib

namespace MathAI.RepresentationInvariants

variable {R : Type*} [CommRing R]
variable {ι : Type*} [Fintype ι] [DecidableEq ι]

/-- Similar matrices have equal characteristic polynomials.

The unit matrix encodes the invertible change of basis. This is the
kernel-checked algebraic statement behind the finite exact Python tests.
-/
theorem charpoly_conjugate_by_unit
    (P : (Matrix ι ι R)ˣ) (A : Matrix ι ι R) :
    ((P : Matrix ι ι R) * A * (P : Matrix ι ι R)⁻¹).charpoly = A.charpoly := by
  exact Matrix.charpoly_units_conj P A

end MathAI.RepresentationInvariants
