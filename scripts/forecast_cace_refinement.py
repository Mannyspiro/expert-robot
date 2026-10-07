#!/usr/bin/env python3
"""Theorem-backed advisory forecast for CACE uniform refinement depth."""

from __future__ import annotations
import argparse, json, math
from pathlib import Path


def forecast(h0: float, target_h: float, bridge: dict) -> dict:
    if h0 <= 0 or target_h <= 0:
        raise ValueError("h0 and target_h must be positive")
    if bridge["formal_status"] != "LOCAL_GEOMETRY_PROVEN_IMPLEMENTATION_BRIDGE_EMPIRICAL":
        raise ValueError("unexpected bridge formal status")
    if not bridge["runtime_policy"]["may_use_for_advisory_planning"]:
        raise ValueError("bridge does not permit advisory planning")

    if target_h >= h0:
        levels = 0
    else:
        levels = math.ceil(math.log2(h0 / target_h))

    predicted = h0 / (2 ** levels)
    previous = h0 / (2 ** (levels - 1)) if levels > 0 else None
    minimal = levels == 0 or (previous is not None and previous > target_h)

    return {
        "schema_version": 1,
        "bridge_id": bridge["bridge_id"],
        "h0": h0,
        "target_h": target_h,
        "recommended_uniform_levels": levels,
        "predicted_h_after_levels": predicted,
        "minimal_level_under_halving_model": minimal,
        "formal_geometry_refs": bridge["formal_geometry_refs"],
        "evidence_scope": bridge["formal_status"],
        "advisory_only": True,
        "must_still_validate_resulting_mesh": True,
        "must_not_be_used_as_continuum_error_certificate": True
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--h0",type=float,required=True)
    p.add_argument("--target-h",type=float,required=True)
    p.add_argument(
        "--bridge",
        type=Path,
        default=Path("config/cace_refinement_formal_bridge.json"),
    )
    args=p.parse_args()
    bridge=json.loads(args.bridge.read_text(encoding="utf-8"))
    print(json.dumps(forecast(args.h0,args.target_h,bridge),indent=2,sort_keys=True))


if __name__=="__main__":
    main()
