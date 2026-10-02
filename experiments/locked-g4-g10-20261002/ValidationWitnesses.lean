import Mathlib

set_option maxHeartbeats 800000

namespace BenchValidation

theorem validation_train_filler (n : ℕ) : n + 0 = n := by
  simp

theorem validation_other_filler (n : ℕ) : n + 0 = n := by
  simp

theorem v01 (a : ℝ) (b : ℝ) :
    (a + b)^3 = a^3 + 3 * a^2 * b + 3 * a * b^2 + b^3 := by
  ring

theorem v02 (a : ℝ) (b : ℝ) (z : ℝ) (h : a + b = z) :
    (a + b)^2 = z^2 ∧ a * z + b * z = z^2 := by
  constructor
    · rw [h]
    · rw [← h]
      ring

theorem v03 (a : ℝ) (b : ℝ) :
    (a + b)^2 ≤ 2 * (a^2 + b^2) := by
  nlinarith [sq_nonneg (a - b)]

theorem v04 (u : ℝ) (v : ℝ) (t : ℝ) (h : u < v) (ht : 0 ≤ t) :
    u - t < v + t := by
  linarith

theorem v05 (a : ℝ) (b : ℝ) (ha : a ≠ 0) (hb : b ≠ 0) :
    (a + b) / (a * b) = 1 / a + 1 / b := by
  field_simp [ha, hb] <;> ring

theorem v06 (m : ℕ) (n : ℕ) (h : 3 * m + 2 = 3 * n + 2) :
    m = n := by
  omega

theorem v07 (P : Prop) (Q : Prop) (R : Prop) (hPQ : P → Q) (hQR : Q → R) :
    (P ∨ Q) → R := by
  intro h
    rcases h with hp | hq
    · exact hQR (hPQ hp)
    · exact hQR hq

theorem v08 :
    (fun x : ℝ => 3 * (x + 7) - 4) = (fun x : ℝ => 3 * x + 17) := by
  funext x
    ring

theorem v09 (a : ℝ) (b : ℝ) :
    ((a + b, a - b).1 + (a + b, a - b).2, (a + b, a - b).1 - (a + b, a - b).2) = (2 * a, 2 * b) := by
  apply Prod.ext
    · dsimp
      ring
    · dsimp
      ring

theorem v10 (a : ℝ) (b : ℝ) (c : ℝ) :
    (fun i : Fin 3 => ![a + b, b + c, c + a] i) = (fun i : Fin 3 => ![b + a, c + b, a + c] i) := by
  funext i
    fin_cases i <;> simp [add_comm]

theorem v11 (px : ℝ) (py : ℝ) (qx : ℝ) (qy : ℝ) (dx : ℝ) (dy : ℝ) :
    ((px + dx) - (qx + dx))^2 + ((py + dy) - (qy + dy))^2 = (px - qx)^2 + (py - qy)^2 := by
  ring

theorem v12 (x : ℝ) (y : ℝ) (u : ℝ) (v : ℝ) :
    (x + u)^2 + (y + v)^2 + (x - u)^2 + (y - v)^2 = 2 * (x^2 + y^2 + u^2 + v^2) := by
  ring

end BenchValidation
