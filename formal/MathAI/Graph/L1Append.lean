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

end MathAI.Graph
