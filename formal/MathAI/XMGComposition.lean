import Mathlib

/-!
# XMG composition and rewrite laws

These are foundational function-level laws for the Merlin Glyph Foundry.
They establish the mathematics of composition, identity, product projections,
and integer negation/absolute-value identities. They do not verify the Python
implementation or any external execution receipt.
-/

namespace MathAI.XMG

/-- Typed function composition: first apply f, then g. -/
def compose {A B C : Type} (g : B → C) (f : A → B) : A → C :=
  fun x => g (f x)

/-- The identity operator on a type. -/
def identity (A : Type) : A → A := fun x => x

/-- Left identity law for composition. -/
theorem compose_identity_left {A B : Type} (f : A → B) :
    compose f (identity A) = f := by
  funext x
  rfl

/-- Right identity law for composition. -/
theorem compose_identity_right {A B : Type} (f : A → B) :
    compose (identity B) f = f := by
  funext x
  rfl

/-- Associativity of typed function composition. -/
theorem compose_associative {A B C D : Type}
    (h : C → D) (g : B → C) (f : A → B) :
    compose h (compose g f) = compose (compose h g) f := by
  funext x
  rfl

/-- First projection after pairing recovers the first function. -/
theorem project_pair_left {A B C : Type}
    (f : A → B) (g : A → C) :
    (fun x => ((f x, g x).1)) = f := by
  funext x
  rfl

/-- Second projection after pairing recovers the second function. -/
theorem project_pair_right {A B C : Type}
    (f : A → B) (g : A → C) :
    (fun x => ((f x, g x).2)) = g := by
  funext x
  rfl

/-- Integer double negation is identity. -/
theorem int_double_negation (x : ℤ) : -(-x) = x := by
  simp

/-- Integer absolute magnitude is invariant under negation. -/
theorem int_natAbs_negation (x : ℤ) : Int.natAbs (-x) = Int.natAbs x := by
  simp

end MathAI.XMG
