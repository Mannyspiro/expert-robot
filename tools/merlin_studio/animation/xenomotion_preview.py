"""Render a Xenomaths camera and blink plan using the existing mouth rig."""

import argparse
from fractions import Fraction
import json
from itertools import chain, repeat
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw

from exposure import time_value
from preview import exposures, patch
from xenomotion import compile_plan


def closed_layer(art, eyes):
    plate=Image.new("RGBA",art.size)
    brush=ImageDraw.Draw(plate)
    for feature in eyes:
        outline=[tuple(point) for point in feature["outline"]]
        points=[tuple(point) for point in feature["line"]]
        skin=art.getpixel(tuple(feature["sample"]))
        brush.polygon(outline,fill=(*skin,255))
        brush.line(points,fill=(43,23,26,255),width=3,joint="curve")
    return plate


def render(plan, rig, art, audio, sheet, output):
    result=compile_plan(plan)
    image=Image.open(art).convert("RGB")
    if image.size!=tuple(result["art_size"]) or image.size!=tuple(rig["art_size"]):
        raise ValueError("Plan, mouth rig and artwork dimensions disagree")
    labels=exposures(sheet,rig["mouths"])
    speech=list(chain.from_iterable(repeat((actor,shape),length) for length,actor,shape in labels))
    if len(speech)!=len(result["frames"]):
        raise ValueError("Camera coverage and dialogue exposure must share the same frame count")
    blink_layers={actor:closed_layer(image,features) for actor,features in plan["eyes"].items()}
    w,h=result["size"]
    fps=time_value(result["fps"])
    start=time_value(result["audio_start"])
    duration=Fraction(len(speech),1)/fps
    drawing_cache={}
    if output.exists():
        raise FileExistsError(output)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix=".xenomotion-") as stage:
        target=Path(stage)/"preview.mp4"
        command=["ffmpeg","-v","error","-f","rawvideo","-pix_fmt","rgb24","-s",f"{w}x{h}","-r",str(fps),
                 "-i","-","-ss",f"{float(start):.8f}","-i",str(audio),"-map","0:v","-map","1:a",
                 "-af","apad","-t",f"{float(duration):.8f}","-c:v","libx264","-preset","fast","-crf","19",
                 "-threads","4","-pix_fmt","yuv420p","-c:a","aac","-movflags","+faststart",str(target)]
        with subprocess.Popen(command,stdin=subprocess.PIPE) as proc:
            try:
                for motion,(actor,shape) in zip(result["frames"],speech,strict=True):
                    key=actor,shape
                    if key not in drawing_cache:
                        drawing_cache[key]=patch(image,rig["mouths"][actor],shape) if actor else image
                    drawing=drawing_cache[key]
                    if motion["blink"]:
                        drawing=drawing.copy()
                        for name,amount in motion["blink"].items():
                            layer=blink_layers[name]
                            alpha=layer.getchannel("A").point([round(i*amount) for i in range(256)])
                            drawing.paste(layer,(0,0),alpha)
                    canvas=drawing.transform((w,h),Image.Transform.EXTENT,motion["crop"],
                                             resample=Image.Resampling.BICUBIC)
                    proc.stdin.write(canvas.tobytes())
            finally:
                proc.stdin.close()
            if proc.wait():
                raise RuntimeError("Could not encode Xenomaths motion preview")
        output.hardlink_to(target)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("plan","rig","art","audio","sheet","output"):
        p.add_argument(name,type=Path)
    opts=p.parse_args()
    plan=json.loads(opts.plan.read_text(encoding="utf-8"))
    rig=json.loads(opts.rig.read_text(encoding="utf-8"))
    render(plan,rig,opts.art,opts.audio,opts.sheet,opts.output)


if __name__=="__main__":
    main()
