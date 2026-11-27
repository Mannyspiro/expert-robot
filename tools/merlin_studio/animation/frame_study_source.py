"""Render benchmark RGB input before any MP4 color conversion or quantization."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from xenomotion import compile_plan
from xenomotion_preview import frame_images


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("plan","rig","art","sheet","output"):
        p.add_argument(name,type=Path)
    p.add_argument("--hold-camera",action="store_true")
    o=p.parse_args()
    plan=json.loads(o.plan.read_text(encoding="utf-8"))
    rig=json.loads(o.rig.read_text(encoding="utf-8"))
    plan["size"]=[640,360]
    if o.hold_camera:
        for shot in plan["shots"]:
            shot["keys"]=shot["keys"][:1]
    compiled=compile_plan(plan)
    whole=sha256()
    records=[]
    start=perf_counter()
    with o.output.open("xb") as target:
        for image in frame_images(plan,compiled,rig,o.art,o.sheet):
            pixels=image.tobytes()
            target.write(pixels)
            whole.update(pixels)
            records.append(sha256(pixels).hexdigest())
    print(json.dumps({"frames":len(records),"render_seconds":round(perf_counter()-start,4),
                      "geometry":compiled["size"],"fps":compiled["fps"],
                      "raw_sha256":whole.hexdigest(),"frame_sha256":records},indent=2))


if __name__=="__main__":
    main()
