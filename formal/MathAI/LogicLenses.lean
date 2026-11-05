import Mathlib

namespace MathAI.LogicLenses

/-- A finite n-valued truth domain. The parameter is the number of available states. -/
abbrev NTruth (n : Nat) := Fin n

/-- Gödel/min conjunction on a finite ordered truth domain. -/
def nAnd {n : Nat} (a b : NTruth n) : NTruth n := min a b

/-- Gödel/max disjunction on a finite ordered truth domain. -/
def nOr {n : Nat} (a b : NTruth n) : NTruth n := max a b

theorem nAnd_comm {n : Nat} (a b : NTruth n) : nAnd a b = nAnd b a := by
  exact min_comm a b

theorem nOr_comm {n : Nat} (a b : NTruth n) : nOr a b = nOr b a := by
  exact max_comm a b

theorem nAnd_idempotent {n : Nat} (a : NTruth n) : nAnd a a = a := by
  exact min_self a

theorem nOr_idempotent {n : Nat} (a : NTruth n) : nOr a a = a := by
  exact max_self a

/-- A fuzzy truth degree represented by a real number in the unit interval. -/
abbrev FuzzyDegree := {x : Real // 0 ≤ x ∧ x ≤ 1}

/-- Gödel t-norm: minimum of two graded truth values. -/
def fuzzyGodelAnd (a b : FuzzyDegree) : FuzzyDegree :=
  ⟨min a.1 b.1,
    ⟨le_min a.2.1 b.2.1,
      le_trans (min_le_left a.1 b.1) a.2.2⟩⟩

/-- Product t-norm: product of two graded truth values. -/
def fuzzyProductAnd (a b : FuzzyDegree) : FuzzyDegree :=
  ⟨a.1 * b.1,
    ⟨mul_nonneg a.2.1 b.2.1,
      by nlinarith [mul_nonneg a.2.1 (1 - b.1)]⟩⟩

/-- Łukasiewicz t-norm: max(0, a + b - 1). -/
def fuzzyLukasiewiczAnd (a b : FuzzyDegree) : FuzzyDegree :=
  ⟨max 0 (a.1 + b.1 - 1),
    ⟨le_max_left 0 (a.1 + b.1 - 1),
      max_le (by norm_num) (by linarith [a.2.2, b.2.2])⟩⟩

theorem fuzzyGodelAnd_comm (a b : FuzzyDegree) :
    fuzzyGodelAnd a b = fuzzyGodelAnd b a := by
  apply Subtype.ext
  exact min_comm a.1 b.1

theorem fuzzyProductAnd_comm (a b : FuzzyDegree) :
    fuzzyProductAnd a b = fuzzyProductAnd b a := by
  apply Subtype.ext
  exact mul_comm a.1 b.1

theorem fuzzyLukasiewiczAnd_comm (a b : FuzzyDegree) :
    fuzzyLukasiewiczAnd a b = fuzzyLukasiewiczAnd b a := by
  apply Subtype.ext
  simp [fuzzyLukasiewiczAnd, add_comm]

end MathAI.LogicLenses
