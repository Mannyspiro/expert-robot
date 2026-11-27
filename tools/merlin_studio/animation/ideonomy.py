"""Run the released Merlin Ideonomy enumerator on the anime tool catalogue."""

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
MERLIN_RESEARCH = ROOT / "docs/merlin/usb/source/payload/research"

PRIMITIVES = {
    "mouth-cues": ("audio", 2),
    "actor-routing": ("performance", 1),
    "exposure-sheet": ("animation", 1),
    "frame-hash": ("verification", 1),
    "shot-boundary": ("editorial", 1),
    "depth-layers": ("composition", 3),
    "camera-curve": ("camera", 2),
    "controlled-holds": ("timing", 1),
}
PROPOSALS = [
    ("Dialogue exposure compiler", ("mouth-cues", "actor-routing", "exposure-sheet"), (4, 4, 4, 4)),
    ("Exact match-cut verifier", ("frame-hash", "shot-boundary"), (4, 2, 4, 4)),
    ("Exposure hold optimizer", ("exposure-sheet", "controlled-holds"), (3, 2, 4, 4)),
    ("Layered camera move", ("depth-layers", "camera-curve"), (3, 3, 3, 2)),
]


def research(module_path):
    sys.path.insert(0, str(module_path.resolve()))
    from merlin_ideonomy import enumerate_combination_report
    rows = [{"id": name, "domain": domain, "estimated_cost": cost}
            for name, (domain, cost) in PRIMITIVES.items()]
    pairs = ("mouth-cues actor-routing", "mouth-cues exposure-sheet", "actor-routing exposure-sheet",
             "exposure-sheet controlled-holds", "frame-hash shot-boundary", "depth-layers camera-curve",
             "camera-curve controlled-holds", "shot-boundary controlled-holds", "shot-boundary exposure-sheet")
    data = enumerate_combination_report(rows, {frozenset(pair.split()) for pair in pairs},
        trigger="The pilot holds character artwork during separately timed dialogue",
        problem="Which tools add reusable character motion while preserving timing and edit integrity?",
        max_size=3, max_cost=6, limit=84, work_budget=84)
    available = {frozenset(row["primitive_ids"]) for row in data["candidates"]}
    weights = (4, 3, 2, 1)
    ranked = []
    for name, ids, scores in PROPOSALS:
        if frozenset(ids) not in available:
            raise ValueError(f"Proposed tool was excluded by the catalogue checks: {name}")
        ranked.append({"name": name, "primitives": list(ids), "judgment_scores": scores,
                       "weighted_percent": sum(w*s for w, s in zip(weights, scores, strict=True))*2.5})
    data["prioritization"] = {
        "evidence_class": "engineering judgments on a 0–4 scale",
        "criteria_and_weights": dict(zip(("immediate_need","visual_payoff","testability","readiness"),weights,strict=True)),
        "ranked_proposals": sorted(ranked, key=lambda row: -row["weighted_percent"]),
        "lenses": {
            "n_ality": "Track actor, cue, shot and frame as independent axes.",
            "simplex": "Deferred. Hard drawing categories are sufficient for this prototype.",
            "continuum": "Use half-open cue intervals and sample frame centers on a rational timeline.",
            "fuzzy": "Defer fuzzy quality scoring until a viewer labels examples. Timing and hashes use Boolean gates."
        }
    }
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--merlin-research", type=Path, default=MERLIN_RESEARCH)
    options = parser.parse_args()
    print(json.dumps(research(options.merlin_research), indent=2))
