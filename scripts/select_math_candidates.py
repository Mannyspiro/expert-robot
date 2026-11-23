#!/usr/bin/env python3
"""Select experiment-inspired math candidates for counterexample/proof work.

Selection is intentionally conservative. Passing this script means only
"worth proof-search compute", never "true".
"""

import argparse
import json
from pathlib import Path


def select(payload: dict, policy: dict) -> dict:
    cfg = policy["candidate_selection"]
    selected = []
    rejected = []

    for candidate in payload.get("candidates", []):
        support = candidate.get("empirical_support", {})
        source = candidate.get("source_evidence", {})
        reasons = []

        fit = support.get("fit_score")
        if fit is None or float(fit) < float(cfg["minimum_fit_score"]):
            reasons.append("fit_below_threshold")
        if int(support.get("counterexamples_found", 0)) > int(
            cfg["maximum_observed_counterexamples"]
        ):
            reasons.append("observed_counterexample")
        if int(source.get("sample_count", 0)) < int(cfg["minimum_samples"]):
            reasons.append("too_few_samples")
        if cfg["require_source_artifact_hash"] and len(
            str(source.get("artifact_sha256", ""))
        ) != 64:
            reasons.append("missing_source_hash")
        if cfg["require_holdout_sealed_before_proof_search"] and not bool(
            source.get("holdout_sealed", False)
        ):
            reasons.append("holdout_not_sealed")
        if candidate.get("status") != "INSPIRED":
            reasons.append("unexpected_status")

        entry = {
            "candidate_id": candidate.get("candidate_id"),
            "pattern_class": candidate.get("pattern_class"),
            "informal_statement": candidate.get("informal_statement"),
            "formalization_target": candidate.get("formalization_target"),
            "proof_obligations": candidate.get("proof_obligations", []),
            "optimization_hypothesis": candidate.get("optimization_hypothesis"),
            "source_artifact_sha256": source.get("artifact_sha256"),
        }

        if reasons:
            entry["reasons"] = reasons
            rejected.append(entry)
        else:
            entry["next_stage"] = "COUNTEREXAMPLE_SEARCH"
            selected.append(entry)

    return {
        "schema_version": 1,
        "selected_count": len(selected),
        "rejected_count": len(rejected),
        "selected": selected,
        "rejected": rejected,
        "epistemic_status": "selected_for_testing_not_proven",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("candidates", type=Path)
    p.add_argument(
        "--policy",
        type=Path,
        default=Path("config/math_discovery_policy.json"),
    )
    args = p.parse_args()

    payload = json.loads(args.candidates.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    print(json.dumps(select(payload, policy), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
