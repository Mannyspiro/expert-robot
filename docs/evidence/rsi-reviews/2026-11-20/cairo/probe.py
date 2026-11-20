"""Check renderer-pinned receipt compatibility on the synthetic lab sheet."""
import argparse
import json
from pathlib import Path
from time import perf_counter

import cairosvg
from merlin.drafting_control import CHECKS, digest, guide_files, review_wiring
from merlin.wiring_sheet import read_sheet, wire_svg


def create(source, root):
    root.mkdir()
    raw = source.read_bytes()
    title, _, parts, pins, nets = read_sheet(raw)
    svg = wire_svg(title, parts, pins, nets)
    (root / "wiring.svg").write_bytes(svg)
    for path, content in guide_files(raw, svg, nets, "cairosvg").items():
        (root / path).write_bytes(content)
    controls = json.loads((root / "draft-controls.json").read_bytes())
    verdict = {
        "schema": "merlin-drafting-verdict/1",
        "reviewer": "fixed synthetic compatibility control",
        "notes": "Unchanged guide pixels",
        "source_sha256": controls["source_sha256"],
        "guide_sha256": controls["guide_sha256"],
        "image_sha256": digest((root / "conditioning-guide.png").read_bytes()),
        "checks": dict.fromkeys(CHECKS, "pass"),
        "nets": [
            {"id": name, "status": "pass", "connections": [
                {"from": row["from"], "to": row["to"], "status": "pass"} for row in connections
            ]}
            for name, connections in controls["nets"].items()
        ],
    }
    (root / "verdict.json").write_text(json.dumps(verdict))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("guide", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("--create", action="store_true")
    args = parser.parse_args()
    start = perf_counter()
    if args.create:
        create(args.source, args.guide)
    try:
        outcome = review_wiring(args.source, args.guide, args.guide / "conditioning-guide.png",
                                args.guide / "verdict.json", args.result)["decision"]
    except ValueError as error:
        outcome = f"refused: {error}"
    print(json.dumps({"runtime": cairosvg.__version__,
                      "guide":json.loads((args.guide/"draft-controls.json").read_bytes())["renderer"],
                      "decision":outcome,"receipt_written":(args.result/"review.json").exists(),
                      "wall_seconds":round(perf_counter()-start,4)}))
