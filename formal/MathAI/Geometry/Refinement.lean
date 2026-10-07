import MathAI.Geometry.Exact

/-!
# Exact midpoint refinement geometry

These lemmas were motivated by CACE UniformRefinementND convergence data and
counterexample screening. They formalize only exact geometry. They do not by
themselves prove a complete mesh-refinement theorem for the CACE implementation.
-/

namespace MathAI.Geometry

/-- Exact midpoint of two rational 3D points. -/
def midpoint (a b : Point3) : Point3 :=
  ⟨
    (a.x + b.x) / 2,
    (a.y + b.y) / 2,
    (a.z + b.z) / 2
  ⟩

/-- The midpoint lies at one-quarter of the squared endpoint distance. -/
theorem squaredDistance_left_midpoint (a b : Point3) :
    squaredDistance a (midpoint a b) =
      squaredDistance a b / 4 := by
  unfold squaredDistance midpoint
  ring

/-- Midpoints on two edges sharing a vertex are separated by half the
corresponding opposite edge length, hence one-quarter the squared distance. -/
theorem squaredDistance_midpoint_midpoint_shared
    (a b c : Point3) :
    squaredDistance (midpoint a c) (midpoint b c) =
      squaredDistance a b / 4 := by
  unfold squaredDistance midpoint
  ring

/-- Reversing midpoint arguments does not change the point. -/
theorem midpoint_comm (a b : Point3) :
    midpoint a b = midpoint b a := by
  ext <;> simp [midpoint, add_comm]

end MathAI.Geometry
