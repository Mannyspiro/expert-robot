import MathAI

/-! Trusted witnesses for the post-G3 algebraic progression benchmark. -/

namespace MathAI.HardBenchmarkV4Witnesses

open MathAI.Geometry

theorem validation001 (a b : Vec3) (h : parallel a b) :
    parallel b a := by
  unfold parallel at h ⊢
  apply Vec3.ext_coords
  · have hx := congrArg Vec3.x h
    simp [cross, zeroVec] at hx ⊢
    linarith
  · have hy := congrArg Vec3.y h
    simp [cross, zeroVec] at hy ⊢
    linarith
  · have hz := congrArg Vec3.z h
    simp [cross, zeroVec] at hz ⊢
    linarith

theorem validation002 (a b : Vec3) :
    (cross a b).x = -(cross b a).x ∧
    (cross a b).y = -(cross b a).y ∧
    (cross a b).z = -(cross b a).z := by
  constructor
  · simp [cross]
    ring
  constructor
  · simp [cross]
    ring
  · simp [cross]
    ring

theorem validation003 (a b : Vec3) :
    dot a b = dot b a ∧ (cross a b).x = -(cross b a).x := by
  constructor
  · exact dot_comm a b
  · simp [cross]
    ring

theorem validation004 (p q : Point3) :
    dot (vecBetween p q) (vecBetween p q) =
      dot (vecBetween q p) (vecBetween q p) ∧
    squaredDistance p q = squaredDistance q p := by
  constructor
  · unfold dot vecBetween
    ring
  · exact squaredDistance_symm p q

theorem holdout001 (a b : Vec3) :
    (cross a b).x + (cross b a).x = 0 ∧
    (cross a b).y + (cross b a).y = 0 := by
  constructor <;> simp [cross] <;> ring

theorem holdout002 (p q : Point3) :
    dot (vecBetween p q) (vecBetween p q) = squaredDistance q p ∧
    0 ≤ dot (vecBetween p q) (vecBetween p q) := by
  constructor
  · unfold dot vecBetween squaredDistance
    ring
  · exact dot_self_nonnegative (vecBetween p q)

theorem holdout003 (a b : Vec3) (h : cross a b = zeroVec) :
    cross b a = zeroVec := by
  apply Vec3.ext_coords
  · have hx := congrArg Vec3.x h
    simp [cross, zeroVec] at hx ⊢
    linarith
  · have hy := congrArg Vec3.y h
    simp [cross, zeroVec] at hy ⊢
    linarith
  · have hz := congrArg Vec3.z h
    simp [cross, zeroVec] at hz ⊢
    linarith

end MathAI.HardBenchmarkV4Witnesses
