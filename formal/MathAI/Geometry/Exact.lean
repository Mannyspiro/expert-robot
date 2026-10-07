import Mathlib

/-!
# Exact 3D geometry bridge

Imported from Mannyspiro/refactored-fishstick at commit
77224183e78a262a34b2c1c311b1d1fbc7c59b4e.

Exact rational geometry definitions. Predicates include explicit
nondegeneracy conditions so implementation and formal semantics can agree.
-/

namespace MathAI.Geometry

structure Vec3 where
  x : ℚ
  y : ℚ
  z : ℚ
deriving DecidableEq, Repr

structure Point3 where
  x : ℚ
  y : ℚ
  z : ℚ
deriving DecidableEq, Repr

structure Line3 where
  point : Point3
  direction : Vec3
deriving DecidableEq, Repr

structure Plane3 where
  normal : Vec3
  offset : ℚ
deriving DecidableEq, Repr

structure Sphere3 where
  center : Point3
  radiusSquared : ℚ
deriving DecidableEq, Repr

/-- A Euclidean circle embedded in 3D by center, plane normal, and squared radius. -/
structure Circle3 where
  center : Point3
  normal : Vec3
  radiusSquared : ℚ
deriving DecidableEq, Repr

@[ext] theorem Vec3.ext_coords
    (a b : Vec3)
    (hx : a.x = b.x)
    (hy : a.y = b.y)
    (hz : a.z = b.z) :
    a = b := by
  cases a
  cases b
  simp_all

@[ext] theorem Point3.ext_coords
    (a b : Point3)
    (hx : a.x = b.x)
    (hy : a.y = b.y)
    (hz : a.z = b.z) :
    a = b := by
  cases a
  cases b
  simp_all

def pointVec (p : Point3) : Vec3 :=
  ⟨p.x, p.y, p.z⟩

def vecBetween (a b : Point3) : Vec3 :=
  ⟨b.x - a.x, b.y - a.y, b.z - a.z⟩

def dot (a b : Vec3) : ℚ :=
  a.x * b.x + a.y * b.y + a.z * b.z

def cross (a b : Vec3) : Vec3 :=
  ⟨
    a.y * b.z - a.z * b.y,
    a.z * b.x - a.x * b.z,
    a.x * b.y - a.y * b.x
  ⟩

def zeroVec : Vec3 := ⟨0, 0, 0⟩

def validLine (line : Line3) : Prop :=
  line.direction ≠ zeroVec

def validPlane (plane : Plane3) : Prop :=
  plane.normal ≠ zeroVec

def validSphere (sphere : Sphere3) : Prop :=
  0 ≤ sphere.radiusSquared

def pointOnPlane (p : Point3) (plane : Plane3) : Prop :=
  validPlane plane ∧ dot plane.normal (pointVec p) = plane.offset

def pointOnLine (p : Point3) (line : Line3) : Prop :=
  validLine line ∧ cross (vecBetween line.point p) line.direction = zeroVec

def squaredDistance (a b : Point3) : ℚ :=
  (b.x - a.x) ^ 2 + (b.y - a.y) ^ 2 + (b.z - a.z) ^ 2

def pointOnSphere (p : Point3) (sphere : Sphere3) : Prop :=
  validSphere sphere ∧ squaredDistance sphere.center p = sphere.radiusSquared

def validCircle (circle : Circle3) : Prop :=
  circle.normal ≠ zeroVec ∧ 0 ≤ circle.radiusSquared

def circlePlaneOffset (circle : Circle3) : ℚ :=
  dot circle.normal (pointVec circle.center)

def pointOnCircle (p : Point3) (circle : Circle3) : Prop :=
  validCircle circle ∧
    dot circle.normal (pointVec p) = circlePlaneOffset circle ∧
    squaredDistance circle.center p = circle.radiusSquared

def orthogonal (a b : Vec3) : Prop :=
  dot a b = 0

def parallel (a b : Vec3) : Prop :=
  cross a b = zeroVec

theorem origin_on_xy_plane :
    pointOnPlane
      (⟨0, 0, 0⟩ : Point3)
      (⟨⟨0, 0, 1⟩, 0⟩ : Plane3) := by
  norm_num [pointOnPlane, validPlane, zeroVec, dot, pointVec]

theorem unit_x_on_unit_sphere :
    pointOnSphere
      (⟨1, 0, 0⟩ : Point3)
      (⟨⟨0, 0, 0⟩, 1⟩ : Sphere3) := by
  norm_num [pointOnSphere, validSphere, squaredDistance]

theorem unit_x_on_unit_xy_circle :
    pointOnCircle
      (⟨1, 0, 0⟩ : Point3)
      (⟨⟨0, 0, 0⟩, ⟨0, 0, 1⟩, 1⟩ : Circle3) := by
  norm_num [
    pointOnCircle, validCircle, circlePlaneOffset, zeroVec,
    dot, pointVec, squaredDistance
  ]

end MathAI.Geometry
