import MathAI.Bio.LinearConservation

/-! Unqualified until pinned Mathlib build, LeanChecker, and axiom report pass. -/

#check MathAI.Bio.linear_conservation_update
#print axioms MathAI.Bio.linear_conservation_update

#check MathAI.Bio.linear_conservation_change
#print axioms MathAI.Bio.linear_conservation_change

example {m n : ℕ}
    (S : (Fin n → ℚ) →ₗ[ℚ] (Fin m → ℚ))
    (mass : (Fin m → ℚ) →ₗ[ℚ] ℚ)
    (h : ∀ v, mass (S v) = 0)
    (state : Fin m → ℚ) (flux : Fin n → ℚ) (dt : ℚ) :
    mass (state + dt • S flux) = mass state :=
  MathAI.Bio.linear_conservation_update S mass h state flux dt
