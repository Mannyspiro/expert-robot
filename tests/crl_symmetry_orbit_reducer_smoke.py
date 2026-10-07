#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "reducer",
    ROOT / "scripts" / "reduce_crl_symmetry_orbit.py",
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

contract = json.loads(
    (
        ROOT
        / "config"
        / "examples"
        / "quarter_turn_crl_component_symmetry_contract.json"
    ).read_text(encoding="utf-8")
)
fixture = (
    ROOT
    / "config"
    / "examples"
    / "circle_symmetry_component.crl"
)

plan = module.build_plan(fixture, contract)
assert plan["execute_degrees"] == [0]
assert plan["reuse_map"]["90"] == 0
assert plan["reuse_map"]["180"] == 0
assert plan["reuse_map"]["270"] == 0
assert plan["expected_compile_reduction_ratio"] == 4
assert plan["full_cace_solver_qualified"] is False

print("CRL symmetry orbit reducer: PASS")
