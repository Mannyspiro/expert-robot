import Mathlib

/-!
# Trusted seed theorems

Imported from Mannyspiro/refactored-fishstick at commit
77224183e78a262a34b2c1c311b1d1fbc7c59b4e.

This file verifies the pinned Lean + Mathlib environment.
-/

namespace MathAI.Trust

theorem add_zero_verified (n : Nat) : n + 0 = n := by
  simp

theorem square_nonnegative (x : ℝ) : 0 ≤ x ^ 2 := by
  positivity

end MathAI.Trust
