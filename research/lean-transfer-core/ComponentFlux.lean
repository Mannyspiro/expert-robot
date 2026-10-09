import ComponentFactorization

/-!
A fully kernel-checkable arithmetic consequence of the transfer-graph
component theorem: any finite schedule of directed unit-transfer edge
fluxes annihilates a component-constant integer observable.

This verifies symbolic incidence/weight pairing over arbitrary finite
lists; it does not establish a numerical PDE scheme or CACE runtime.
-/

namespace CoreTransfer

/-- Exact integer weighted incidence-flux pairing for any finite list of
directed transfer edges. Repeated edges are permitted. -/
def weightedFlux {n m : Nat}
    (edge : Fin m → Fin n × Fin n)
    (weight : Fin n → Int) (rate : Fin m → Int)
    (schedule : List (Fin m)) : Int :=
  (schedule.map (fun e =>
    (weight (edge e).2 - weight (edge e).1) * rate e)).sum

/-- Edgewise constant weights annihilate every finite flux schedule. -/
theorem weightedFlux_eq_zero_of_edgewise
    {n m : Nat}
    (edge : Fin m → Fin n × Fin n)
    (weight : Fin n → Int) (rate : Fin m → Int)
    (schedule : List (Fin m))
    (h : ∀ e : Fin m, weight (edge e).1 = weight (edge e).2) :
    weightedFlux edge weight rate schedule = 0 := by
  have each_zero (e : Fin m) :
      (weight (edge e).2 - weight (edge e).1) * rate e = 0 := by
    rw [← h e]
    simp
  induction schedule with
  | nil => rfl
  | cons e rest ih =>
      calc
        weightedFlux edge weight rate (e :: rest) =
            (weight (edge e).2 - weight (edge e).1) * rate e +
              weightedFlux edge weight rate rest := rfl
        _ = weightedFlux edge weight rate rest := by
          rw [each_zero e]
          simp
        _ = 0 := ih

/-- Any integer observable factored through connected components
annihilates arbitrary finite signed reaction/transfer fluxes. -/
theorem component_observable_flux_zero
    {n m : Nat}
    (edge : Fin m → Fin n × Fin n)
    (componentWeight : Component edge → Int)
    (rate : Fin m → Int)
    (schedule : List (Fin m)) :
    weightedFlux edge
      (fun vertex => componentWeight (componentOf edge vertex))
      rate schedule = 0 := by
  apply weightedFlux_eq_zero_of_edgewise
  intro e
  apply congrArg componentWeight
  exact Quotient.sound (Reach.forward e Reach.refl)

/-- An integer observable annihilates every finite flux schedule if
it is constant on every graph component. -/
theorem walk_constant_flux_zero
    {n m : Nat}
    (edge : Fin m → Fin n × Fin n)
    (weight : Fin n → Int) (rate : Fin m → Int)
    (schedule : List (Fin m))
    (h : ∀ a b : Fin n, Reach edge a b → weight a = weight b) :
    weightedFlux edge weight rate schedule = 0 := by
  apply weightedFlux_eq_zero_of_edgewise
  exact (walk_constant_iff_edgewise edge weight).1 h

#check CoreTransfer.weightedFlux_eq_zero_of_edgewise
#print axioms CoreTransfer.weightedFlux_eq_zero_of_edgewise
#check CoreTransfer.component_observable_flux_zero
#print axioms CoreTransfer.component_observable_flux_zero
#check CoreTransfer.walk_constant_flux_zero
#print axioms CoreTransfer.walk_constant_flux_zero

end CoreTransfer
