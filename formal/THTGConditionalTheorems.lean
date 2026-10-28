import Mathlib

/-!
THTG conditional theorem module.

This proves only a general compactness fact. It does not assert that the
currently documented THTG Page-curve expression is continuous or physically
correct. That expression is singular at its proposed Page time.
-/

namespace THTGConditionalTheorems

/--
A real-valued function continuous on a nonempty closed bounded interval
attains a maximum. This is a conditional mathematical lemma that can be used
only after a physical entropy function and its continuity assumptions have
been independently established.
-/
theorem continuous_attains_finite_maximum
    (a b : ℝ) (hab : a ≤ b) (S : ℝ → ℝ)
    (hS : ContinuousOn S (Set.Icc a b)) :
    ∃ t ∈ Set.Icc a b, ∀ u ∈ Set.Icc a b, S u ≤ S t := by
  have hcompact : IsCompact (Set.Icc a b) := isCompact_Icc
  have hne : (Set.Icc a b).Nonempty := ⟨a, ⟨le_rfl, hab⟩⟩
  exact hcompact.exists_isMaxOn hne hS

end THTGConditionalTheorems

#print axioms THTGConditionalTheorems.continuous_attains_finite_maximum
