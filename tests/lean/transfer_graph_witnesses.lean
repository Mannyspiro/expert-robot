import MathAI.Bio.TransferGraph

/-! Transfer-graph independent witness entry point; candidates until checked. -/

#check MathAI.Bio.transfer_flux_pairing_zero_iff
#print axioms MathAI.Bio.transfer_flux_pairing_zero_iff

#check MathAI.Bio.transfer_graph_total_mass_flux_zero
#print axioms MathAI.Bio.transfer_graph_total_mass_flux_zero

example {n m : ℕ}
    (edges : Fin m → Fin n × Fin n) (weight : Fin n → ℚ) :
    (∀ rates : Fin m → ℚ,
       (∑ e : Fin m,
          (weight (edges e).2 - weight (edges e).1) * rates e) = 0) ↔
     ∀ e : Fin m, weight (edges e).1 = weight (edges e).2 :=
  MathAI.Bio.transfer_flux_pairing_zero_iff edges weight
