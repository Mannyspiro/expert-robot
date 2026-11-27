"""Validate a Merlin series plan and the review and stream gates for its master."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def planned(path):
    plan = load(path)
    chapters = plan["chapters"]
    ids = [chapter["id"] for chapter in chapters]
    if not chapters or len(set(ids)) != len(ids) or not all(re.fullmatch(r"[a-zA-Z0-9_-]+", i) for i in ids):
        raise ValueError("Chapter IDs must be unique filename-safe strings")
    if any(type(c["seconds"]) is not int or c["seconds"] <= 0 or not c["question"].strip() for c in chapters):
        raise ValueError("Each chapter needs a positive duration and a research question")
    total = sum(c["seconds"] for c in chapters)
    if total != plan["target_seconds"]:
        raise ValueError(f"Expected {plan['target_seconds']} planned seconds, got {total}")
    return plan, ids


def run(*command):
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout


def probe(path):
    data = json.loads(run("ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)))
    keys = ("codec_type", "codec_name", "profile", "width", "height", "pix_fmt", "sample_rate",
            "channel_layout", "r_frame_rate", "time_base", "color_space", "color_primaries", "color_transfer")
    streams = data["streams"]
    if [s["codec_type"] for s in streams] != ["video", "audio"]:
        raise ValueError(f"{path.name}: expected one video stream followed by one audio stream")
    return tuple(tuple(s.get(key) for key in keys) for s in streams), float(data["format"]["duration"])


def checked_review(claims, chapter, path):
    if not claims.get("writer") or not claims.get("reviewer") or claims["writer"] == claims["reviewer"]:
        raise ValueError(f"{chapter}: record an independent named reviewer")
    for aspect in ("writing", "animation", "screen_design"):
        score = claims.get("scores", {}).get(aspect)
        if type(score) not in (int, float) or not 8 < score <= 10:
            raise ValueError(f"{chapter}: {aspect} must exceed 8/10")
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if claims.get("video_sha256") != digest:
        raise ValueError(f"{chapter}: reviewer must identify the exact cut by SHA-256")
    if claims.get("technical_pass") is not True:
        raise ValueError(f"{chapter}: require an explicit technical pass")


def local_file(folder, name):
    path = (folder / name).resolve()
    if not path.is_relative_to(folder) or not path.is_file():
        raise ValueError(f"Missing or external manifest file: {name}")
    return path


def assemble(plan, ids, manifest, output):
    items = load(manifest)
    if [item["chapter"] for item in items] != ids:
        raise ValueError("Manifest chapter IDs must match the plan in order")
    paths, shapes = [], set()
    durations = []
    folder = manifest.resolve().parent
    for chapter, item in zip(plan["chapters"], items, strict=True):
        path = local_file(folder, item["video"])
        checked_review(load(local_file(folder, item["review"])), chapter["id"], path)
        shape, duration = probe(path)
        if abs(duration - chapter["seconds"]) > 1:
            raise ValueError(f"{chapter['id']}: video differs from its planned duration by more than one second")
        paths.append(path)
        shapes.add(shape)
        durations.append(duration)
    if len(shapes) != 1:
        raise ValueError("Normalize all chapter streams before assembly")
    output = output.resolve()
    if output.exists():
        raise FileExistsError(output)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".merlin-master-") as stage:
        stage = Path(stage)
        entries = []
        for i, path in enumerate(paths):
            name = f"chapter-{i:03d}.mp4"
            (stage / name).symlink_to(path)
            entries.append(f"file {name}")
        listing = stage / "chapters.ffconcat"
        listing.write_text("ffconcat version 1.0\n" + "\n".join(entries) + "\n")
        temporary = stage / "master.mp4"
        run("ffmpeg", "-v", "error", "-f", "concat", "-safe", "1", "-i", str(listing),
            "-c", "copy", "-movflags", "+faststart", str(temporary))
        _, duration = probe(temporary)
        if abs(duration - sum(durations)) > 1:
            raise ValueError("Master duration disagrees with the input streams")
        output.hardlink_to(temporary)
    return duration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if bool(args.manifest) != bool(args.output):
        parser.error("--manifest and --output are required together")
    try:
        plan, ids = planned(args.plan)
        result = {"title": plan["title"], "chapters": len(ids), "planned_seconds": plan["target_seconds"]}
        if args.manifest:
            result["assembled_seconds"] = assemble(plan, ids, args.manifest, args.output)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
