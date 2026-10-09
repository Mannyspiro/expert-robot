import Mathlib

/-!
Exact criterion for a linear observable to annihilate *all* directed
unit-transfer edge fluxes. For a one-to-one transfer e : src → dst the
observable changes by (weight dst - weight src) * flux e.

This is an edgewise characterization, not yet the stronger theorem that
the left nullspace has a basis of undirected component indicators.
It says nothing about nonlinear kinetics, chemistry validity or numerical
solver correctness.
-/

namespace MathAI.Bio

/-- Over exact rationals, a weighted sum of arbitrary transfer fluxes is
zero for *every* choice of flux if and only if each transfer preserves
the vertex weight. -/
theorem transfer_flux_pairing_zero_iff
    {species reactions : ℕ}
    (edge : Fin reactions → Fin species × Fin species)
    (weight : Fin species → ℚ) :
    (∀ rate : Fin reactions → ℚ,
      (∑ e : Fin reactions,
        (weight (edge e).2 - weight (edge e).1) * rate e) = 0) ↔
    (∀ e : Fin reactions,
      weight (edge e).1 = weight (edge e).2) := by
  constructor
  · intro h e
    have hz := h (fun j => if j = e then (1 : ℚ) else 0)
    have hdelta : weight (edge e).2 - weight (edge e).1 = 0 := by
      simpa [mul_ite] using hz
    exact (sub_eq_zero.mp hdelta).symm
  · intro heq rate
    apply Finset.sum_eq_zero
    intro e _
    rw [← heq e]
    ring

/-- The all-ones mass observable satisfies the edgewise conservation
condition for every finite directed unit-transfer graph. -/
theorem transfer_graph_total_mass_flux_zero
    {species reactions : ℕ}
    (edge : Fin reactions → Fin species × Fin species)
    (rate : Fin reactions → ℚ) :
    (∑ e : Fin reactions, ((1 : ℚ) - 1) * rate e) = 0 := by
  simp

end MathAI.Bio
