#!/usr/bin/env python3
"""Evaluate portal-class evidence without allowing class-skipping.

Input:
{
  "requested_class": "P2_field_energy",
  "satisfied_requirements": ["..."],
  "independent_replications": 0
}
"""

import argparse
import json
from pathlib import Path


ORDER = [
    "P0_perceptual",
    "P1_information",
    "P2_field_energy",
    "P3_matter_transport",
    "P4_spacetime_connection",
]


def evaluate(evidence: dict, policy: dict) -> dict:
    requested = evidence["requested_class"]
    if requested not in ORDER:
        raise ValueError("unknown portal class")

    satisfied = set(evidence.get("satisfied_requirements", []))
    by_class = {x["class"]: x for x in policy["classes"]}

    gates = []
    highest = None
    for cls in ORDER[: ORDER.index(requested) + 1]:
        required = by_class[cls]["minimum_required"]
        missing = [x for x in required if x not in satisfied]
        passed = not missing

        # P1+ requires at least one independent replication unless a stronger
        # class states an even stronger requirement in the supplied evidence.
        if cls != "P0_perceptual" and int(evidence.get("independent_replications", 0)) < 1:
            if "at least one independent replication" not in missing:
                missing.append("at least one independent replication")
            passed = False

        gates.append({
            "class": cls,
            "passed": passed,
            "missing": missing,
        })
        if passed and all(g["passed"] for g in gates):
            highest = cls
        else:
            break

    return {
        "schema_version": 1,
        "requested_class": requested,
        "highest_supported_class": highest,
        "requested_class_supported": highest == requested,
        "gates": gates,
        "interpretation": (
            "Evidence gate result only. Passing a class means supplied evidence "
            "meets this policy's minimum structure; it does not establish the "
            "underlying exotic mechanism."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("evidence", type=Path)
    p.add_argument(
        "--policy",
        type=Path,
        default=Path("config/portal_evidence_policy.json"),
    )
    args = p.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    print(json.dumps(evaluate(evidence, policy), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
