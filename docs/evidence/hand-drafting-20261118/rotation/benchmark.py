"""Compare rotated optical bench mockups with their enclosing boxes."""
import json
from pathlib import Path

import FreeCAD as cad
import Part


def main():
    project = Path(__file__).resolve().parent
    protocol = json.loads((project / "protocol.json").read_text())

    def solid(origin):
        shape = Part.makeBox(*protocol["solid_size"])
        shape.rotate(cad.Vector(0, 0, 0), cad.Vector(0, 0, 1), protocol["yaw_degrees"])
        shape.translate(cad.Vector(*origin))
        return shape

    fixed = solid(protocol["fixed_origin"])
    results = []
    for case in protocol["cases"]:
        moving = solid(case["offset"])
        volume = fixed.common(moving).Volume
        a, b = fixed.BoundBox, moving.BoundBox
        box_overlap = all(min(getattr(a, k+"Max"), getattr(b, k+"Max")) >
                          max(getattr(a, k+"Min"), getattr(b, k+"Min")) for k in "XYZ")
        exact_overlap = volume > protocol["volume_threshold_m3"]
        assert (box_overlap, exact_overlap) == (case["aabb_overlap"], case["solid_overlap"])
        results.append(dict(offset=case["offset"], enclosing_box_overlap=box_overlap,
                            solid_overlap=exact_overlap, intersection_m3=volume))
    print(json.dumps(dict(freecad=cad.Version()[:3], opencascade=Part.OCC_VERSION,
                          scope="Synthetic rotated boxes. CAD experiment only.", cases=results), indent=2))


if __name__ == "__main__":
    main()
