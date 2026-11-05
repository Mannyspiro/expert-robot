#!/usr/bin/env python3
"""Generate a small deterministic FreeCAD assembly fixture for adapter qualification.

Call from inside the exact FreeCAD Python runtime. The output is a native FCStd
document (hierarchy fixture) and a STEP export (neutral geometry fixture).
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_fixture(output_dir: str | Path, *, app: Any, part: Any) -> dict:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    doc = app.newDocument("Merlin_Geometry_Fixture_v1")
    try:
        # Three non-overlapping solids: a base plate, an upper block and a post.
        base_shape = part.makeBox(20.0, 10.0, 2.0)
        block_shape = part.makeBox(5.0, 5.0, 8.0)
        block_shape.translate(app.Vector(5.0, 2.0, 2.0))
        post_shape = part.makeCylinder(2.0, 6.0)
        post_shape.translate(app.Vector(15.0, 5.0, 2.0))

        root = doc.addObject("App::DocumentObjectGroup", "MerlinAssembly")
        root.Label = "Merlin fixture assembly"
        sub = doc.addObject("App::DocumentObjectGroup", "UpperSubassembly")
        sub.Label = "Upper subassembly"

        base = doc.addObject("Part::Feature", "BasePlate")
        base.Label = "Base plate 20x10x2 mm"
        base.Shape = base_shape
        block = doc.addObject("Part::Feature", "UpperBlock")
        block.Label = "Upper block 5x5x8 mm"
        block.Shape = block_shape
        post = doc.addObject("Part::Feature", "RoundPost")
        post.Label = "Round post R2x6 mm"
        post.Shape = post_shape

        root.addObject(base)
        root.addObject(sub)
        sub.addObject(block)
        sub.addObject(post)
        doc.recompute()

        native_path = output / "merlin-fixture-v1.FCStd"
        step_path = output / "merlin-fixture-v1.step"
        doc.saveAs(str(native_path))
        part.export([base, block, post], str(step_path))

        manifest = {
            "fixture_version": "1.0",
            "units": {"length": "mm", "angle": "deg"},
            "coordinate_frame": {
                "frame_id": "fixture-world",
                "handedness": "right",
                "axis_convention": "X-right,Y-up,Z-out",
            },
            "component_names": ["BasePlate", "UpperBlock", "RoundPost"],
            "assembly_groups": {
                "MerlinAssembly": ["BasePlate", "UpperSubassembly"],
                "UpperSubassembly": ["UpperBlock", "RoundPost"],
            },
            "expected": {
                "component_count": 3,
                "bounding_box": {
                    "xmin": 0.0, "ymin": 0.0, "zmin": 0.0,
                    "xmax": 20.0, "ymax": 10.0, "zmax": 10.0,
                },
                "sum_of_shape_volumes_mm3": 600.0 + 24.0 * math.pi,
                "sum_of_shape_areas_mm2": 730.0 + 32.0 * math.pi,
                "all_shapes_valid": True,
                "mesh_parameters": {
                    "linear_deflection": 0.1,
                    "angular_deflection": 0.5,
                    "relative": False,
                },
            },
            "artifacts": {
                native_path.name: {"sha256": _sha256(native_path), "size_bytes": native_path.stat().st_size},
                step_path.name: {"sha256": _sha256(step_path), "size_bytes": step_path.stat().st_size},
            },
            "limitations": [
                "STEP export may not preserve native document group hierarchy; compare FCStd hierarchy separately",
                "expected metrics are analytic references for the three source solids, not an independent CAD-kernel certification",
                "FreeCAD execution and STEP round-trip remain to be performed in the authorized worker",
            ],
        }
        manifest_path = output / "fixture-manifest.json"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return manifest
    finally:
        app.closeDocument(doc.Name)


def main() -> int:
    import FreeCAD as App
    import Part
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = generate_fixture(args.output_dir, app=App, part=Part)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
