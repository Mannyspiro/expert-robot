#!/usr/bin/env python3
"""Evaluate whether a symmetry-reduction contract may be applied.

This gate is intentionally stricter than the geometry theorem. Every
correctness-relevant channel must be explicitly invariant before reduction.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FIELDS = [
    "geometry_invariant",
    "materials_invariant",
    "sources_invariant",
    "boundary_conditions_invariant",
    "observables_invariant",
    "orientation_metadata_invariant",
    "symbolic_channel_invariant",
]


def evaluate(contract: dict) -> dict:
    missing = [field for field in FIELDS if not bool(contract.get(field, False))]
    theorem_refs = contract.get("theorem_refs", [])
    benchmark = contract.get("benchmark_evidence", {})

    permitted = (
        not missing
        and bool(theorem_refs)
        and benchmark.get("exact_output_match") is True
        and benchmark.get("level") in {"component", "full_cace"}
        and contract.get("status") in {"COMPONENT_QUALIFIED","FULL_CACE_QUALIFIED"}
    )

    return {
        "schema_version": 1,
        "contract_id": contract.get("contract_id"),
        "reduction_permitted": permitted,
        "missing_invariance_proofs_or_declarations": missing,
        "theorem_refs_present": bool(theorem_refs),
        "benchmark_level": benchmark.get("level"),
        "status": contract.get("status"),
        "reason": (
            "all symmetry, benchmark, and qualification gates satisfied"
            if permitted
            else "fail-closed: geometry theorem/kernel benchmark alone is insufficient"
        ),
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("contract",type=Path)
    args=p.parse_args()
    payload=json.loads(args.contract.read_text(encoding="utf-8"))
    print(json.dumps(evaluate(payload),indent=2,sort_keys=True))


if __name__=="__main__":
    main()
