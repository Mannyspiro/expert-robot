from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import json, random, subprocess, tempfile, time

root=Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("scene_directory", type=Path)
parser.add_argument("isolated_results", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
scenes=args.scene_directory.resolve()
files=sorted(scenes.glob("thermal-paths-*.blend"))
reference={r["scene"]:r["pixel_sha256"] for r in map(json.loads,args.isolated_results.read_text().splitlines()) if r["threads"]==1}
jobs=[(workers,threads,trial) for workers,threads in ((1,8),(2,4),(4,2),(8,1)) for trial in range(3)]
random.Random(9184).shuffle(jobs)
with tempfile.TemporaryDirectory(prefix="merlin-render-batches-") as tmp, args.output.open("x") as log:
    tmp=Path(tmp)
    for workers,threads,trial in jobs:
        def render(index):
            src=files[index%len(files)]
            pattern=tmp/f"render-{index}-####"
            res=subprocess.run(["blender","-b","--factory-startup","--disable-autoexec",str(src),
                "-t",str(threads),"--python",str(root/"bench_setup.py"),"-o",str(pattern),"-F","PNG","-f","65"],
                capture_output=True,timeout=90)
            path=tmp/f"render-{index}-0065.png"
            return src.name,path if res.returncode==0 and path.is_file() else None
        start=time.monotonic()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            paths=list(pool.map(render,range(8)))
        elapsed=time.monotonic()-start
        from hashlib import sha256
        def validated(name,path):
            if path is None:return False
            raw=subprocess.check_output(["ffmpeg","-v","error","-i",str(path),"-frames:v","1","-pix_fmt","rgb24","-f","rawvideo","-"])
            path.unlink()
            return sha256(raw).hexdigest()==reference[name]
        passing=sum(validated(*x) for x in paths)
        log.write(json.dumps(dict(workers=workers,threads=threads,trial=trial,frames=8,valid=passing,
                    seconds=round(elapsed,4),frames_per_minute=round(60*passing/elapsed,4)))+"\n")
        log.flush()
