"""Edit the original pilot animatic from timed dialogue, art, and Blender inserts."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageOps


FPS = 24
SIZE = (1280, 720)
INK = "#110d19"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
NUMBERS = {
    "control": ("The control", "6 W input   /   20 °C sink", 1),
    "baseline": ("One thermal path", "6 W × 4 K/W + 20 °C = 44 °C", 1),
    "parallel": ("Two equal thermal paths", "3 W × 4 K/W + 20 °C = 32 °C", 2),
}


def ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", *map(str, args)], check=True)


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else SANS, size)


def frame(art, shot):
    name = shot["id"]
    character = art
    if name == "alarm":
        character = art.crop((0, 10, 990, 640))
    elif name in ("challenge", "limits"):
        character = art.crop((592, 92, 1536, 800))
    background = ImageOps.fit(character, SIZE, centering=(.5, .43)).convert("RGB")
    paint = ImageDraw.Draw(background)
    if name == "title":
        background = Image.blend(background, Image.new("RGB", SIZE, INK), .62)
        paint = ImageDraw.Draw(background)
        paint.text((76, 483), "AFTER THE GRID", font=font(55, True), fill="white")
        paint.text((74, 545), "WENT VIOLET", font=font(69, True), fill="#e5baff")
        paint.text((80, 634), "TWO WAYS OUT", font=font(22, True), fill="#ffc978")
    else:
        who = shot["speaker"].upper()
        paint.rounded_rectangle((52, 52, 212, 103), radius=10, fill=INK)
        paint.text((70, 64), who, font=font(24, True), fill="#eddbfa")
    return background


def render_technical(work, shot, index):
    title, detail, count = NUMBERS[shot["id"]]
    source = work / f"path-{count}-{(1, 33, 65, 96)[index]:04d}.png"
    image = ImageOps.fit(Image.open(source).convert("RGB"), SIZE)
    paint = ImageDraw.Draw(image)
    paint.rectangle((0, 0, 1280, 107), fill=INK)
    paint.text((56, 23), title, font=font(38, True), fill="#ffffff")
    paint.text((58, 73), "IDEAL STEADY-STATE MODEL", font=font(17, True), fill="#e2b2ff")
    paint.rectangle((0, 570, 1280, 638), fill=INK)
    paint.text((55, 581), detail, font=font(36, True), fill="#ffc978")
    return image


def timestamp(seconds):
    ms = round(seconds * 1000)
    return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"


def transitions(timing):
    points = [0, 3]
    points.extend((a["end"] + b["start"]) / 2 for a, b in zip(timing, timing[1:]))
    points.append(timing[-1]["end"] + 2.7)
    return [round(t * FPS) for t in points]


def edit(art, work, timing, output):
    with tempfile.TemporaryDirectory(dir=work) as temporary:
        stage = Path(temporary)
        shots = [{"id": "title"}, *timing]
        points = transitions(timing)
        parts = []
        for i, shot in enumerate(shots):
            length = points[i+1] - points[i]
            if shot["id"] in NUMBERS:
                frames = [render_technical(work, shot, k) for k in range(4)]
                for k, sample in enumerate(frames):
                    sample.save(stage / f"frame{k:02d}.png")
                # Blend between four independently rendered Blender camera frames.
                source = ["-framerate", str(3 * FPS / max(1, length - 1)), "-i", stage / "frame%02d.png",
                          "-vf", "minterpolate=fps=24:mi_mode=blend,tpad=stop_mode=clone:stop_duration=4"]
            else:
                picture = stage / "art.png"
                frame(art, shot).resize((2560, 1440), Image.Resampling.LANCZOS).save(picture)
                zoom = f"1.004+0.038*on/{length}"
                source = ["-i", picture, "-vf", f"zoompan=z={zoom}:x=iw/2-iw/zoom/2:y=ih/2-ih/zoom/2:d={length}:s=1280x720:fps={FPS}"]
            name = f"shot-{i:02d}.mp4"
            ff("-threads", "4", *source, "-frames:v", length, "-an", "-c:v", "libx264",
               "-crf", "20", "-preset", "fast", "-pix_fmt", "yuv420p", "-threads", "4", stage / name)
            parts.append(f"file {name}")
        listing = stage / "shots.ffconcat"
        listing.write_text("ffconcat version 1.0\n" + "\n".join(parts) + "\n")
        captions = output.with_suffix(".srt")
        cues = [
            f"{i}\n{timestamp(cue['start'])} --> {timestamp(cue['end'])}\n{cue['speaker'].title()}: {cue['text']}\n"
            for i, cue in enumerate(timing, 1)
        ]
        captions.write_text("\n".join(cues), encoding="utf-8")
        ff("-f", "concat", "-safe", "1", "-i", listing, "-i", work / "pilot.wav", "-i", captions,
           "-map", "0:v", "-map", "1:a", "-map", "2:s", "-c:v", "copy", "-af", "apad", "-c:a", "aac", "-b:a", "128k",
           "-c:s", "mov_text", "-metadata:s:s:0", "language=eng", "-movflags", "+faststart",
           "-t", points[-1] / FPS, output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("art", type=Path)
    p.add_argument("work", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    if args.output.exists():
        p.error("Choose a new output path")
    art = Image.open(args.art).convert("RGB")
    if art.size != (1536, 1024):
        p.error("The pilot's composition expects the original 1536 × 1024 cast art")
    timing = json.loads((args.work / "timing.json").read_text())
    edit(art, args.work.resolve(), timing, args.output.resolve())


if __name__ == "__main__":
    main()
