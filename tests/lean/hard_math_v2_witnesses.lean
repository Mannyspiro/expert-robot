import MathAI

/-!
Trusted witnesses for the hidden hard-v2 benchmark propositions.
This file lives under tests/ and is excluded from the candidate generation view.
-/

namespace MathAI.HardBenchmarkWitnesses

open MathAI.Geometry

theorem validation001 (a : Vec3) :
    parallel a a ∧ orthogonal zeroVec a := by
  exact ⟨parallel_self a, zero_orthogonal_left a⟩

theorem validation002 (a b : Vec3) :
    orthogonal a (cross a b) ∧ orthogonal b (cross a b) := by
  exact ⟨cross_orthogonal_left a b, cross_orthogonal_right a b⟩

theorem validation003 (a b : Point3) :
    squaredDistance a b = dot (vecBetween a b) (vecBetween a b) := by
  exact squaredDistance_eq_dot_vecBetween a b

theorem validation004
    (p : Point3) (sphere : Sphere3)
    (h : pointOnSphere p sphere) :
    validSphere sphere ∧ squaredDistance sphere.center p = sphere.radiusSquared := by
  exact ⟨h.1, h.2⟩

theorem holdout001
    (p : Point3) (line : Line3)
    (h : pointOnLine p line) :
    validLine line ∧ parallel (vecBetween line.point p) line.direction := by
  exact ⟨h.1, h.2⟩

theorem holdout002
    (p : Point3) (plane : Plane3)
    (h : pointOnPlane p plane) :
    validPlane plane ∧ dot plane.normal (pointVec p) = plane.offset := by
  exact ⟨h.1, h.2⟩

theorem holdout003
    (a b : Vec3) (h : parallel a b) :
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

theorem holdout004
    (a b : Vec3) (h : orthogonal a b) :
    orthogonal b a := by
  exact (orthogonal_symm a b).mp h

theorem holdout005 (a : Vec3) :
    parallel a a ∧ parallel zeroVec a ∧ parallel a zeroVec := by
  exact ⟨parallel_self a, parallel_zero_left a, parallel_zero_right a⟩

theorem holdout006 (a b : Vec3) :
    orthogonal a (cross a b) ∧
    orthogonal b (cross a b) ∧
    0 ≤ dot (cross a b) (cross a b) := by
  exact ⟨
    cross_orthogonal_left a b,
    cross_orthogonal_right a b,
    dot_self_nonnegative (cross a b)
  ⟩

theorem holdout007 (a b : Point3) :
    squaredDistance a b = squaredDistance b a ∧
    0 ≤ squaredDistance a b := by
  exact ⟨squaredDistance_symm a b, squaredDistance_nonnegative a b⟩

theorem holdout008
    (p : Point3) (sphere : Sphere3)
    (h : pointOnSphere p sphere) :
    validSphere sphere ∧
    squaredDistance sphere.center p = sphere.radiusSquared ∧
    0 ≤ sphere.radiusSquared := by
  exact ⟨h.1, h.2, h.1⟩

end MathAI.HardBenchmarkWitnesses
