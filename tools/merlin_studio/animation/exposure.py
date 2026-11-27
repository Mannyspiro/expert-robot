"""Compile named dialogue clips and Rhubarb cues into exact frame exposures."""

import argparse
from bisect import bisect_right
import csv
from decimal import Decimal
from fractions import Fraction
import json
from pathlib import Path
import re


SHAPES = frozenset("ABCDEFGHX")


def time_value(value):
    if type(value) not in (Decimal, float, int, str):
        raise ValueError("Time must be a finite decimal or rational")
    return Fraction(str(value))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)


def validate_spans(spans, duration=None):
    previous = Fraction(0)
    for start, end in spans:
        if not previous <= start < end or (duration is not None and end > duration):
            raise ValueError("Time spans must be positive, ordered, non-overlapping and within their clip")
        previous = end


def load_lines(timing_path, cues_folder, duration):
    lines = []
    identifiers = set()
    for record in read_json(timing_path):
        identifier, speaker = record["id"], record["speaker"]
        if not all(re.fullmatch(r"[a-zA-Z0-9_-]+", x) for x in (identifier, speaker)):
            raise ValueError("Line and speaker IDs must be filename-safe")
        if identifier in identifiers:
            raise ValueError(f"Duplicate line ID: {identifier}")
        identifiers.add(identifier)
        start, end = (time_value(record[key]) for key in ("start", "end"))
        cues_doc = read_json(cues_folder / f"{identifier}.json")
        cue_duration = time_value(cues_doc["metadata"]["duration"])
        if abs(cue_duration - (end-start)) > Fraction("0.02"):
            raise ValueError(f"Rhubarb duration disagrees with dialogue timing for {identifier}")
        cues = [(time_value(cue["start"]), time_value(cue["end"]), cue["value"])
                for cue in cues_doc["mouthCues"]]
        if not cues or any(shape not in SHAPES for _, _, shape in cues):
            raise ValueError(f"Empty cues or unsupported mouth drawing for {identifier}")
        validate_spans(((a, b) for a, b, _ in cues), cue_duration)
        lines.append((start, end, speaker, identifier, cues))
    validate_spans(((a, b) for a, b, *_ in lines), duration)
    return lines


def compile_exposures(lines, start, end, fps, hold=1):
    if start < 0 or end <= start or not 1 <= fps <= 120 or hold not in (1, 2):
        raise ValueError("Require increasing times, an FPS in [1,120] and a drawing hold of 1 or 2")
    frames = (end - start) * fps
    if frames.denominator != 1 or frames <= 0 or frames > 2_000_000:
        raise ValueError("The explicit range must end on a frame boundary and contain at most two million frames")
    line_starts = [line[0] for line in lines]
    cue_starts = [[cue[0] for cue in line[4]] for line in lines]
    previous_line = ""
    previous_shape = "X"
    age = 0
    runs = []
    for frame in range(int(frames)):
        instant = start + Fraction(2*frame+1, 2)/fps
        index = bisect_right(line_starts, instant) - 1
        line_id, actor, shape = "", "", "X"
        if index >= 0:
            a, b, speaker, identifier, cues = lines[index]
            if instant < b:
                line_id, actor = identifier, speaker
                offset = instant - a
                nearest = bisect_right(cue_starts[index], offset) - 1
                if nearest >= 0 and offset < cues[nearest][1]:
                    shape = cues[nearest][2]
        if line_id != previous_line or shape == "X" or previous_shape == "X" or age >= hold:
            previous_shape = shape
            age = 0
        stamp = (line_id, actor, previous_shape)
        if runs and runs[-1][2:] == stamp:
            prior = runs[-1]
            runs[-1] = (prior[0], frame+1, *stamp)
        else:
            runs.append((frame, frame+1, *stamp))
        age += 1
        previous_line = line_id
    return runs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("timing", type=Path)
    p.add_argument("cues", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--duration", type=time_value, required=True, help="Full audio duration")
    p.add_argument("--start", type=time_value, default=Fraction(0))
    p.add_argument("--end", type=time_value, required=True, help="End of frame-aligned edit window")
    p.add_argument("--fps", type=time_value, default=Fraction(24))
    p.add_argument("--hold", type=int, choices=(1, 2), default=1)
    args = p.parse_args()
    try:
        if args.end > args.duration:
            raise ValueError("The edit window extends beyond the audio.")
        lines = load_lines(args.timing, args.cues, args.duration)
        rows = compile_exposures(lines, args.start, args.end, args.fps, args.hold)
        with args.output.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(("first_frame", "end_frame_exclusive", "line", "speaker", "mouth"))
            writer.writerows(rows)
    except (OSError, ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        p.exit(1, f"{exc}\n")
    print(json.dumps({"exposures": len(rows), "frames": rows[-1][1], "fps": str(args.fps)}))


if __name__ == "__main__":
    main()
