"""Render a dialogue exposure sheet with an editable, art-specific 2D mouth rig."""

import argparse
import csv
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw

from exposure import SHAPES, time_value


POSES = {
    # width factor, opening height relative to the rig width, show teeth, show tongue
    "A": (.92,.025,False,False),
    "B": (.88,.08,True,False),
    "C": (.87,.24,True,False),
    "D": (.8,.43,True,True),
    "E": (.63,.32,False,True),
    "F": (.46,.23,False,False),
    "G": (.72,.11,True,False),
    "H": (.73,.32,True,True),
}


def patch(image, spec, shape):
    if shape == "X":
        return image
    width_scale, opening, teeth, tongue = POSES[shape]
    cx, cy = spec["anchor"]
    unit = spec["width"]
    size = unit*2
    overlay = Image.new("RGBA",(size,size))
    paint = ImageDraw.Draw(overlay)
    center = size // 2
    half = unit*width_scale/2
    height = max(1,unit*opening)
    lip = [(center-half,center),(center-.46*half,center-height*.57-2),
           (center+.50*half,center-height*.46-1),(center+half,center+1),
           (center+.47*half,center+height*.64+2),(center-.43*half,center+height*.67+2)]
    paint.polygon(lip, fill=spec["lip"])
    draw_box = (center-half*.88,center-height*.45,center+half*.87,center+height*.55)
    paint.ellipse(draw_box,fill=spec["ink"])
    if teeth:
        paint.ellipse((center-half*.45,center-height*.28,center+half*.52,center-height*.14+1),fill="#e4bda0")
    if tongue:
        paint.ellipse((center-half*.37,center+height*.13,center+half*.48,center+height*.39),fill=spec["tongue"])
    overlay = overlay.rotate(-spec["angle"],resample=Image.Resampling.BICUBIC)
    patched = image.copy()
    patched.paste(overlay,(cx-center,cy-center),overlay)
    return patched


def exposures(sheet, actors):
    latest = 0
    with sheet.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            start, end = int(row["first_frame"]), int(row["end_frame_exclusive"])
            actor, shape = row["speaker"], row["mouth"]
            if start != latest or not start < end or end > 24000 or shape not in SHAPES:
                raise ValueError("Expected contiguous frame ranges and valid shapes in a short preview")
            if (actor and actor not in actors) or (not actor and shape != "X"):
                raise ValueError("The mouth rig does not define this speaker")
            latest = end
            yield end - start, actor, shape
    if latest == 0:
        raise ValueError("Exposure sheet is empty")


def run(art, rig, audio, sheet, start, fps, output, group):
    if output.exists():
        raise FileExistsError(output)
    frame_rate = str(fps)
    images = {}
    count = 0
    image = Image.open(art).convert("RGB")
    if image.size != tuple(rig["art_size"]):
        raise ValueError("Art dimensions differ from the rig")
    frames = list(exposures(sheet, rig["mouths"]))
    image_raw = ["-f","rawvideo","-pix_fmt","rgb24","-s","1280x720","-r",frame_rate,"-i","-"]
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".pilot-edit-") as folder:
        target = Path(folder)/"preview.mp4"
        cmd = ["ffmpeg","-v","error",*image_raw,"-ss",f"{float(start):.8f}","-i",str(audio),"-map","0:v","-map","1:a",
               "-af","apad","-t",f"{float(Fraction(sum(n for n,_,_ in frames),1)/fps):.8f}",
               "-c:v","libx264","-preset","fast","-crf","19","-threads","4","-pix_fmt","yuv420p","-c:a","aac",
               "-movflags","+faststart",str(target)]
        with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
            try:
                for length, actor, shape in frames:
                    key = actor, shape
                    if key not in images:
                        plate = patch(image, rig["mouths"][actor], shape) if actor else image
                        camera = "group" if group or not actor else actor
                        rendered = plate.crop(tuple(rig["viewports"][camera])).resize((1280,720),Image.Resampling.LANCZOS)
                        images[key] = rendered.tobytes()
                    for _ in range(length):
                        proc.stdin.write(images[key])
                    count += length
            finally:
                proc.stdin.close()
            if proc.wait():
                raise RuntimeError("Could not encode the dialogue preview")
        output.hardlink_to(target)
    return {"frames": count, "composited_poses":len(images), "fps":frame_rate}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("art", type=Path)
    p.add_argument("rig", type=Path)
    p.add_argument("audio", type=Path)
    p.add_argument("sheet", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--audio-start", type=time_value, default=Fraction(0))
    p.add_argument("--fps", type=time_value, default=Fraction(24))
    p.add_argument("--group-shot", action="store_true")
    o = p.parse_args()
    if o.audio_start < 0 or not 1 <= o.fps <= 120:
        p.error("Invalid frame rate or audio offset")
    print(json.dumps(run(o.art,json.loads(o.rig.read_text()),o.audio,o.sheet,o.audio_start,o.fps,o.output,o.group_shot)))


if __name__ == "__main__":
    main()
