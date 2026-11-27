from hashlib import file_digest, sha256
import json, os, random, resource, subprocess, tempfile, time
from pathlib import Path
import argparse

root = Path(__file__).resolve().parent
cfg = json.loads((root/"protocol.json").read_text())
parser = argparse.ArgumentParser()
parser.add_argument("scene_directory", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
source = args.scene_directory.resolve()
result = args.output.resolve()
rng = random.Random(16031)
commands = []
for repeat in range(cfg["repeats"]):
    current = [(n, source/f) for n in cfg["candidates"] for f in cfg["scenes"]]
    rng.shuffle(current)
    commands.extend((repeat, n, scene) for n, scene in current)
with tempfile.TemporaryDirectory(prefix="merlin-render-bench-") as tmp, result.open("x") as sink:
    for repeat, threads, scene in commands:
        target = Path(tmp)/"frame-0065.png"
        target.unlink(missing_ok=True)
        cmd = ["blender","-b","--factory-startup","--disable-autoexec",
               str(scene),"-t",str(threads),"--python-exit-code","1","--python",str(root/"bench_setup.py"),
               "-o",str(Path(tmp)/"frame-####"),"-F","PNG","-f","65"]
        now = time.monotonic()
        with tempfile.TemporaryFile() as log:
            proc = subprocess.Popen(cmd, stdout=log, stderr=log)
            _, status, usage = os.wait4(proc.pid, 0)
            proc.returncode = os.waitstatus_to_exitcode(status)
            log.seek(0)
            tail = log.read()[-400:].decode(errors="replace")
        elapsed = time.monotonic()-now
        if proc.returncode or not target.is_file():
            sink.write(json.dumps(dict(repeat=repeat,threads=threads,scene=scene.name,error=tail))+"\n")
        else:
            pixels = subprocess.check_output(["ffmpeg","-v","error","-i",str(target),"-frames:v","1","-pix_fmt","rgb24","-f","rawvideo","-"])
            with scene.open("rb") as f: scene_hash=file_digest(f,"sha256").hexdigest()
            rss = usage.ru_maxrss/1024
            sink.write(json.dumps(dict(repeat=repeat,threads=threads,scene=scene.name,scene_hash=scene_hash,
                seconds=round(elapsed,4),rss_mib=round(rss,2),bytes=target.stat().st_size,pixel_sha256=sha256(pixels).hexdigest()))+"\n")
        sink.flush()
