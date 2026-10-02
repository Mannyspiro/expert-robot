import Mathlib

set_option maxHeartbeats 800000

namespace BenchFinal

theorem final_train_filler (n : ℕ) : n + 0 = n := by
  simp

theorem final_other_filler (n : ℕ) : n + 0 = n := by
  simp

theorem h01 (a : ℝ) (b : ℝ) :
    a^4 - b^4 = (a - b) * (a + b) * (a^2 + b^2) := by
  ring

theorem h02 (a : ℝ) (b : ℝ) (c : ℝ) (hab : a ≤ b) (hc : 0 ≤ c) :
    a * c ≤ b * c := by
  exact mul_le_mul_of_nonneg_right hab hc

theorem h03 (x : ℝ) (y : ℝ) (h1 : x + 2 * y = 7) (h2 : 2 * x - y = 4) :
    x = 3 ∧ y = 2 := by
  constructor <;> linarith

theorem h04 (m : ℕ) (n : ℕ) (hm : m % 2 = 1) (hn : n % 2 = 1) :
    (m + n) % 2 = 0 := by
  omega

theorem h05 (α : Type) (β : Type) (f : α → β) (P : α → Prop) (Q : α → Prop) (R : β → Prop) (hex : ∃ x, P x ∧ Q x) (hmap : ∀ x, Q x → R (f x)) :
    ∃ y, R y := by
  rcases hex with ⟨x, hxP, hxQ⟩
  exact ⟨f x, hmap x hxQ⟩

theorem h06 :
    (fun p : ℝ × ℝ => (p.1 - p.2)^2 + 1) = (fun p : ℝ × ℝ => (p.2 - p.1)^2 + 1) := by
  funext p
  ring

theorem h07 (f : Bool → ℝ) :
    (fun b : Bool => f (!(!b))) = f := by
  funext b
  cases b <;> rfl

theorem h08 (s : Finset ℕ) (f : ℕ → ℝ) (c : ℝ) :
    s.sum (fun i => f i + c) = s.sum f + s.card * c := by
  simp [Finset.sum_add_distrib, nsmul_eq_mul]

theorem h09 (a : ℝ) (b : ℝ) (x : ℝ) (y : ℝ) :
    (a * x - b * y)^2 + (b * x + a * y)^2 = (a^2 + b^2) * (x^2 + y^2) := by
  ring

theorem h10 (ax : ℝ) (ay : ℝ) (bx : ℝ) (byCoord : ℝ) :
    ax * byCoord - ay * bx = -(bx * ay - byCoord * ax) := by
  ring

end BenchFinal
