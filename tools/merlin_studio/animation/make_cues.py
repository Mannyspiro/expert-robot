"""Run Rhubarb on each transcript-aligned line in a dialogue WAV."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import wave

from exposure import read_json, time_value, validate_spans


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rhubarb", type=Path)
    p.add_argument("audio", type=Path)
    p.add_argument("timing", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    binary = args.rhubarb.resolve(strict=True)
    source = args.audio.resolve(strict=True)
    out = args.output.resolve()
    if out.exists():
        p.error("Use a new output directory")
    lines = read_json(args.timing)
    with wave.open(str(source), "rb") as wav:
        duration = time_value(f"{wav.getnframes()}/{wav.getframerate()}")
    validate_spans(((time_value(line["start"]), time_value(line["end"])) for line in lines), duration)
    targets = {}
    with tempfile.TemporaryDirectory(dir=out.parent, prefix=".rhubarb-") as folder:
        work = Path(folder)
        for i, line in enumerate(lines):
            identifier = line["id"]
            if not identifier or any(c not in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-" for c in identifier):
                p.error("Use filename-safe dialogue IDs")
            if identifier in targets:
                p.error(f"Duplicate dialogue line: {identifier}")
            target = work / f"cue-{i}.json"
            tmp_audio, dialogue_text = work / "audio.wav", work / "script.txt"
            start, end = map(time_value, (line["start"],line["end"]))
            dialogue_text.write_text(line["text"], encoding="utf-8")
            subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{float(start):.8f}","-i",str(source),"-t",
                            f"{float(end-start):.8f}","-ac","1","-ar","16000",str(tmp_audio)],check=True,timeout=120)
            result = subprocess.run([str(binary),"-f","json","-o",str(target),"-d",str(dialogue_text),
                                     "--extendedShapes","GHX",str(tmp_audio)],capture_output=True,text=True,timeout=300)
            if result.returncode:
                raise RuntimeError(result.stderr[-1300:])
            document = json.loads(target.read_text())
            document["metadata"]["soundFile"] = source.name
            document["metadata"]["line"] = identifier
            target.write_text(json.dumps(document,indent=2)+"\n")
            targets[identifier] = target
        staged = work / "publish"
        staged.mkdir()
        for identifier, target in targets.items():
            target.rename(staged / f"{identifier}.json")
        staged.rename(out)
    print(json.dumps({"lines": len(targets), "audio_duration": str(duration), "rhubarb": subprocess.check_output(
        [str(binary),"--version"],text=True).strip()}))


if __name__ == "__main__":
    main()
