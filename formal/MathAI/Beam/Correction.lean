import Mathlib

/-!
Exact algebraic correction obligations for the stored beam system.
Injectivity is an explicit hypothesis. Deriving it from the checked LDL
witness, and connecting these propositions to the Python parser, remain open.
-/

namespace MathAI.Beam

variable {ι : Type*}

/-- An exact residual correction produces an exact solution. -/
theorem corrected_solution
    (A : (ι → ℚ) →ₗ[ℚ] (ι → ℚ)) (u b delta : ι → ℚ)
    (correction : A delta = b - A u) :
    A (u + delta) = b := by
  rw [map_add, correction]
  abel

/-- With injectivity, the corrected solution is the unique exact solution. -/
theorem exact_error
    (A : (ι → ℚ) →ₗ[ℚ] (ι → ℚ)) (u b delta exact : ι → ℚ)
    (injective : Function.Injective A)
    (correction : A delta = b - A u) (solution : A exact = b) :
    exact - u = delta := by
  have equal : exact = u + delta := injective
    (solution.trans (corrected_solution A u b delta correction).symm)
  rw [equal]
  abel

/-- Checked coordinate endpoints bound the error in any exact solution. -/
theorem coordinate_error_bound
    (A : (ι → ℚ) →ₗ[ℚ] (ι → ℚ)) (u b delta exact : ι → ℚ)
    (injective : Function.Injective A)
    (correction : A delta = b - A u) (solution : A exact = b)
    (bound : ℚ) (endpoints : ∀ i, |delta i| ≤ bound) :
    ∀ i, |exact i - u i| ≤ bound := by
  intro i
  have error := congrFun (exact_error A u b delta exact injective correction solution) i
  change exact i - u i = delta i at error
  rw [error]
  exact endpoints i

end MathAI.Beam
