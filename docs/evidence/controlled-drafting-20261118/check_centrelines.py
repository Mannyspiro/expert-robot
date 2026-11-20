"""Measure registered optical-sheet traces using a local teal-ink profile."""
import argparse
import json
from pathlib import Path
from statistics import median

import numpy as np
from PIL import Image


def measure(controls, path):
    with Image.open(path) as image:
        if list(image.size) != controls["canvas_px"]:
            raise ValueError("unregistered canvas dimensions")
        rgb = np.asarray(image.convert("RGB")).astype(int)
    r, g, b = rgb.transpose(2, 0, 1)
    ink = (g-r > 32) & (b-r > 28) & (g < 175)
    reports = {}
    for name, routes in controls["nets"].items():
        distances = []
        missing = 0
        for route in routes:
            vertices = route["vertices_px"]
            for start, end in zip(vertices, vertices[1:]):
                horizontal = start[1] == end[1]
                along, normal = (0, 1) if horizontal else (1, 0)
                for fraction in (0.2, 0.4, 0.6, 0.8):
                    t = round(start[along] + fraction*(end[along]-start[along]))
                    n = start[normal]
                    ns = [v for v in range(round(n)-5, round(n)+6)
                          if 0 <= v < (ink.shape[0] if horizontal else ink.shape[1]) and
                          (ink[v,t] if horizontal else ink[t,v])]
                    if ns:
                        distances.append(abs(median(ns)-n))
                    else:
                        missing += 1
        reports[name] = {"sampled":len(distances)+missing, "found":len(distances),
                         "max_normal_offset_px":round(max(distances),3) if distances else None}
    return reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controls", type=Path)
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    print(json.dumps(measure(json.loads(args.controls.read_text()), args.image), indent=2))
