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

/-- Exact weighted amount accounting with an explicit boundary/source contribution.
    This is an algebraic one-step identity; no stability or positivity claim. -/
theorem weighted_balance_with_boundary
    {n : ℕ} (weights state reaction boundary : Fin n → ℚ) (dt : ℚ)
    (hreaction : (∑ i, weights i * reaction i) = 0) :
    (∑ i, weights i * (state i + dt * (reaction i + boundary i))) =
      (∑ i, weights i * state i) +
        dt * (∑ i, weights i * boundary i) := by
  calc
    (∑ i, weights i * (state i + dt * (reaction i + boundary i))) =
        ∑ i, (weights i * state i + dt * (weights i * reaction i) +
          dt * (weights i * boundary i)) := by
            apply Finset.sum_congr rfl
            intro i hi
            ring
    _ = (∑ i, weights i * state i) +
        dt * (∑ i, weights i * reaction i) +
        dt * (∑ i, weights i * boundary i) := by
          simp only [Finset.sum_add_distrib, ← Finset.mul_sum]
    _ = (∑ i, weights i * state i) +
        dt * (∑ i, weights i * boundary i) := by
          rw [hreaction]
          ring

/-- A finite stoichiometric matrix preserves any left-nullspace weight,
    except for explicitly modeled boundary sources. The rates are arbitrary:
    no kinetic or biological mechanism is assumed. -/
theorem weighted_balance_stoichiometric_matrix
    {n m : ℕ} (weights state boundary : Fin n → ℚ)
    (stoich : Fin m → Fin n → ℚ) (rates : Fin m → ℚ) (dt : ℚ)
    (hcolumns : ∀ j, (∑ i, weights i * stoich j i) = 0) :
    (∑ i, weights i *
      (state i + dt * ((∑ j, stoich j i * rates j) + boundary i))) =
        (∑ i, weights i * state i) +
          dt * (∑ i, weights i * boundary i) := by
  have hreaction :
      (∑ i, weights i * (∑ j, stoich j i * rates j)) = 0 := by
    calc
      (∑ i, weights i * (∑ j, stoich j i * rates j)) =
          ∑ i, ∑ j, weights i * (stoich j i * rates j) := by
            apply Finset.sum_congr rfl
            intro i hi
            rw [Finset.mul_sum]
      _ = ∑ j, ∑ i, weights i * (stoich j i * rates j) := by
            rw [Finset.sum_comm]
      _ = ∑ j, (∑ i, weights i * stoich j i) * rates j := by
            apply Finset.sum_congr rfl
            intro j hj
            rw [Finset.sum_mul]
            apply Finset.sum_congr rfl
            intro i hi
            ring
      _ = 0 := by simp [hcolumns]
  exact weighted_balance_with_boundary weights state
    (fun i => ∑ j, stoich j i * rates j) boundary dt hreaction

end MathAI.Bio
