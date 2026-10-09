import ComponentFactorization

/-!
Exact rational analogue of the verified integer transfer-flux theorem.

The rational scalar field is Lean core Rat, corresponding to the exact
fractions.Fraction oracle used in the CACE transport experiment. This
still addresses pure unit-transfer incidence, not arbitrary reactions
or certified PDE discretizations.
-/

namespace CoreTransfer

/-- The exact rational weighted incidence pairing for a finite flux list. -/
def rationalWeightedFlux {n m : Nat}
    (edge : Fin m → Fin n × Fin n)
    (weight : Fin n → Rat) (rate : Fin m → Rat)
    (schedule : List (Fin m)) : Rat :=
  (schedule.map (fun e =>
    (weight (edge e).2 - weight (edge e).1) * rate e)).sum

/-- Rational vertex weights constant across each edge annihilate every
finite rational flux schedule. No positivity or kinetics assumed. -/
theorem rationalFlux_zero_of_edgewise
    {n m : Nat}
    (edge : Fin m → Fin n × Fin n)
    (weight : Fin n → Rat) (rate : Fin m → Rat)
    (schedule : List (Fin m))
    (h : ∀ e : Fin m, weight (edge e).1 = weight (edge e).2) :
    rationalWeightedFlux edge weight rate schedule = 0 := by
  have each_zero (e : Fin m) :
      (weight (edge e).2 - weight (edge e).1) * rate e = 0 := by
    rw [← h e]
    rw [Rat.sub_self, Rat.zero_mul]
  induction schedule with
  | nil => rfl
  | cons e rest ih =>
      calc
        rationalWeightedFlux edge weight rate (e :: rest) =
            (weight (edge e).2 - weight (edge e).1) * rate e +
              rationalWeightedFlux edge weight rate rest := rfl
        _ = rationalWeightedFlux edge weight rate rest := by
          rw [each_zero e]
          rw [Rat.zero_add]
        _ = 0 := ih

/-- An observable annihilates *all* finite signed rational fluxes if and
only if it factors through the undirected connected components. -/
theorem rationalFlux_zero_for_all_iff_factors
    {n m : Nat}
    (edge : Fin m → Fin n × Fin n)
    (weight : Fin n → Rat) :
    (∀ rate : Fin m → Rat, ∀ schedule : List (Fin m),
       rationalWeightedFlux edge weight rate schedule = 0) ↔
    (∃ f : Component edge → Rat,
       ∀ a, weight a = f (componentOf edge a)) := by
  constructor
  · intro hz
    apply (edgewise_constant_iff_factors edge weight).1
    intro e
    have hs := hz (fun _ => (1 : Rat)) [e]
    have hsub : weight (edge e).2 - weight (edge e).1 = 0 := by
      simpa [rationalWeightedFlux, Rat.mul_one, Rat.add_zero] using hs
    have hsummed :=
      congrArg (fun x : Rat => x + weight (edge e).1) hsub
    have hdst : weight (edge e).2 = weight (edge e).1 := by
      simpa only [Rat.sub_add_cancel, Rat.zero_add] using hsummed
    exact hdst.symm
  · intro hf rate schedule
    apply rationalFlux_zero_of_edgewise
    exact (edgewise_constant_iff_factors edge weight).2 hf

#check CoreTransfer.rationalFlux_zero_of_edgewise
#print axioms CoreTransfer.rationalFlux_zero_of_edgewise
#check CoreTransfer.rationalFlux_zero_for_all_iff_factors
#print axioms CoreTransfer.rationalFlux_zero_for_all_iff_factors

end CoreTransfer
