#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"generate_math_puzzle_boxes.py"

spec=importlib.util.spec_from_file_location("boxes",SCRIPT)
module=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

a=module.generate(7)
b=module.generate(7)
assert a==b
assert len(a["boxes"])==len(module.FAMILIES)
assert all(x["sealed_construction"]["withhold_from_proposer"] for x in a["boxes"])
assert {x["family"] for x in a["boxes"]}==set(module.FAMILIES)

sym=next(x for x in a["boxes"] if x["family"]=="symmetry_orbit")
vals=sym["visible_problem"]["observables"][0]["values"]
assert len(set(vals))==1

hist=next(x for x in a["boxes"] if x["family"]=="historical_geometry_control")
assert "geometry" in hist["visible_problem"]["question"].lower()

print("math puzzle boxes: PASS")
