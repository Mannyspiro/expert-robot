#!/usr/bin/env python3
"""Rank Magick IR experiments by expected information value.

This tool does not estimate whether a historical supernatural claim is true.
It prioritizes controlled experiments that can most efficiently distinguish
ordinary physical/informational explanations from candidate anomalies.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


POSITIVE_WEIGHTS = {
    "information_gain": 0.25,
    "identifiability": 0.20,
    "known_physics_coverage": 0.15,
    "reproducibility": 0.10,
    "source_independence": 0.10,
    "transmission_specificity": 0.10,
    "prior_physical_support": 0.10,
}

PENALTY_WEIGHTS = {
    "normalized_cost": 0.10,
    "confound_risk": 0.15,
    "hazard": 0.10,
}


def unit(value: float, name: str) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {value}")
    return value


def score(candidate: dict) -> dict:
    components = {}
    total = 0.0

    for key, weight in POSITIVE_WEIGHTS.items():
        value = unit(float(candidate[key]), key)
        contribution = weight * value
        components[key] = contribution
        total += contribution

    for key, weight in PENALTY_WEIGHTS.items():
        value = unit(float(candidate[key]), key)
        contribution = -weight * value
        components[key] = contribution
        total += contribution

    portal_class = candidate.get("portal_class", "P0_perceptual")

    # Fail-closed ordering: high-level portal claims cannot outrank a more
    # identifiable lower-level experiment merely because their narrative claim
    # is dramatic. This is a prioritization prior, not a truth judgment.
    class_multiplier = {
        "P0_perceptual": 1.00,
        "P1_information": 0.95,
        "P2_field_energy": 0.80,
        "P3_matter_transport": 0.45,
        "P4_spacetime_connection": 0.25,
    }.get(portal_class, 0.50)

    weighted = max(0.0, min(1.0, total * class_multiplier))

    return {
        "id": candidate["id"],
        "title": candidate["title"],
        "portal_class": portal_class,
        "score": round(weighted, 6),
        "raw_score": round(total, 6),
        "class_multiplier": class_multiplier,
        "components": {k: round(v, 6) for k, v in components.items()},
        "next_if_positive": candidate.get("next_if_positive"),
    }


def rank(payload: dict) -> dict:
    rows = [score(c) for c in payload["candidates"]]
    rows.sort(key=lambda row: (-row["score"], row["id"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    return {
        "schema_version": 1,
        "objective": (
            "maximize information gained about separable physical/informational "
            "channels while minimizing confounds, cost, and hazard"
        ),
        "ranking": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    print(json.dumps(rank(payload), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
