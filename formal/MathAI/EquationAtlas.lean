import Mathlib

namespace MathAI.EquationAtlas

/-- The square of a real number is nonnegative. -/
theorem square_nonnegative (x : ℝ) : 0 ≤ x ^ 2 := by
  exact sq_nonneg x

/-- Algebraic inequality used to prove the balanced-rectangle bound. -/
theorem square_sum_ge_four_product (x y : ℝ) :
    4 * x * y ≤ (x + y) ^ 2 := by
  nlinarith [sq_nonneg (x - y)]

/-- The normalized logistic growth term is nonnegative on [0,1]. -/
theorem normalized_logistic_growth_nonnegative
    (r p : ℝ) (hr : 0 ≤ r) (hp : 0 ≤ p) (hp_le_one : p ≤ 1) :
    0 ≤ r * p * (1 - p) := by
  have hfactor : 0 ≤ 1 - p := by linarith
  exact mul_nonneg hr (mul_nonneg hp hfactor)

end MathAI.EquationAtlas
