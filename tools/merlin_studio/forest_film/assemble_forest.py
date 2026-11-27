"""Assemble Blender shot frames, keeping interpolation inside each cut."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile


NATIVE_FPS=8
SHOT_FRAMES=48
DELIVERY_FPS=24


def ff(*args):
    subprocess.run(["ffmpeg","-nostdin","-v","error",*map(str,args)],check=True)


def timecode(value):
    ms=round(value*1000)
    return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"


def assemble(frames,audio,dest,font):
    total=3*SHOT_FRAMES
    if not all((frames/f"frame-{i:04d}.png").is_file() for i in range(1,total+1)):
        raise ValueError("The 144 Blender source frames are required")
    cues=json.loads((audio/"Sound_Cues.json").read_text(encoding="utf-8"))
    caption="\n".join(f"{i}\n{timecode(cue['start'])} --> {timecode(cue['end'])}\n{cue['text']}\n"
                      for i,cue in enumerate(cues["cues"],1))
    if dest.exists():
        raise FileExistsError(dest)
    if font and any(c in str(font) for c in ":,;'[]\\"):
        raise ValueError("Use a font path without FFmpeg filter punctuation")
    with tempfile.TemporaryDirectory(dir=dest.parent,prefix=".woods-edit-") as temp:
        work=Path(temp)
        for cut in range(3):
            shot=work/f"shot-{cut}"
            shot.mkdir()
            for frame in range(1,SHOT_FRAMES+1):
                (shot/f"frame-{frame:04d}.png").symlink_to(frames/f"frame-{cut*SHOT_FRAMES+frame:04d}.png")
            effects="hqdn3d=7:5:8:7,tpad=stop_mode=clone:stop_duration=0.5," \
                    "minterpolate=fps=24:mi_mode=blend,scale=960:540:flags=lanczos,setsar=1"
            if cut==0 and font:
                effects+=(f",drawtext=fontfile={font}:text=A Lantern in the Violet Woods:"
                          "fontsize=37:fontcolor=#f2e7ca:x=46:y=h-90:shadowcolor=black@0.82:shadowx=2:shadowy=2:"
                          "enable='lt(t,2.8)'")
            ff("-filter_threads","3","-framerate",NATIVE_FPS,"-start_number","1","-i",
               shot/"frame-%04d.png","-frames:v",DELIVERY_FPS*(SHOT_FRAMES//NATIVE_FPS),
               "-vf",effects,"-an","-c:v","libx264","-crf","19","-pix_fmt","yuv420p","-threads","4",work/f"cut{cut}.mp4")
        concat=work/"shots.ffconcat"
        concat.write_text("ffconcat version 1.0\n"+"".join(f"file cut{i}.mp4\n" for i in range(3)))
        words=work/"words.srt"
        words.write_text(caption,encoding="utf-8")
        master=work/"film.mp4"
        ff("-f","concat","-safe","1","-i",concat,"-i",audio/"Forest_Mix_528.wav","-i",words,
           "-map","0:v","-map","1:a","-map","2:s","-c:v","copy","-c:a","aac","-b:a","192k",
           "-c:s","mov_text","-metadata:s:s:0","language=eng","-movflags","+faststart","-t","18",master)
        dest.hardlink_to(master)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("frames","audio","output"):
        parser.add_argument(name,type=Path)
    parser.add_argument("--font",type=Path)
    opts=parser.parse_args()
    assemble(opts.frames.resolve(),opts.audio.resolve(),opts.output.resolve(),
             opts.font.resolve(strict=True) if opts.font else None)


if __name__=="__main__":
    main()
