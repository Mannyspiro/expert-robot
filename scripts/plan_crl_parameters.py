#!/usr/bin/env python3
"""Plan bounded parameter sweeps for compiled CRL/Magick IR programs.

The default design is baseline + one-factor-at-a-time (OFAT), intentionally
avoiding combinatorial explosion. Interaction experiments should be promoted
only after individual channels show information value.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_crl_module():
    path = ROOT / "scripts" / "compile_crl.py"
    spec = importlib.util.spec_from_file_location("compile_crl", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load CRL compiler")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def levels(param: dict[str, Any]) -> list[Any]:
    if param.get("values"):
        return list(param["values"])
    kind = param["kind"]
    lo, hi = param.get("minimum"), param.get("maximum")
    if kind == "boolean":
        return [False, True]
    if kind == "integer" and lo is not None and hi is not None:
        lo, hi = int(lo), int(hi)
        if hi < lo:
            raise ValueError(f"{param['id']}: maximum < minimum")
        if hi - lo <= 6:
            return list(range(lo, hi + 1))
        mid = (lo + hi) // 2
        return list(dict.fromkeys([lo, mid, hi]))
    if kind == "continuous" and lo is not None and hi is not None:
        lo, hi = float(lo), float(hi)
        if hi < lo:
            raise ValueError(f"{param['id']}: maximum < minimum")
        return [lo, (lo + hi) / 2.0, hi]
    return []


def plan(ir: dict[str, Any], max_variants: int = 32) -> dict[str, Any]:
    if max_variants < 1:
        raise ValueError("max_variants must be positive")

    params = ir.get("parameters", [])
    resolved = []
    unresolved = []
    for p in params:
        lv = levels(p)
        if lv:
            resolved.append((p, lv))
        else:
            unresolved.append(p["id"])

    baseline = {p["id"]: lv[0] for p, lv in resolved}
    variants = [{
        "variant_id": "baseline",
        "assignments": dict(baseline),
        "changed_parameters": [],
    }]

    for p, lv in resolved:
        for value in lv[1:]:
            if len(variants) >= max_variants:
                break
            assignment = dict(baseline)
            assignment[p["id"]] = value
            variants.append({
                "variant_id": f"{p['id']}={value}",
                "assignments": assignment,
                "changed_parameters": [p["id"]],
            })
        if len(variants) >= max_variants:
            break

    return {
        "schema_version": 1,
        "experiment_id": ir["experiment_id"],
        "design": "baseline_plus_one_factor_at_a_time",
        "variant_count": len(variants),
        "variants": variants,
        "unresolved_parameters": unresolved,
        "bindings": ir.get("bindings", []),
        "interaction_policy": (
            "Do not schedule multi-parameter interactions by default. "
            "Promote interactions after single-parameter information gain."
        ),
        "epistemic_status": "experimental_design_not_evidence",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path, help=".crl file")
    p.add_argument("--max-variants", type=int, default=32)
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()

    crl = load_crl_module()
    ir = crl.parse(args.input.read_text(encoding="utf-8"), str(args.input))
    result = plan(ir, args.max_variants)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
