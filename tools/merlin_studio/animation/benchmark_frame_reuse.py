"""Measure exact frame archives and verify every restored RGB frame."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from time import perf_counter

from frame_archive import decode, pack, raw_frames


CODECS = {
    "ffv1_intra": ["-c:v","ffv1","-level","3","-g","1","-pix_fmt","bgr0","-slices","4","-slicecrc","1"],
    "x264rgb_inter": ["-c:v","libx264rgb","-preset","fast","-qp","0","-g","24","-keyint_min","24","-sc_threshold","0",
                      "-pix_fmt","rgb24"],
}


def consume(frames, expected):
    for index,(pixels,digest) in enumerate(zip(frames,expected,strict=True)):
        if sha256(pixels).hexdigest() != digest:
            raise ValueError(f"Restored RGB mismatch at frame {index}")


def journal(path, result):
    with path.open("a",encoding="utf-8") as log:
        log.write(json.dumps(result)+"\n")


def benchmark(source, output):
    manifest=json.loads(source.with_name(source.stem+"-source.json").read_text(encoding="utf-8"))
    expected=manifest["frame_sha256"]
    size=tuple(manifest["geometry"])
    fps=manifest["fps"]
    cases={"png", "dedup", "delta"}
    report=output/"runs.jsonl"
    for mode in ("png","dedup","delta",*CODECS):
        target=output/(source.stem+"-"+mode+(".sqlite3" if mode in cases else ".mkv"))
        start=perf_counter()
        counts=None
        if mode in cases:
            counts=pack(source,target,size,mode,24)
        else:
            subprocess.run(["ffmpeg","-nostdin","-n","-v","error","-f","rawvideo","-pix_fmt","rgb24",
                            "-s",f"{size[0]}x{size[1]}","-r",fps,"-i",str(source),*CODECS[mode],
                            "-threads","4",str(target)],check=True)
        elapsed=perf_counter()-start
        start=perf_counter()
        if mode in cases:
            consume(decode(target),expected)
        else:
            command=["ffmpeg","-nostdin","-v","error","-xerror","-threads","4","-i",str(target),"-map","0:v:0",
                     "-pix_fmt","rgb24","-fps_mode","passthrough","-f","rawvideo","-threads","1","-"]
            with subprocess.Popen(command,stdout=subprocess.PIPE) as decoder:
                try:
                    consume(raw_frames(decoder.stdout,size),expected)
                except BaseException:
                    decoder.terminate()
                    raise
                if decoder.wait():
                    raise RuntimeError(f"Codec decode failed for {mode}")
        restore=perf_counter()-start
        entry={"regime":source.stem,"method":mode,"frames":len(expected),
               "archive_bytes":target.stat().st_size,"encode_wall_s":round(elapsed,3),
               "decode_and_hash_wall_s":round(restore,3),"all_frame_hashes_match":True}
        if counts:
            entry["record_counts"]=counts
            index=min(317,len(expected)-1)
            pixels,=decode(target,index)
            if sha256(pixels).hexdigest()!=expected[index]:
                raise ValueError("Random-access frame did not match")
            entry["single_frame_check"]=index
        journal(report,entry)
        print(json.dumps(entry),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("output",type=Path)
    p.add_argument("sources",type=Path,nargs="+")
    o=p.parse_args()
    o.output.mkdir(parents=True,exist_ok=False)
    for source in o.sources:
        benchmark(source,o.output)


if __name__=="__main__":
    main()
