"""Generate timed two-voice dialogue using Merlin's Kokoro narration assets."""

import argparse
import json
from pathlib import Path
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pilot", type=Path)
    p.add_argument("narrator_dir", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    sys.path.insert(0, str(args.narrator_dir.resolve()))
    from narrator import DEFAULT, Narrator, master, to_phones, write_wav, RATE
    import numpy as np

    plan = json.loads(args.pilot.read_text())
    profile = json.loads(DEFAULT.read_text())
    args.output.mkdir(exist_ok=True, parents=True)
    engine = Narrator()
    shots = plan["shots"]
    phones = to_phones([shot["text"] for shot in shots], profile["pronunciation"])
    tracks = [np.zeros(RATE * 3, dtype=np.float32)]
    timing = []
    cursor = len(tracks[0])
    for shot, phonemes in zip(shots, phones, strict=True):
        actor = plan["cast"][shot["speaker"]]
        sound = engine.generate(phonemes, actor["voice"], actor["pace"])
        silence = np.zeros(int(RATE * .7), dtype=np.float32)
        timing.append(dict(shot, start=cursor / RATE, end=(cursor + len(sound)) / RATE))
        tracks.extend((sound, silence))
        cursor += len(sound) + len(silence)
    tracks.append(np.zeros(2 * RATE, dtype=np.float32))
    raw = args.output / "raw.wav"
    write_wav(raw, np.concatenate(tracks), RATE)
    master(raw, args.output / "pilot.wav", profile)
    raw.unlink()
    (args.output / "timing.json").write_text(json.dumps(timing, indent=2) + "\n")


if __name__ == "__main__":
    main()
