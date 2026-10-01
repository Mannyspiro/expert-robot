import MathAI.Geometry.Exact

/-!
# Derived exact-geometry lemmas

Small reusable lemmas over the exact rational 3D geometry kernel. These are
kept deliberately elementary so they can serve as stable building blocks for
proof search, theorem-graph routing, and future generated lemmas.
-/

namespace MathAI.Geometry

theorem dot_comm (a b : Vec3) :
    dot a b = dot b a := by
  unfold dot
  ring

theorem dot_zero_left (a : Vec3) :
    dot zeroVec a = 0 := by
  simp [dot, zeroVec]

theorem dot_zero_right (a : Vec3) :
    dot a zeroVec = 0 := by
  simp [dot, zeroVec]

theorem orthogonal_symm (a b : Vec3) :
    orthogonal a b ↔ orthogonal b a := by
  unfold orthogonal
  rw [dot_comm]

theorem zero_orthogonal_left (a : Vec3) :
    orthogonal zeroVec a := by
  unfold orthogonal
  exact dot_zero_left a

theorem zero_orthogonal_right (a : Vec3) :
    orthogonal a zeroVec := by
  unfold orthogonal
  exact dot_zero_right a

theorem squaredDistance_self (p : Point3) :
    squaredDistance p p = 0 := by
  simp [squaredDistance]

theorem squaredDistance_symm (a b : Point3) :
    squaredDistance a b = squaredDistance b a := by
  unfold squaredDistance
  ring

theorem squaredDistance_nonnegative (a b : Point3) :
    0 ≤ squaredDistance a b := by
  unfold squaredDistance
  positivity

theorem validSphere_of_pointOnSphere
    (p : Point3) (sphere : Sphere3)
    (h : pointOnSphere p sphere) :
    validSphere sphere := by
  exact h.1

theorem squaredDistance_eq_radius_of_pointOnSphere
    (p : Point3) (sphere : Sphere3)
    (h : pointOnSphere p sphere) :
    squaredDistance sphere.center p = sphere.radiusSquared := by
  exact h.2

end MathAI.Geometry
