import Mathlib

/-!
# Exact audit of the four beta functions printed in the uploaded THTG report

The decimal coefficients in the report are represented as exact rationals.
This file proves an algebraic statement about those printed functions only.
It does not establish that they are the correct FRG flow of a physical theory:
the regulator, gauge fixing, ghost sector, projection and derivation of the
coefficients remain unspecified in the source report.
-/

namespace THTGPrintedBetaAudit

noncomputable section

def denominator (g : ℝ) : ℝ :=
  10970423 * g ^ 2 + 65060000 * g + 80000000

def omegaNumerator (g : ℝ) : ℝ :=
  3400 * g * (5041 * g + 10000)

def thetaNumerator (g : ℝ) : ℝ :=
  35500 * g * (493 * g + 800)

def omegaSolved (g : ℝ) : ℝ :=
  omegaNumerator g / denominator g

def thetaSolved (g : ℝ) : ℝ :=
  thetaNumerator g / denominator g

def betaG (g omega theta : ℝ) : ℝ :=
  3 * g + (127 / 100 : ℝ) * g ^ 2 *
    (1 - (41 / 100 : ℝ) * omega + (18 / 100 : ℝ) * theta)

def betaOmega (g omega theta : ℝ) : ℝ :=
  -2 * omega + (85 / 100 : ℝ) * g *
    (1 - (112 / 100 : ℝ) * omega + (47 / 100 : ℝ) * theta)

def betaTheta (g omega theta : ℝ) : ℝ :=
  -2 * theta + (71 / 100 : ℝ) * g *
    (1 + (33 / 100 : ℝ) * omega - (95 / 100 : ℝ) * theta)

def reducedNumerator (g : ℝ) : ℝ :=
  900879453 * g ^ 3 + 10432590900 * g ^ 2 +
    29678000000 * g + 24000000000

lemma denominator_pos (g : ℝ) (hg : 0 < g) :
    0 < denominator g := by
  unfold denominator
  positivity

/-- Elimination identity for omega, verified by exact polynomial normalization. -/
lemma omega_elimination_identity (g omega theta : ℝ) :
    omega * denominator g - omegaNumerator g =
      (-13490000 * g - 40000000) * betaOmega g omega theta +
        (-7990000 * g) * betaTheta g omega theta := by
  unfold denominator omegaNumerator betaOmega betaTheta
  ring

/-- Elimination identity for theta, verified by exact polynomial normalization. -/
lemma theta_elimination_identity (g omega theta : ℝ) :
    theta * denominator g - thetaNumerator g =
      (-4686000 * g) * betaOmega g omega theta +
        (-19040000 * g - 40000000) * betaTheta g omega theta := by
  unfold denominator thetaNumerator betaOmega betaTheta
  ring

/-- The two printed beta equations uniquely determine omega at fixed g. -/
theorem omega_forced_by_beta_equations
    (g omega theta : ℝ) (hg : 0 < g)
    (hω : betaOmega g omega theta = 0)
    (hθ : betaTheta g omega theta = 0) :
    omega = omegaSolved g := by
  have hid := omega_elimination_identity g omega theta
  rw [hω, hθ] at hid
  have hD : denominator g ≠ 0 := ne_of_gt (denominator_pos g hg)
  unfold omegaSolved
  field_simp [hD]
  linarith

/-- The two printed beta equations uniquely determine theta at fixed g. -/
theorem theta_forced_by_beta_equations
    (g omega theta : ℝ) (hg : 0 < g)
    (hω : betaOmega g omega theta = 0)
    (hθ : betaTheta g omega theta = 0) :
    theta = thetaSolved g := by
  have hid := theta_elimination_identity g omega theta
  rw [hω, hθ] at hid
  have hD : denominator g ≠ 0 := ne_of_gt (denominator_pos g hg)
  unfold thetaSolved
  field_simp [hD]
  linarith

/-- Substitution of the exact solution of betaOmega=betaTheta=0. -/
lemma betaG_after_elimination (g : ℝ) (hD : denominator g ≠ 0) :
    betaG g (omegaSolved g) (thetaSolved g) =
      g * reducedNumerator g / (100 * denominator g) := by
  unfold betaG omegaSolved thetaSolved omegaNumerator thetaNumerator
    reducedNumerator
  field_simp [hD]
  unfold denominator
  ring

/-- The reduced beta_g is strictly positive for every positive g. -/
theorem reduced_betaG_positive (g : ℝ) (hg : 0 < g) :
    0 < betaG g (omegaSolved g) (thetaSolved g) := by
  have hD : denominator g ≠ 0 := ne_of_gt (denominator_pos g hg)
  rw [betaG_after_elimination g hD]
  have hP : 0 < reducedNumerator g := by
    unfold reducedNumerator
    positivity
  have hDen : 0 < 100 * denominator g :=
    mul_pos (by norm_num) (denominator_pos g hg)
  exact div_pos (mul_pos hg hP) hDen

/--
The four beta functions as printed in the uploaded report have no simultaneous
fixed point with g > 0. This refutes the report's proposed positive-g point
for its printed coefficients; it does not refute a corrected, independently
derived FRG system.
-/
theorem no_positive_g_fixed_point
    (g omega theta : ℝ) (hg : 0 < g)
    (hω : betaOmega g omega theta = 0)
    (hθ : betaTheta g omega theta = 0)
    (hgβ : betaG g omega theta = 0) :
    False := by
  have hω' := omega_forced_by_beta_equations g omega theta hg hω hθ
  have hθ' := theta_forced_by_beta_equations g omega theta hg hω hθ
  rw [hω', hθ'] at hgβ
  exact (ne_of_gt (reduced_betaG_positive g hg)) hgβ

end
end THTGPrintedBetaAudit

#print axioms THTGPrintedBetaAudit.no_positive_g_fixed_point
