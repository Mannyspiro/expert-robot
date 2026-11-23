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

-- The exact equilibrium obstruction is universally quantified over the
-- (potentially unphysical) off-rate and arbitrary complex concentration.
example (kon koff kcat enzyme substrate complex : ℚ)
    (hkon : 0 < kon) (hkcat : 0 < kcat)
    (he : 0 < enzyme) (hs : 0 < substrate)
    (hcplx : kon * enzyme * substrate - koff * complex - kcat * complex = 0)
    (hprod : kcat * complex = 0) : False :=
  MathAI.Bio.no_positive_enzyme_substrate_steady_state
    kon koff kcat enzyme substrate complex hkon hkcat he hs hcplx hprod

-- Genuine zero-rate boundary cases are excluded by the theorem's
-- strictly positive catalytic rate hypothesis.
example : ¬ (0 : ℚ) < 0 := by norm_num

example (cat complex : ℚ) (hcat : 0 < cat) (hc : 0 < complex) :
    0 < cat * complex :=
  MathAI.Bio.product_flux_positive cat complex hcat hc
