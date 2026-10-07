#!/usr/bin/env python3
"""Build an opt-in symmetry-reduced execution plan for CRL geometry variants.

This tool is intentionally not enabled by default. A component-qualified
symmetry contract must pass the fail-closed evaluator first.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


crl = load("compile_crl", ROOT / "scripts" / "compile_crl.py")
sym = load(
    "evaluate_symmetry_reduction",
    ROOT / "scripts" / "evaluate_symmetry_reduction.py",
)


def build_plan(crl_path: Path, contract: dict) -> dict:
    gate = sym.evaluate(contract)
    if not gate["reduction_permitted"]:
        raise ValueError(
            "symmetry reduction contract is not qualified: "
            + gate["reason"]
        )

    ir = crl.parse(crl_path.read_text(encoding="utf-8"), str(crl_path))
    if ir["geometry"].get("orientation_sensitive"):
        raise ValueError("CRL program declares orientation-sensitive geometry")
    if ir["symbols"]["tokens"]:
        raise ValueError(
            "generic reducer refuses symbolic tokens without a stronger "
            "symbolic invariance proof"
        )
    if ir["materials"]:
        raise ValueError(
            "generic reducer refuses material assignments without a stronger "
            "material-position proof"
        )
    if ir["acoustics"]["utterances"]:
        raise ValueError(
            "generic reducer refuses acoustic sources without a stronger "
            "source-field symmetry proof"
        )

    orbit = [0, 90, 180, 270]
    representative = 0
    return {
        "schema_version": 1,
        "experiment_id": ir["experiment_id"],
        "contract_id": contract["contract_id"],
        "transformation": contract["transformation"]["name"],
        "orbit": orbit,
        "canonical_representative_deg": representative,
        "execute_degrees": [representative],
        "reuse_map": {
            str(angle): representative
            for angle in orbit
        },
        "expected_compile_reduction_ratio": len(orbit),
        "optimization_scope": "CRL/exact-geometry component only",
        "full_cace_solver_qualified": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("crl", type=Path)
    p.add_argument(
        "--contract",
        type=Path,
        default=Path(
            "config/examples/"
            "quarter_turn_crl_component_symmetry_contract.json"
        ),
    )
    args = p.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    print(json.dumps(
        build_plan(args.crl, contract),
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
