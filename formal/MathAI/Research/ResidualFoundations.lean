import Mathlib

/-!
# Residual research foundations

These are generic mathematical lemmas that can support later model-specific
formalizations. They do not certify any physical parameter estimate.
-/

namespace MathAI.Research

/--
An affine scalar equation over the rationals has at most one root when its
linear coefficient is nonzero. This is a reusable exact lemma for checking
uniqueness of scalar fixed-point candidates once a concrete beta function
has actually been specified.
-/
theorem affine_root_unique
    (a b x y : ℚ)
    (ha : a ≠ 0)
    (hx : a * x + b = 0)
    (hy : a * y + b = 0) :
    x = y := by
  have hxy : a * x = a * y := by
    linarith
  exact mul_left_cancel₀ ha hxy

end MathAI.Research
