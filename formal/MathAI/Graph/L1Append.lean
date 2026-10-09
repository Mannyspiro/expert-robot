import Mathlib

/-!
A restricted finite-dimensional analogue of
OAI.BoundedTreewidthL1.l1Append_norm_sub
(openai/math@fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb,
lean/OAI/Combinatorics/TreewidthL1/Main.lean; Apache-2.0).

This statement is about exact rational coordinate-vector L1 distance.
It does NOT establish a graph embedding, shortest-path correctness,
FEM error control, or an application-side witness.
-/

namespace MathAI.Graph

/-- Sum of exact rational coordinatewise absolute differences. -/
def l1Distance {n : ℕ} (x y : Fin n → ℚ) : ℚ :=
  ∑ i, |x i - y i|

/-- Independent feature-channel distances add when the coordinates are appended. -/
theorem l1Distance_append {m n : ℕ}
    (x x' : Fin m → ℚ) (y y' : Fin n → ℚ) :
    l1Distance (Fin.append x y) (Fin.append x' y') =
      l1Distance x x' + l1Distance y y' := by
  unfold l1Distance
  rw [Fin.sum_univ_add]
  simp


/-- The upstream finite-real L1 direct sum, with exactly the upstream norm representation.
    Adapted from openai/math@fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb,
    OAI/Combinatorics/TreewidthL1/Main.lean (Apache-2.0). -/
def l1AppendReal {m n : ℕ} (x : PiLp (1 : ENNReal) (fun _ : Fin m => ℝ))
    (y : PiLp (1 : ENNReal) (fun _ : Fin n => ℝ)) :
    PiLp (1 : ENNReal) (fun _ : Fin (m + n) => ℝ) :=
  WithLp.toLp 1 (Fin.append x.ofLp y.ofLp)

/-- Standalone transfer of the upstream PiLp direct-sum norm identity. -/
theorem l1AppendReal_norm_sub {m n : ℕ}
    (x x' : PiLp (1 : ENNReal) (fun _ : Fin m => ℝ))
    (y y' : PiLp (1 : ENNReal) (fun _ : Fin n => ℝ)) :
    ‖l1AppendReal x y - l1AppendReal x' y'‖ =
      ‖x - x'‖ + ‖y - y'‖ := by
  simp only [PiLp.norm_eq_sum (by simp : 0 < (1 : ENNReal).toReal),
    ENNReal.toReal_one, Real.rpow_one,
    div_self (by norm_num : (1 : ℝ) ≠ 0)]
  rw [Fin.sum_univ_add]
  simp [l1AppendReal, PiLp.sub_apply]

end MathAI.Graph
