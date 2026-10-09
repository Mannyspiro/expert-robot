import Mathlib

/-!
Exact abstract reaction-step identities for the harmless toy enzyme network
E + S <-> ES -> E + P.

These lemmas are algebraic identities over rational numbers. They do not prove
that any empirical kinetics, discretization, chemical energy, or CACE runtime
has been validated.
-/

namespace MathAI.Bio

/-- E + ES is conserved for arbitrary binding, unbinding and catalysis increments. -/
theorem total_enzyme_conserved
    (e es forward reverse catalytic : ℚ) :
    (e - forward + reverse + catalytic) +
      (es + forward - reverse - catalytic) = e + es := by
  ring

/-- S + ES + P is conserved for arbitrary increments of these three reactions. -/
theorem substrate_moiety_conserved
    (s es p forward reverse catalytic : ℚ) :
    (s - forward + reverse) +
      (es + forward - reverse - catalytic) +
      (p + catalytic) = s + es + p := by
  ring

/-- Opposing reaction columns can be merged into a signed net binding flux. -/
theorem reversible_flux_merged
    (x forward reverse : ℚ) :
    x - forward + reverse = x - (forward - reverse) := by
  ring

end MathAI.Bio
