import MathAI.Geometry.Exact

/-!
# A stated abstract 3D hardware model for Parallax experiments

These results concern exact natural/rational/real arithmetic. They do not prove
floating-point equivalence, physical timing, energy, routing manufacturability,
or an upstream Parallax chip specification. `pack3` is a proposed row-major
address convention; boxes are half-open, exact rational objects.
-/

namespace MathAI.Parallax

def pack3 (nx ny x y z : ℕ) : ℕ := x + nx * (y + ny * z)

theorem pack2_unique {base a b q r : ℕ}
    (ha : a < base) (hb : b < base)
    (h : a + base * q = b + base * r) : a = b ∧ q = r := by
  have hm := congrArg (fun n : ℕ => n % base) h
  have hab : a = b := by
    simpa [Nat.add_mod, Nat.mul_mod, Nat.mod_eq_of_lt ha, Nat.mod_eq_of_lt hb] using hm
  refine ⟨hab, ?_⟩
  have hp : 0 < base := lt_of_le_of_lt (Nat.zero_le a) ha
  have hmul : base * q = base * r := by omega
  exact Nat.eq_of_mul_eq_mul_left hp hmul

theorem pack3_unique {nx ny x y z x' y' z' : ℕ}
    (hx : x < nx) (hx' : x' < nx)
    (hy : y < ny) (hy' : y' < ny)
    (h : pack3 nx ny x y z = pack3 nx ny x' y' z') :
    x = x' ∧ y = y' ∧ z = z' := by
  obtain ⟨hxx, hrest⟩ := pack2_unique hx hx' h
  obtain ⟨hyy, hzz⟩ := pack2_unique hy hy' hrest
  exact ⟨hxx, hyy, hzz⟩

theorem pack3_lt_volume {nx ny nz x y z : ℕ}
    (hx : x < nx) (hy : y < ny) (hz : z < nz) :
    pack3 nx ny x y z < nx * ny * nz := by
  have hz' : z + 1 ≤ nz := by omega
  have hrow := Nat.mul_le_mul_left ny hz'
  have hyz : y + ny * z < ny * nz := by nlinarith
  have hyz' : y + ny * z + 1 ≤ ny * nz := by omega
  have hplane := Nat.mul_le_mul_left nx hyz'
  unfold pack3
  nlinarith

theorem legal_grid_dimensions_positive {nx ny nz x y z : ℕ}
    (hx : x < nx) (hy : y < ny) (hz : z < nz) :
    0 < nx ∧ 0 < ny ∧ 0 < nz := by omega

theorem distinct_legal_coordinates_have_distinct_addresses
    {nx ny x y z x' y' z' : ℕ}
    (hx : x < nx) (hx' : x' < nx)
    (hy : y < ny) (hy' : y' < ny)
    (hne : ¬ (x = x' ∧ y = y' ∧ z = z')) :
    pack3 nx ny x y z ≠ pack3 nx ny x' y' z' := by
  intro h
  exact hne (pack3_unique hx hx' hy hy' h)

structure Box3 where
  lo : MathAI.Geometry.Point3
  hi : MathAI.Geometry.Point3
deriving DecidableEq, Repr

def InBox (p : MathAI.Geometry.Point3) (b : Box3) : Prop :=
  b.lo.x ≤ p.x ∧ p.x < b.hi.x ∧
  b.lo.y ≤ p.y ∧ p.y < b.hi.y ∧
  b.lo.z ≤ p.z ∧ p.z < b.hi.z

def AxisSeparated (a b : Box3) : Prop :=
  a.hi.x ≤ b.lo.x ∨ b.hi.x ≤ a.lo.x ∨
  a.hi.y ≤ b.lo.y ∨ b.hi.y ≤ a.lo.y ∨
  a.hi.z ≤ b.lo.z ∨ b.hi.z ≤ a.lo.z

theorem axis_separated_no_shared_point (a b : Box3)
    (hsep : AxisSeparated a b) :
    ¬ ∃ p, InBox p a ∧ InBox p b := by
  rintro ⟨p, ha, hb⟩
  rcases ha with ⟨hax0, hax1, hay0, hay1, haz0, haz1⟩
  rcases hb with ⟨hbx0, hbx1, hby0, hby1, hbz0, hbz1⟩
  rcases hsep with h | h | h | h | h | h <;> linarith

theorem axis_separation_symmetric (a b : Box3) :
    AxisSeparated a b ↔ AxisSeparated b a := by
  unfold AxisSeparated
  tauto

def mass {n : ℕ} (w : Fin n → ℝ) : ℝ := ∑ i, w i

def weightedSum {n : ℕ} (w x : Fin n → ℝ) : ℝ := ∑ i, w i * x i

theorem positive_weights_positive_mass {n : ℕ} (hn : 0 < n)
    (w : Fin n → ℝ) (hw : ∀ i, 0 < w i) : 0 < mass w := by
  unfold mass
  apply Finset.sum_pos'
  · intro i _
    exact le_of_lt (hw i)
  · exact ⟨⟨0, hn⟩, Finset.mem_univ _, hw _⟩

theorem normalized_weights_sum_one {n : ℕ} (w : Fin n → ℝ)
    (hm : mass w ≠ 0) : (∑ i, w i / mass w) = 1 := by
  rw [← Finset.sum_div]
  exact div_self hm

theorem weighted_translation_identity {n : ℕ}
    (w x : Fin n → ℝ) (c : ℝ) :
    weightedSum w (fun i => x i - c) = weightedSum w x - c * mass w := by
  unfold weightedSum mass
  simp_rw [mul_sub]
  rw [Finset.sum_sub_distrib, ← Finset.sum_mul]
  ring

theorem centered_mean_same_exact_value {n : ℕ}
    (w x : Fin n → ℝ) (c : ℝ) (hm : mass w ≠ 0) :
    c + weightedSum w (fun i => x i - c) / mass w = weightedSum w x / mass w := by
  rw [weighted_translation_identity]
  field_simp [hm]; ring

theorem weighted_square_translation_identity {n : ℕ}
    (w x : Fin n → ℝ) (c : ℝ) :
    weightedSum w (fun i => (x i - c) ^ 2) =
      weightedSum w (fun i => x i ^ 2) - 2 * c * weightedSum w x + c ^ 2 * mass w := by
  unfold weightedSum mass
  calc
    (∑ i, w i * (x i - c) ^ 2) =
        ∑ i, (w i * x i ^ 2 - (2 * c) * (w i * x i) + c ^ 2 * w i) := by
      apply Finset.sum_congr rfl
      intro i _
      ring
    _ = _ := by
      rw [Finset.sum_add_distrib, Finset.sum_sub_distrib,
        ← Finset.mul_sum, ← Finset.mul_sum]

theorem centered_energy_same_exact_value {n : ℕ}
    (w x : Fin n → ℝ) (c : ℝ) (hm : mass w ≠ 0) :
    weightedSum w (fun i => (x i - c) ^ 2) -
        (weightedSum w (fun i => x i - c)) ^ 2 / mass w =
      weightedSum w (fun i => x i ^ 2) - (weightedSum w x) ^ 2 / mass w := by
  rw [weighted_square_translation_identity, weighted_translation_identity]
  field_simp [hm]; ring

theorem weighted_cross_translation_identity {n : ℕ}
    (w u v : Fin n → ℝ) (c d : ℝ) :
    weightedSum w (fun i => (u i - c) * (v i - d)) =
      weightedSum w (fun i => u i * v i) -
        d * weightedSum w u - c * weightedSum w v + c * d * mass w := by
  unfold weightedSum mass
  calc
    (∑ i, w i * ((u i - c) * (v i - d))) =
        ∑ i, (w i * (u i * v i) - d * (w i * u i) -
          c * (w i * v i) + (c * d) * w i) := by
      apply Finset.sum_congr rfl
      intro i _
      ring
    _ = _ := by
      rw [Finset.sum_add_distrib, Finset.sum_sub_distrib,
        Finset.sum_sub_distrib, ← Finset.mul_sum, ← Finset.mul_sum,
        ← Finset.mul_sum]

noncomputable def weightedCovariance {n : ℕ} (w u v : Fin n → ℝ) : ℝ :=
  weightedSum w (fun i => u i * v i) / mass w -
    weightedSum w u * weightedSum w v / (mass w) ^ 2

theorem covariance_centering_same_exact_value {n : ℕ}
    (w u v : Fin n → ℝ) (c d : ℝ) (hm : mass w ≠ 0) :
    weightedCovariance w (fun i => u i - c) (fun i => v i - d) =
      weightedCovariance w u v := by
  unfold weightedCovariance
  rw [weighted_cross_translation_identity,
    weighted_translation_identity, weighted_translation_identity]
  field_simp [hm]; ring

theorem parallax_covariance_identity (meanV meanA crossMoment : ℝ) :
    meanV * (1 + meanA) - crossMoment =
      meanV - (crossMoment - meanV * meanA) := by ring

theorem normalized_two_block_covariance_merge
    (p q meanUA meanUB meanVA meanVB covA covB : ℝ)
    (h : p + q = 1) :
    p * (covA + meanUA * meanVA) + q * (covB + meanUB * meanVB) -
        (p * meanUA + q * meanUB) * (p * meanVA + q * meanVB) =
      p * covA + q * covB + p * q * (meanUA - meanUB) * (meanVA - meanVB) := by
  have hq : q = 1 - p := by linarith
  rw [hq]
  ring

noncomputable def perplexity (meanNLL : ℝ) : ℝ := Real.exp meanNLL

theorem perplexity_positive (loss : ℝ) : 0 < perplexity loss := Real.exp_pos loss

theorem perplexity_preserves_nll_order {a b : ℝ} (h : a ≤ b) :
    perplexity a ≤ perplexity b := Real.exp_le_exp.mpr h

end MathAI.Parallax
