"""Build the pilot's two idealized thermal-path inserts in Blender."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from merlin_scene import build
import bpy


def box(name, at, size, material, bevel=0.035):
    return {"name": name, "shape": "cube", "at": at, "size": size, "material": material, "bevel": bevel}


def thermal_scene(paths):
    parts = [
        box("Relay board", [0, 0, 0], [7.5, 4.8, .28], "board", .1),
        box("Compute tile", [0, 0, .41], [1.7, 1.6, .5], "ceramic", .12),
        box("Amber indicator", [-.15, 0, .68], [.54, .22, .08], "copper"),
    ]
    for i, x in enumerate((-1, 1)):
        active = i < paths
        connector = "copper" if active else "inactive"
        parts += [
            box(f"Path {i+1}", [1.69*x, 0, .39], [1.9, .45, .32], connector),
            box(f"Sink {i+1}", [2.87*x, 0, .43], [1.15, 1.95, .52], "sink"),
        ]
        for j in range(-3, 4):
            parts.append(box(f"Sink fin {i+1}-{j}", [2.87*x, j*.245, .72], [1.01, .074, .16], "sink", .019))
        for y in (-1.58, 1.58):
            parts.append(box(f"Violet trace {x},{y}", [1.74*x, y, .19], [2.5, .083, .07], "violet"))
    materials = {
        "board": {"color": [.058,.027,.09], "metallic": .25, "roughness": .42},
        "ceramic": {"color": [.46,.28,.56], "metallic": .19, "roughness": .28},
        "sink": {"color": [.095,.34,.45], "metallic": .58, "roughness": .26},
        "copper": {"color": [.9,.24,.027], "metallic": .55, "roughness": .22},
        "violet": {"color": [.45,.105,.92], "metallic": .45, "roughness": .24},
        "inactive": {"color": [.064,.075,.09], "metallic": .2},
    }
    return {
        "name": f"{paths} equal thermal path" + ("s" if paths > 1 else ""),
        "resolution": [1280,720], "fps": 24, "frames": 96,
        "objects": parts, "materials": materials,
        "camera": {"at":[6,-9,10], "target":[0,0,.3], "orthographic":9.4,
                   "keys":[{"frame":1,"at":[6,-9,10],"target":[0,0,.3]},
                           {"frame":96,"at":[4,-9,11],"target":[0,0,.3]}]},
        "lights": [
            {"name":"Cool key","at":[-4,-5,8],"target":[0,0,0],"power":1600,"size":7,"color":[.76,.79,1]},
            {"name":"Amber rim","at":[2,4,6],"target":[0,0,0],"power":1650,"size":5,"color":[1,.59,.33]},
            {"name":"Violet fill","at":[7,-2,4],"target":[0,0,0],"power":800,"size":4,"color":[.68,.32,1]},
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for paths in (1, 2):
        spec = thermal_scene(paths)
        scene, _ = build(spec, out, "draft")
        scene.render.resolution_percentage = 75
        scene.cycles.samples = 32
        scene.cycles.use_denoising = False
        scene.render.threads_mode = "FIXED"
        scene.render.threads = 4
        for frame in (1, 33, 65, 96):
            scene.frame_set(frame)
            scene.render.filepath = str(out / f"path-{paths}-{frame:04d}.png")
            bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(out/f"thermal-paths-{paths}.blend"))
        (out / f"scene-{paths}.json").write_text(json.dumps(spec,indent=2)+"\n")


if __name__ == "__main__":
    main()
