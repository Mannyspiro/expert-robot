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

#check MathAI.Bio.transfer_weight_walk_iff_edgewise
#print axioms MathAI.Bio.transfer_weight_walk_iff_edgewise

#check MathAI.Bio.transfer_flux_zero_iff_walk_constant
#print axioms MathAI.Bio.transfer_flux_zero_iff_walk_constant

example {n m : ℕ}
    (edges : Fin m → Fin n × Fin n)
    (weight : Fin n → ℚ) :
    (∀ rate : Fin m → ℚ,
        (∑ e : Fin m,
          (weight (edges e).2 - weight (edges e).1) * rate e) = 0) ↔
      ∀ a b : Fin n, MathAI.Bio.TransferWalk edges a b →
        weight a = weight b :=
  MathAI.Bio.transfer_flux_zero_iff_walk_constant edges weight
