import MathAI

-- Tight quadratic case: curvature 2, residual 2, displacement 1, defect 1.
example : (1 : ℝ) ≤ (2 : ℝ) ^ 2 / (2 * 2) :=
  MathAI.Molecular.energy_defect_bound 2 2 1 1 (by norm_num) (by norm_num)

example : (1 : ℝ) ≤ (3 / 2 : ℝ) :=
  MathAI.Molecular.energy_endpoint_bound 2 2 1 1 (3 / 2)
    (by norm_num) (by norm_num) (by norm_num)

-- Zero residual has no positive defect under the stated model.
example (d defect : ℝ) (h : defect ≤ -(d ^ 2)) : defect ≤ 0 := by
  have bound := MathAI.Molecular.energy_defect_bound 2 0 d defect
    (by norm_num) (by simpa using h)
  simpa using bound

-- Zero and negative curvature cannot supply the theorem's strict hypothesis.
example : ¬ (0 : ℝ) < 0 := by norm_num
example : ¬ (0 : ℝ) < -2 := by norm_num
