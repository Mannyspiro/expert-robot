import MathAI.Geometry.Derived

/-!
# Derived vector and incidence lemmas

Small exact-rational identities that create reusable dependency chains for
proof search and theorem-graph routing.
-/

namespace MathAI.Geometry

theorem cross_zero_left (a : Vec3) :
    cross zeroVec a = zeroVec := by
  ext <;> simp [cross, zeroVec]

theorem cross_zero_right (a : Vec3) :
    cross a zeroVec = zeroVec := by
  ext <;> simp [cross, zeroVec]

theorem cross_self (a : Vec3) :
    cross a a = zeroVec := by
  ext <;> simp [cross, zeroVec] <;> ring

theorem vecBetween_self (p : Point3) :
    vecBetween p p = zeroVec := by
  ext <;> simp [vecBetween, zeroVec]

theorem parallel_zero_left (a : Vec3) :
    parallel zeroVec a := by
  unfold parallel
  exact cross_zero_left a

theorem parallel_zero_right (a : Vec3) :
    parallel a zeroVec := by
  unfold parallel
  exact cross_zero_right a

theorem parallel_self (a : Vec3) :
    parallel a a := by
  unfold parallel
  exact cross_self a

theorem dot_self_nonnegative (a : Vec3) :
    0 ≤ dot a a := by
  unfold dot
  positivity

theorem validPlane_of_pointOnPlane
    (p : Point3) (plane : Plane3)
    (h : pointOnPlane p plane) :
    validPlane plane := by
  exact h.1

theorem validLine_of_pointOnLine
    (p : Point3) (line : Line3)
    (h : pointOnLine p line) :
    validLine line := by
  exact h.1

end MathAI.Geometry
