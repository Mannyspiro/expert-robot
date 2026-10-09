import Mathlib

/-!
Conditional energy-defect bound motivated by molecular residual experiments.
The lower quadratic model is a hypothesis, not a conclusion from an orbital
gap. This module does not certify molecular Hessians, neighborhoods, spin
branches, floating-point calculations, or global electronic ground states.
-/

namespace MathAI.Molecular

/-- Completing the square bounds the defect under a positive-curvature model.
Here `r` and `d` can represent a residual norm and displacement norm after
an independently justified reduction to this scalar model. -/
theorem energy_defect_bound
    (mu r d defect : ℝ) (positive_curvature : 0 < mu)
    (quadratic_model : defect ≤ r * d - (mu / 2) * d ^ 2) :
    defect ≤ r ^ 2 / (2 * mu) := by
  apply (le_div_iff₀ (show 0 < 2 * mu by positivity)).2
  have scaled := mul_le_mul_of_nonneg_left quadratic_model
    (show 0 ≤ 2 * mu by positivity)
  nlinarith [sq_nonneg (r - mu * d)]

/-- A checked residual endpoint yields a conservative defect endpoint. -/
theorem energy_endpoint_bound
    (mu r d defect endpoint : ℝ) (positive_curvature : 0 < mu)
    (quadratic_model : defect ≤ r * d - (mu / 2) * d ^ 2)
    (checked_endpoint : r ^ 2 ≤ 2 * mu * endpoint) :
    defect ≤ endpoint := by
  have bound := energy_defect_bound mu r d defect positive_curvature quadratic_model
  have endpoint_bound : r ^ 2 / (2 * mu) ≤ endpoint := by
    apply (div_le_iff₀ (show 0 < 2 * mu by positivity)).2
    nlinarith [checked_endpoint]
  exact bound.trans endpoint_bound

end MathAI.Molecular
