import Mathlib

/-!
Exact criterion for a linear observable to annihilate *all* directed
unit-transfer edge fluxes. For a one-to-one transfer e : src → dst the
observable changes by (weight dst - weight src) * flux e.

This is an edgewise characterization, not yet the stronger theorem that
the left nullspace has a basis of undirected component indicators.
It says nothing about nonlinear kinetics, chemistry validity or numerical
solver correctness.
-/

namespace MathAI.Bio

/-- Over exact rationals, a weighted sum of arbitrary transfer fluxes is
zero for *every* choice of flux if and only if each transfer preserves
the vertex weight. -/
theorem transfer_flux_pairing_zero_iff
    {species reactions : ℕ}
    (edge : Fin reactions → Fin species × Fin species)
    (weight : Fin species → ℚ) :
    (∀ rate : Fin reactions → ℚ,
      (∑ e : Fin reactions,
        (weight (edge e).2 - weight (edge e).1) * rate e) = 0) ↔
    (∀ e : Fin reactions,
      weight (edge e).1 = weight (edge e).2) := by
  constructor
  · intro h e
    have hz := h (fun j => if j = e then (1 : ℚ) else 0)
    have hdelta : weight (edge e).2 - weight (edge e).1 = 0 := by
      simpa [mul_ite] using hz
    exact (sub_eq_zero.mp hdelta).symm
  · intro heq rate
    apply Finset.sum_eq_zero
    intro e _
    rw [← heq e]
    ring

/-- The all-ones mass observable satisfies the edgewise conservation
condition for every finite directed unit-transfer graph. -/
theorem transfer_graph_total_mass_flux_zero
    {species reactions : ℕ}
    (edge : Fin reactions → Fin species × Fin species)
    (rate : Fin reactions → ℚ) :
    (∑ e : Fin reactions, ((1 : ℚ) - 1) * rate e) = 0 := by
  simp


/-- Finite undirected reachability through the edges of a directed unit-transfer
network. Direction of a biochemical transfer is deliberately ignored here,
because conserved component totals depend on the underlying incidence graph. -/
inductive TransferWalk {species reactions : ℕ}
    (edge : Fin reactions → Fin species × Fin species)
    (origin : Fin species) : Fin species → Prop where
  | refl : TransferWalk edge origin origin
  | forward (e : Fin reactions) :
      TransferWalk edge origin (edge e).1 →
      TransferWalk edge origin (edge e).2
  | backward (e : Fin reactions) :
      TransferWalk edge origin (edge e).2 →
      TransferWalk edge origin (edge e).1

/-- A vertex weight is constant on every finite undirected transfer walk
if and only if it has equal values at endpoints of every edge. -/
theorem transfer_weight_walk_iff_edgewise
    {species reactions : ℕ}
    (edge : Fin reactions → Fin species × Fin species)
    (weight : Fin species → ℚ) :
    (∀ a b : Fin species, TransferWalk edge a b → weight a = weight b) ↔
    (∀ e : Fin reactions, weight (edge e).1 = weight (edge e).2) := by
  constructor
  · intro h e
    exact h _ _ (TransferWalk.forward e TransferWalk.refl)
  · intro hedges a b hwalk
    induction hwalk with
    | refl => rfl
    | forward e _ ih => exact ih.trans (hedges e)
    | backward e _ ih => exact ih.trans (hedges e).symm

/-- Conservation under *every* rational transfer flux is equivalent to
constant vertex weights along every finite path in the transfer graph. -/
theorem transfer_flux_zero_iff_walk_constant
    {species reactions : ℕ}
    (edge : Fin reactions → Fin species × Fin species)
    (weight : Fin species → ℚ) :
    (∀ rate : Fin reactions → ℚ,
      (∑ e : Fin reactions,
        (weight (edge e).2 - weight (edge e).1) * rate e) = 0) ↔
    (∀ a b : Fin species, TransferWalk edge a b → weight a = weight b) := by
  exact (transfer_flux_pairing_zero_iff edge weight).trans
    (transfer_weight_walk_iff_edgewise edge weight).symm

end MathAI.Bio
