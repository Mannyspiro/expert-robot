import Mathlib

/-!
Abstract linear conservation principle for exact-rational reaction networks.

This is independent of kinetic rate laws and of the shape of the underlying
stoichiometric matrix. It states that any linear conserved quantity annihilating
the stoichiometric operator is unchanged by its explicit update.

No positivity, biochemical plausibility, PDE convergence, or model-level CACE
integration follows from this statement.
-/

namespace MathAI.Bio

/-- Every invariant linear functional that annihilates a stoichiometric
operator is conserved for an arbitrary rational flux vector and timestep. -/
theorem linear_conservation_update {m n : ℕ}
    (S : (Fin n → ℚ) →ₗ[ℚ] (Fin m → ℚ))
    (mass : (Fin m → ℚ) →ₗ[ℚ] ℚ)
    (hmass : ∀ v, mass (S v) = 0)
    (state : Fin m → ℚ) (v : Fin n → ℚ) (dt : ℚ) :
    mass (state + dt • S v) = mass state := by
  simp [map_add, map_smul, hmass]

/-- An arbitrary stoichiometric flux that violates the annihilation premise
does not inherit the conservation conclusion: at unit timestep, its change is
exactly the image of its flux. -/
theorem linear_conservation_change {m n : ℕ}
    (S : (Fin n → ℚ) →ₗ[ℚ] (Fin m → ℚ))
    (mass : (Fin m → ℚ) →ₗ[ℚ] ℚ)
    (state : Fin m → ℚ) (v : Fin n → ℚ) :
    mass (state + S v) - mass state = mass (S v) := by
  simp [map_add]

end MathAI.Bio
