#!/usr/bin/env python3
"""Verify a checked-out CACE repository against the pinned FEM-ND contract."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_extractor():
    path = ROOT / "scripts" / "extract_cace_contracts.py"
    spec = importlib.util.spec_from_file_location("extract_cace_contracts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load contract extractor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def declared_specs(actual: dict, assignment: str, constructor: str) -> list[str]:
    entry = actual.get("class_assignments", {}).get(assignment)
    if not entry or not entry.get("expression"):
        return []
    tree = ast.parse(entry["expression"], mode="eval")
    names = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func.id if isinstance(node.func, ast.Name) else None
        if fn != constructor or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            names.append(first.value)
    return names


def verify(cace_root: Path, pin: dict) -> dict:
    actual_commit = subprocess.check_output(
        ["git", "-C", str(cace_root), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    extractor = load_extractor()
    extracted = extractor.extract(cace_root)
    files = {f["path"]: f for f in extracted["files"]}
    target = files.get(pin["module"])
    if target is None:
        raise ValueError(f"missing pinned module {pin['module']}")

    classes = {c["class"]: c for c in target["classes"]}
    mismatches = []
    for expected in pin["classes"]:
        actual = classes.get(expected["name"])
        if actual is None:
            mismatches.append({"class": expected["name"], "reason": "missing"})
            continue
        checks = {
            "inputs": declared_specs(actual, "inputs", "PortSpec"),
            "params": declared_specs(actual, "parameters", "ParameterSpec"),
            "outputs": declared_specs(actual, "outputs", "PortSpec"),
        }
        for key, actual_values in checks.items():
            if sorted(actual_values) != sorted(expected[key]):
                mismatches.append({
                    "class": expected["name"],
                    "field": key,
                    "expected": sorted(expected[key]),
                    "actual": sorted(actual_values),
                })

    return {
        "schema_version": 1,
        "expected_commit": pin["commit"],
        "actual_commit": actual_commit,
        "commit_matches": actual_commit == pin["commit"],
        "contract_matches": not mismatches,
        "mismatches": mismatches,
        "compatible": actual_commit == pin["commit"] and not mismatches,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cace_root", type=Path)
    p.add_argument(
        "--pin",
        type=Path,
        default=ROOT / "config" / "cace_fem_nd_contract_pin.json",
    )
    args = p.parse_args()
    pin = json.loads(args.pin.read_text(encoding="utf-8"))
    result = verify(args.cace_root, pin)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["compatible"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
