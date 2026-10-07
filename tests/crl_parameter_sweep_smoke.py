#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

crl = load("crl", ROOT / "scripts" / "compile_crl.py")
planner = load("planner", ROOT / "scripts" / "plan_crl_parameters.py")

path = ROOT / "config" / "examples" / "heptameron_circle.crl"
ir = crl.parse(path.read_text(encoding="utf-8"), str(path))

assert {p["id"] for p in ir["parameters"]} == {"ritual-day", "ritual-hour"}
assert len(ir["bindings"]) == 3
assert ir["energy_inputs"][0]["kind"] == "acoustic"
assert len(ir["processes"]) == 3

plan = planner.plan(ir, max_variants=16)
assert plan["design"] == "baseline_plus_one_factor_at_a_time"
assert plan["variant_count"] <= 16
assert plan["variants"][0]["variant_id"] == "baseline"
assert plan["variants"][0]["assignments"]["ritual-day"] == "Sunday"
assert plan["variants"][0]["assignments"]["ritual-hour"] == 1
assert any(v["assignments"]["ritual-day"] == "Monday" for v in plan["variants"])
assert any(v["assignments"]["ritual-hour"] == 12 for v in plan["variants"])
assert all(len(v["changed_parameters"]) <= 1 for v in plan["variants"])

print("CRL parameter sweep planner: PASS")
