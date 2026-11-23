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


/-- In a closed irreversible-binding/catalysis toy network, steady-state
    complex balance and product balance cannot both hold when free enzyme,
    substrate, binding rate and catalytic rate are strictly positive.
    The unbinding rate and complex concentration need not be positive. -/
theorem no_positive_enzyme_substrate_steady_state
    (onRate offRate catRate e s es : ℚ)
    (hon : 0 < onRate) (hcat : 0 < catRate)
    (he : 0 < e) (hs : 0 < s)
    (hcomplex : onRate * e * s - offRate * es - catRate * es = 0)
    (hproduct : catRate * es = 0) : False := by
  have hes : es = 0 :=
    (mul_eq_zero.mp hproduct).resolve_left (ne_of_gt hcat)
  subst es
  have hzero : onRate * e * s = 0 := by simpa using hcomplex
  exact (ne_of_gt (mul_pos (mul_pos hon he) hs)) hzero

/-- Saturation or a closed-network steady-state cannot be assumed simply from
    positive reaction rates: at positive complex abundance product flux grows. -/
theorem product_flux_positive
    (catRate es : ℚ) (hcat : 0 < catRate) (hes : 0 < es) :
    0 < catRate * es := mul_pos hcat hes

end MathAI.Bio
