"""Render resumable Blender PNG frames with dependency and output checks."""

from concurrent.futures import ThreadPoolExecutor
import argparse
import fcntl
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def digest(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def publish(path, data):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as staged:
        json.dump(data, staged, indent=2)
        staged.write("\n")
    Path(staged.name).replace(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scene", type=Path, help="Trusted .blend; pack external assets or list them with --asset")
    p.add_argument("output", type=Path)
    p.add_argument("--frames", type=int, nargs="+", required=True)
    p.add_argument("--threads", type=int, required=True)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--asset", type=Path, action="append", default=[])
    args = p.parse_args()
    if not 1 <= args.threads <= 256 or any(not 1 <= n <= 999999 for n in args.frames):
        p.error("Use thread counts from 1 to 256 and frame numbers from 1 to 999999")
    available = len(os.sched_getaffinity(0))
    if not 1 <= args.workers <= 64 or args.workers * args.threads > available:
        p.error(f"Worker count times thread count must fit {available} available CPU slots")
    scene = args.scene.resolve(strict=True)
    if scene.suffix != ".blend":
        p.error("Supply a .blend scene")
    blender = shutil.which("blender")
    decoder = shutil.which("ffmpeg")
    if not blender or not decoder:
        p.error("Install Blender and FFmpeg on the selected render worker")
    dependencies = [scene, *(p.resolve(strict=True) for p in args.asset)]
    source = {str(path): digest(path) for path in sorted(set(dependencies))}
    recipe = {"input_files": source, "blender": subprocess.check_output([blender, "--version"], text=True),
              "blender_executable_sha256": digest(Path(blender)), "threads": args.threads,
              "encoding": "PNG", "autoexec": False}
    key = sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    receipt_path = output / "render.json"
    with (output / ".render.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipt = (json.loads(receipt_path.read_text()) if receipt_path.exists()
                   else {"recipe_sha256": key, "recipe": recipe, "frames": {}})
        if receipt["recipe_sha256"] != key:
            p.error("Render settings or inputs changed. Choose a new output directory.")
        results = {"rendered": [], "reused": []}
        pending = []
        for number in sorted(set(args.frames)):
            name = f"frame-{number:06d}.png"
            existing = output / name
            known = receipt["frames"].get(name)
            if known and existing.is_file() and digest(existing) == known:
                results["reused"].append(number)
            else:
                pending.append(number)
        with tempfile.TemporaryDirectory(dir=output, prefix=".frames-") as temp:
            staging = Path(temp)

            def render(number):
                path = staging / f"frame-{number:06d}.png"
                run = subprocess.run([blender, "-b", "--factory-startup", "--disable-autoexec",
                                      str(scene), "-t", str(args.threads), "-o", str(staging / "frame-######"),
                                      "-F", "PNG", "-f", str(number)], capture_output=True, text=True, timeout=3600)
                if run.returncode or not path.is_file():
                    raise RuntimeError(f"Frame {number} failed:\n{run.stderr[-1600:]}\n{run.stdout[-1600:]}")
                subprocess.run([decoder, "-v", "error", "-xerror", "-threads", "1", "-i", str(path),
                                "-frames:v", "1", "-f", "null", "-"], check=True, timeout=60)
                return number, path, digest(path)

            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for number, path, checksum in pool.map(render, pending):
                    if any(digest(Path(name)) != value for name, value in source.items()):
                        raise RuntimeError("A render input changed while Blender was running")
                    path.replace(output / path.name)
                    receipt["frames"][path.name] = checksum
                    publish(receipt_path, receipt)
                    results["rendered"].append(number)
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
