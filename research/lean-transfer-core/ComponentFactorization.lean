import TransferReachability

/-!
A complete factorization characterization for graph-component conserved
observables. For any weight codomain, edge-conserved weights are exactly
functions on connected components. This gives a mathematical "basis
completeness" foundation without asserting a module rank or basis theorem.

The quotient construction may use the kernel-accepted `Quot.sound` axiom;
all dependencies must be audited in CI. No Mathlib, chemistry or CACE runtime.
-/

namespace CoreTransfer

namespace Reach

/-- Compose finite undirected graph walks. -/
theorem append {n m : Nat}
    {edge : Fin m → Fin n × Fin n} {a b c : Fin n}
    (first : Reach edge a b) (second : Reach edge b c) :
    Reach edge a c := by
  induction second with
  | refl => exact first
  | forward e _ ih => exact Reach.forward e ih
  | backward e _ ih => exact Reach.backward e ih

/-- Every finite undirected graph walk has a reverse. -/
theorem reverse {n m : Nat}
    {edge : Fin m → Fin n × Fin n} {a b : Fin n}
    (walk : Reach edge a b) :
    Reach edge b a := by
  induction walk with
  | refl => exact Reach.refl
  | forward e _ ih =>
      exact append (Reach.backward e Reach.refl) ih
  | backward e _ ih =>
      exact append (Reach.forward e Reach.refl) ih

end Reach

/-- Undirected transfer reachability is an equivalence relation. -/
def componentSetoid {n m : Nat}
    (edge : Fin m → Fin n × Fin n) : Setoid (Fin n) where
  r := fun a b => Reach edge a b
  iseqv := ⟨
    (fun _ => Reach.refl),
    (fun {_ _} walk => Reach.reverse walk),
    (fun {_ _ _} first second => Reach.append first second)⟩

/-- The type of connected components of the finite transfer graph. -/
def Component {n m : Nat}
    (edge : Fin m → Fin n × Fin n) : Type :=
  Quotient (componentSetoid edge)

/-- The component containing a vertex. -/
def componentOf {n m : Nat}
    (edge : Fin m → Fin n × Fin n) (a : Fin n) : Component edge :=
  Quotient.mk (componentSetoid edge) a

/-- Every edgewise-conserved vertex observable is *exactly* an observable
on graph components; conversely every component observable is conserved
on edges. No arithmetic is required. -/
theorem edgewise_constant_iff_factors
    {n m : Nat} {α : Type}
    (edge : Fin m → Fin n × Fin n) (weight : Fin n → α) :
    (∀ e : Fin m, weight (edge e).1 = weight (edge e).2) ↔
    (∃ f : Component edge → α, ∀ a, weight a = f (componentOf edge a)) := by
  constructor
  · intro h
    have hp : ∀ a b : Fin n, Reach edge a b → weight a = weight b :=
      (walk_constant_iff_edgewise edge weight).2 h
    let f : Component edge → α :=
      Quotient.lift weight (fun a b walk => hp a b walk)
    exact ⟨f, fun _ => rfl⟩
  · intro h e
    obtain ⟨f, hf⟩ := h
    rw [hf (edge e).1, hf (edge e).2]
    exact congrArg f (Quotient.sound (Reach.forward e Reach.refl))

/-- Component factorization is unique, not merely possible. -/
theorem edgewise_constant_unique_factor
    {n m : Nat} {α : Type}
    (edge : Fin m → Fin n × Fin n) (weight : Fin n → α)
    (hedge : ∀ e : Fin m, weight (edge e).1 = weight (edge e).2) :
    ∃! f : Component edge → α, ∀ a, weight a = f (componentOf edge a) := by
  obtain ⟨f, hf⟩ := (edgewise_constant_iff_factors edge weight).1 hedge
  refine ⟨f, hf, ?_⟩
  intro g hg
  funext q
  refine Quotient.inductionOn q ?_
  intro a
  exact (hf a).symm.trans (hg a)

#check CoreTransfer.Reach.append
#check CoreTransfer.Reach.reverse
#check CoreTransfer.edgewise_constant_iff_factors
#print axioms CoreTransfer.edgewise_constant_iff_factors
#check CoreTransfer.edgewise_constant_unique_factor
#print axioms CoreTransfer.edgewise_constant_unique_factor

end CoreTransfer
