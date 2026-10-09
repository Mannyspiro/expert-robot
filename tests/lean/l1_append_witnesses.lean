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

/-- Exact upstream PiLp identity in the finite 2+3 coordinate case. -/
example (x x' : PiLp (1 : ENNReal) (fun _ : Fin 2 => ℝ))
    (y y' : PiLp (1 : ENNReal) (fun _ : Fin 3 => ℝ)) :
    ‖MathAI.Graph.l1AppendReal x y - MathAI.Graph.l1AppendReal x' y'‖ =
      ‖x - x'‖ + ‖y - y'‖ :=
  MathAI.Graph.l1AppendReal_norm_sub x x' y y'
