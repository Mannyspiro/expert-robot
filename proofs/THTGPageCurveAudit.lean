import Mathlib

/-!
# Exact monotonicity audit of the printed pre-Page THTG expression

The source report prints
  S(t) = (c/6) * log(sinh(a*t) / sinh(a*(T-t)))
for 0 < t < T, with c,a,T positive.

This module proves the displayed branch is strictly increasing on that open
interval and therefore has no maximum at any interior point. It does not
replace the expression with an island/generalized-entropy formula.
-/

namespace THTGPageCurveAudit

noncomputable section

def pageRatio (a T t : ℝ) : ℝ :=
  Real.sinh (a * t) / Real.sinh (a * (T - t))

def pageEntropy (c a T t : ℝ) : ℝ :=
  (c / 6) * Real.log (pageRatio a T t)

lemma pageRatio_pos (a T t : ℝ)
    (ha : 0 < a) (ht : 0 < t) (htT : t < T) :
    0 < pageRatio a T t := by
  unfold pageRatio
  apply div_pos
  · exact Real.sinh_pos (mul_pos ha ht)
  · exact Real.sinh_pos (mul_pos ha (by linarith))

/-- The printed sinh ratio is strictly increasing before the proposed Page time. -/
theorem pageRatio_strict_mono
    (a T t₁ t₂ : ℝ)
    (ha : 0 < a) (ht₁ : 0 < t₁) (ht₂ : t₁ < t₂) (ht₂T : t₂ < T) :
    pageRatio a T t₁ < pageRatio a T t₂ := by
  unfold pageRatio
  have hnumArg : a * t₁ < a * t₂ := mul_lt_mul_of_pos_left ht₂ ha
  have hdenArg : a * (T - t₂) < a * (T - t₁) := by
    apply mul_lt_mul_of_pos_left _ ha
    linarith
  have hnum : Real.sinh (a * t₁) < Real.sinh (a * t₂) :=
    Real.strictMono_sinh hnumArg
  have hden : Real.sinh (a * (T - t₂)) < Real.sinh (a * (T - t₁)) :=
    Real.strictMono_sinh hdenArg
  have hnumPos : 0 < Real.sinh (a * t₂) :=
    Real.sinh_pos (mul_pos ha (lt_trans ht₁ ht₂))
  have hdenPos : 0 < Real.sinh (a * (T - t₁)) :=
    Real.sinh_pos (mul_pos ha (by linarith))
  have hstep₁ :
      Real.sinh (a * t₁) / Real.sinh (a * (T - t₁)) <
      Real.sinh (a * t₂) / Real.sinh (a * (T - t₁)) :=
    div_lt_div_of_pos_right hnum hdenPos
  have hstep₂ :
      Real.sinh (a * t₂) / Real.sinh (a * (T - t₁)) <
      Real.sinh (a * t₂) / Real.sinh (a * (T - t₂)) :=
    div_lt_div_of_pos_left hden hnumPos
  exact lt_trans hstep₁ hstep₂

/-- The printed entropy branch is strictly increasing for positive c and a. -/
theorem pageEntropy_strict_mono
    (c a T t₁ t₂ : ℝ)
    (hc : 0 < c) (ha : 0 < a)
    (ht₁ : 0 < t₁) (ht₂ : t₁ < t₂) (ht₂T : t₂ < T) :
    pageEntropy c a T t₁ < pageEntropy c a T t₂ := by
  unfold pageEntropy
  have hratio := pageRatio_strict_mono a T t₁ t₂ ha ht₁ ht₂ ht₂T
  have hratioPos := pageRatio_pos a T t₁ ha ht₁ (lt_trans ht₂ ht₂T)
  have hlog := Real.log_lt_log hratioPos hratio
  have hc6 : 0 < c / 6 := by positivity
  exact mul_lt_mul_of_pos_left hlog hc6

/--
Every interior point has a later point with strictly larger entropy.
Thus the printed branch has no finite maximum anywhere in (0,T).
-/
theorem pageEntropy_has_no_maximum_on_open_interval
    (c a T t : ℝ)
    (hc : 0 < c) (ha : 0 < a)
    (ht : 0 < t) (htT : t < T) :
    ∃ u, 0 < u ∧ u < T ∧ pageEntropy c a T t < pageEntropy c a T u := by
  let u := (t + T) / 2
  have htu : t < u := by
    dsimp [u]
    linarith
  have huT : u < T := by
    dsimp [u]
    linarith
  have hu : 0 < u := lt_trans ht htu
  exact ⟨u, hu, huT,
    pageEntropy_strict_mono c a T t u hc ha ht htu huT⟩

end
end THTGPageCurveAudit

#print axioms THTGPageCurveAudit.pageEntropy_has_no_maximum_on_open_interval
