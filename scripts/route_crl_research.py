#!/usr/bin/env python3
"""Route a CRL program into the appropriate CACE research pipelines.

Routes are additive:
- every CRL program gets the general occult/protocol packet;
- process-heavy chemistry/material programs also get the alchemy packet;
- P1-P4 portal-class programs get portal evidence requirements;
- every route may later feed experiment-to-math discovery.

Routing does not increase evidence level.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


crl = load("crl", ROOT / "scripts" / "compile_crl.py")
occult = load("occult", ROOT / "scripts" / "build_occult_experiment_packet.py")
alchemy = load("alchemy", ROOT / "scripts" / "build_alchemy_experiment_packet.py")


ALCHEMY_PROCESS_KINDS = {
    "heat", "cool", "mix", "grind", "dissolve", "precipitate",
    "filter", "distill", "sublime", "calcine",
}


def route_program(path: Path) -> dict[str, Any]:
    ir = crl.parse(path.read_text(encoding="utf-8"), str(path))
    routes = ["protocol", "magic_circle_or_occult"]

    process_kinds = {p["kind"] for p in ir.get("processes", [])}
    has_alchemy = bool(process_kinds & ALCHEMY_PROCESS_KINDS)
    if has_alchemy:
        routes.append("alchemy_material_transformation")

    portal_class = ir["claim"]["portal_class"]
    has_portal_route = portal_class != "P0_perceptual"
    if has_portal_route:
        routes.append("portal_evidence")

    packets: dict[str, Any] = {
        "protocol": occult.build(path),
    }
    if has_alchemy:
        packets["alchemy"] = alchemy.build(path)

    if has_portal_route:
        policy = json.loads(
            (ROOT / "config" / "portal_evidence_policy.json").read_text(
                encoding="utf-8"
            )
        )
        class_row = next(x for x in policy["classes"] if x["class"] == portal_class)
        packets["portal_requirements"] = {
            "requested_class": portal_class,
            "minimum_required": class_row["minimum_required"],
            "cannot_establish": class_row["cannot_establish"],
            "global_rules": policy["global_rules"],
            "status": "REQUIREMENTS_ONLY_NOT_SATISFIED",
        }

    return {
        "schema_version": 1,
        "experiment_id": ir["experiment_id"],
        "routes": routes,
        "packets": packets,
        "downstream": [
            "CACE simulation/certification",
            "physical experiment only when safety/bench policy permits",
            "experiment result ingestion",
            "experiment-inspired mathematics",
            "Lean proof search",
            "benchmark-gated optimization",
        ],
        "epistemic_status": "routing_and_experiment_design_only",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()

    result = route_program(args.input)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
