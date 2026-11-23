#!/usr/bin/env python3
"""Prioritize witness-conditioned historical loci for experimental testing.

The score is a transparent research-priority heuristic. It is NOT:
- a transmission probability,
- a probability of physical efficacy,
- or evidence for supernatural claims.

Loci sharing an independence_group are capped to one effective priority item.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

FEATURE_WEIGHT = {
    "scribal_error": 1.00,
    "topology": 0.95,
    "geometry_metric": 0.95,
    "symbol_order": 0.90,
    "material": 0.90,
    "process": 0.85,
    "orientation": 0.80,
    "timing": 0.80,
    "symbol_identity": 0.70,
    "other": 0.50,
}

STATUS_WEIGHT = {
    "observed": 1.00,
    "inferred": 0.70,
    "disputed": 0.40,
    "exclusion": 0.20,
    "missing": 0.00,
}


def load_crl():
    path = ROOT / "scripts" / "compile_crl.py"
    spec = importlib.util.spec_from_file_location("compile_crl", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load CRL compiler")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prioritize(ir: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}

    for locus in ir.get("historical_loci", []):
        base = FEATURE_WEIGHT[locus["feature_class"]]
        status = STATUS_WEIGHT[locus["evidence_status"]]
        confidence = float(locus["confidence"])
        score = base * status * confidence
        row = {
            "locus_id": locus["id"],
            "independence_group": locus["independence_group"],
            "feature_class": locus["feature_class"],
            "evidence_status": locus["evidence_status"],
            "confidence": confidence,
            "priority_score": round(score, 6),
            "experimental_target": locus.get("experimental_target"),
            "observed_state": locus["observed_state"],
            "witness_refs": locus["witness_refs"],
            "score_components": {
                "feature_discrimination_weight": base,
                "status_weight": status,
                "confidence": confidence,
            },
        }
        groups.setdefault(locus["independence_group"], []).append(row)

    effective = []
    suppressed = []
    for group, rows in groups.items():
        rows.sort(key=lambda r: (-r["priority_score"], r["locus_id"]))
        winner = rows[0]
        winner["effective_locus"] = True
        effective.append(winner)
        for row in rows[1:]:
            row["effective_locus"] = False
            row["suppressed_reason"] = "same_independence_group"
            suppressed.append(row)

    effective.sort(key=lambda r: (-r["priority_score"], r["locus_id"]))
    for rank, row in enumerate(effective, start=1):
        row["rank"] = rank

    return {
        "schema_version": 1,
        "experiment_id": ir["experiment_id"],
        "effective_locus_count": len(effective),
        "ranked_loci": effective,
        "suppressed_correlated_loci": suppressed,
        "score_semantics": (
            "research-priority heuristic only; not probability of ancestry, "
            "physical efficacy, anomaly, or supernatural causation"
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path, help=".crl source")
    args = p.parse_args()
    crl = load_crl()
    ir = crl.parse(args.input.read_text(encoding="utf-8"), str(args.input))
    print(json.dumps(prioritize(ir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
