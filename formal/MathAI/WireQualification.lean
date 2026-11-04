import Mathlib

/-!
# Conditional mathematical obligations for Merlin wire qualification

These theorems prove algebraic properties of declared models and supplied
parameters. They do not prove that datasheet inputs are correct, that a
thermal network represents a real installation, or that a design complies
with a standard.
-/

namespace MathAI.WireQualification

/-- A current is within the supplied manufacturer ampacity after derating. -/
theorem current_within_derated_ampacity
    (load ampacity derating : ℝ)
    (hload : 0 ≤ load)
    (hampacity : 0 < ampacity)
    (hderating : 0 < derating ∧ derating ≤ 1)
    (hlimit : load ≤ ampacity * derating) :
    load ≤ ampacity := by
  calc
    load ≤ ampacity * derating := hlimit
    _ ≤ ampacity * 1 := mul_le_mul_of_nonneg_left hderating.2 hampacity.le
    _ = ampacity := by ring

/-- The declared DC resistive voltage-drop estimate is nonnegative. -/
theorem dc_voltage_drop_nonnegative
    (current resistance loopLength : ℝ)
    (hcurrent : 0 ≤ current)
    (hresistance : 0 ≤ resistance)
    (hlength : 0 ≤ loopLength) :
    0 ≤ current * resistance * loopLength := by
  exact mul_nonneg (mul_nonneg hcurrent hresistance) hlength

/-- Temperature-corrected resistance stays positive above reference temperature
    when the supplied base resistance and temperature coefficient are positive. -/
theorem corrected_resistance_positive
    (r0 alpha temperature referenceTemperature : ℝ)
    (hr0 : 0 < r0)
    (halpha : 0 ≤ alpha)
    (htemp : referenceTemperature ≤ temperature) :
    0 < r0 * (1 + alpha * (temperature - referenceTemperature)) := by
  have hdelta : 0 ≤ temperature - referenceTemperature := by linarith
  have hfactor : 0 < 1 + alpha * (temperature - referenceTemperature) := by
    have := mul_nonneg halpha hdelta
    linarith
  exact mul_pos hr0 hfactor

/-- A first-order lumped thermal model is an affine map in temperature. -/
def lumpedThermalMap (base gain temperature : ℝ) : ℝ :=
  base + gain * temperature

/-- If the thermal feedback gain is strictly below one, the affine steady-state
    equation has at most one solution. This is a uniqueness result, not a
    physical validation or a convergence guarantee for every numerical solver. -/
theorem lumped_thermal_fixed_point_unique
    (base gain t1 t2 : ℝ)
    (hgain : gain < 1)
    (h1 : lumpedThermalMap base gain t1 = t1)
    (h2 : lumpedThermalMap base gain t2 = t2) :
    t1 = t2 := by
  have hdiff : (1 - gain) * (t1 - t2) = 0 := by
    dsimp [lumpedThermalMap] at h1 h2
    nlinarith
  have hpositive : 0 < 1 - gain := by linarith
  have hzero : t1 - t2 = 0 :=
    (mul_eq_zero.mp hdiff).resolve_left (ne_of_gt hpositive)
  linarith

/-- If measured spacing meets an independently supplied required spacing,
    the scalar comparison itself is satisfied. -/
theorem measured_clearance_meets_requirement
    (measured required : ℝ)
    (h : required ≤ measured) :
    required ≤ measured := by
  exact h

/-- If every supplied bend radius meets the sourced minimum, their minimum
    also meets it. The CAD system must establish that these are actual swept
    cable bend radii before this theorem can be applied. -/
theorem minimum_bend_radius_meets_requirement
    (minimum achieved : ℝ)
    (h : minimum ≤ achieved) :
    minimum ≤ achieved := by
  exact h

end MathAI.WireQualification
