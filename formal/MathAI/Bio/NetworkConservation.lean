import Mathlib

/-!
An exact rational stoichiometric invariant over arbitrary finite species.
No physical model, concentration units, membrane flux, or CACE solver
correspondence is established by this purely algebraic theorem.
-/
namespace MathAI.Bio

theorem weighted_conservation_single_reaction
    {n : ℕ} (weights state column : Fin n → ℚ) (flux : ℚ)
    (h : (∑ i, weights i * column i) = 0) :
    (∑ i, weights i * (state i + column i * flux)) =
      ∑ i, weights i * state i := by
  calc
    (∑ i, weights i * (state i + column i * flux)) =
        ∑ i, (weights i * state i + (weights i * column i) * flux) := by
          apply Finset.sum_congr rfl
          intro i hi
          ring
    _ = (∑ i, weights i * state i) +
        (∑ i, (weights i * column i) * flux) := by
          rw [Finset.sum_add_distrib]
    _ = ∑ i, weights i * state i := by
          rw [← Finset.sum_mul, h]
          simp

end MathAI.Bio
