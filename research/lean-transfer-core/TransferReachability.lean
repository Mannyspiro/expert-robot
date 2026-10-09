import Init

/-!
A standalone, Mathlib-independent formulation of finite graph reachability.
This module contains only a graph-theoretic proof obligation, not an SBML
model, kinetics, conservation of an arbitrary chemical reaction, or a
qualified CACE sparse-matrix implementation.

The proof is deliberately polymorphic in the weight codomain. It needs no
arithmetic, choice, classical reasoning or external axioms.
-/

namespace CoreTransfer

universe u

/-- Reachability through the *undirected* edges of a directed transfer graph. -/
inductive Reach {n m : Nat}
    (edge : Fin m → Fin n × Fin n)
    (start : Fin n) : Fin n → Prop where
  | refl : Reach edge start start
  | forward (e : Fin m) :
      Reach edge start (edge e).1 →
      Reach edge start (edge e).2
  | backward (e : Fin m) :
      Reach edge start (edge e).2 →
      Reach edge start (edge e).1

/-- A function is constant along all undirected paths iff it has equal
values at the two endpoints of each edge. Works for *any* weight type. -/
theorem walk_constant_iff_edgewise
    {n m : Nat} {α : Type u}
    (edge : Fin m → Fin n × Fin n)
    (weight : Fin n → α) :
    (∀ a b : Fin n, Reach edge a b → weight a = weight b) ↔
    (∀ e : Fin m, weight (edge e).1 = weight (edge e).2) := by
  constructor
  · intro h e
    exact h _ _ (Reach.forward e Reach.refl)
  · intro hedges a b walk
    induction walk with
    | refl => rfl
    | forward e _ ih => exact ih.trans (hedges e)
    | backward e _ ih => exact ih.trans (hedges e).symm

/-- Specialization: constant integer-valued quantities on graph components. -/
example {n m : Nat}
    (edge : Fin m → Fin n × Fin n)
    (weights : Fin n → Int) :
    (∀ a b, Reach edge a b → weights a = weights b) ↔
      (∀ e, weights (edge e).1 = weights (edge e).2) :=
  walk_constant_iff_edgewise edge weights

#check CoreTransfer.Reach
#check CoreTransfer.walk_constant_iff_edgewise
#print axioms CoreTransfer.walk_constant_iff_edgewise

end CoreTransfer
