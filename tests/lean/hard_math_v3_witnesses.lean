import MathAI

/-!
Trusted witnesses for the hidden post-G3 progression benchmark.
This file is verifier-only and excluded from candidate generation views.
-/

namespace MathAI.HardBenchmarkV3Witnesses

open MathAI.Geometry

theorem validation001 (a : Vec3) (p q : Point3) :
    parallel a a ∧
    squaredDistance p q = dot (vecBetween p q) (vecBetween p q) := by
  exact ⟨parallel_self a, squaredDistance_eq_dot_vecBetween p q⟩

theorem validation002 (a : Vec3) :
    parallel a a ∧
      (orthogonal zeroVec a ∧
        (0 ≤ dot a a ∧ dot a zeroVec = 0)) := by
  exact ⟨
    parallel_self a,
    zero_orthogonal_left a,
    dot_self_nonnegative a,
    dot_zero_right a
  ⟩

theorem validation003 (a b : Vec3) :
    parallel a b ↔ cross a b = zeroVec := by
  rfl

theorem validation004 (a : Vec3) (p q : Point3) :
    squaredDistance p q = dot (vecBetween p q) (vecBetween p q) ∨
    parallel a a := by
  exact Or.inl (squaredDistance_eq_dot_vecBetween p q)

theorem holdout001 (a b : Vec3) (h : parallel a b) :
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

theorem holdout002 (p : Point3) (sphere : Sphere3) :
    pointOnSphere p sphere →
      (validSphere sphere ∧
       squaredDistance sphere.center p = sphere.radiusSquared) := by
  intro h
  exact ⟨h.1, h.2⟩

theorem holdout003 (a : Vec3) :
    cross a zeroVec = cross zeroVec a := by
  rw [cross_zero_right a, cross_zero_left a]

end MathAI.HardBenchmarkV3Witnesses
