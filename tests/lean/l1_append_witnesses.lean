import MathAI

/-- A nonempty pair of independent channels is a direct consequence of the audited theorem. -/
example (x x' : Fin 2 → ℚ) (y y' : Fin 3 → ℚ) :
    MathAI.Graph.l1Distance (Fin.append x y) (Fin.append x' y') =
      MathAI.Graph.l1Distance x x' + MathAI.Graph.l1Distance y y' :=
  MathAI.Graph.l1Distance_append x x' y y'

/-- The empty left-channel case remains within the theorem's quantifiers. -/
example (x x' : Fin 0 → ℚ) (y y' : Fin 1 → ℚ) :
    MathAI.Graph.l1Distance (Fin.append x y) (Fin.append x' y') =
      MathAI.Graph.l1Distance x x' + MathAI.Graph.l1Distance y y' :=
  MathAI.Graph.l1Distance_append x x' y y'
