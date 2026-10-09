import MathAI

/-! Synthetic exact-rational witness replay for stoichiometric conservation. -/

-- For two units enzyme and one unit complex, any flux increments conserve three units.
example (forward reverse catalytic : ℚ) :
  (2 - forward + reverse + catalytic) +
    (1 + forward - reverse - catalytic) = 3 := by
  convert MathAI.Bio.total_enzyme_conserved 2 1 forward reverse catalytic using 1 <;> norm_num

-- For substrate, complex and product initial amounts 2, 1 and 0.
example (forward reverse catalytic : ℚ) :
  (2 - forward + reverse) +
    (1 + forward - reverse - catalytic) +
    (0 + catalytic) = 3 := by
  convert MathAI.Bio.substrate_moiety_conserved 2 1 0 forward reverse catalytic using 1 <;> norm_num

-- The optimization must remain exact for arbitrarily signed net fluxes.
example (x a b : ℚ) : x - a + b = x - (a - b) :=
  MathAI.Bio.reversible_flux_merged x a b
