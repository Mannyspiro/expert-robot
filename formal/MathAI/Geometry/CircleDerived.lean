import MathAI.Geometry.Exact

/-!
# Circle-derived exact geometry

Small exact symmetries motivated by circular experimental geometries.

These theorems concern geometry only. They do not imply that a complete
physical/ritual experiment is rotationally invariant: boundary data, materials,
symbols, sources, and measurements must separately satisfy the same symmetry.
-/

namespace MathAI.Geometry

def origin3 : Point3 :=
  ⟨0, 0, 0⟩

def quarterTurnZPoint (p : Point3) : Point3 :=
  ⟨-p.y, p.x, p.z⟩

def xyCircleAtOrigin (radiusSquared : ℚ) : Circle3 :=
  ⟨origin3, ⟨0, 0, 1⟩, radiusSquared⟩

theorem squaredDistance_origin_quarterTurnZ (p : Point3) :
    squaredDistance origin3 (quarterTurnZPoint p) =
      squaredDistance origin3 p := by
  unfold squaredDistance origin3 quarterTurnZPoint
  ring

theorem pointOn_xyCircleAtOrigin_quarterTurnZ
    (p : Point3) (radiusSquared : ℚ)
    (h : pointOnCircle p (xyCircleAtOrigin radiusSquared)) :
    pointOnCircle
      (quarterTurnZPoint p)
      (xyCircleAtOrigin radiusSquared) := by
  rcases h with ⟨hvalid, hplane, hradius⟩
  refine ⟨?_, ?_, ?_⟩
  · simpa [xyCircleAtOrigin] using hvalid
  · simpa [
      xyCircleAtOrigin,
      circlePlaneOffset,
      dot,
      pointVec,
      quarterTurnZPoint,
      origin3
    ] using hplane
  · change
      squaredDistance origin3 (quarterTurnZPoint p) =
        radiusSquared
    rw [squaredDistance_origin_quarterTurnZ]
    simpa [xyCircleAtOrigin] using hradius

end MathAI.Geometry
