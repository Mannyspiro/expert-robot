#!/usr/bin/env python3
"""Analyze feature preservation vs claimed function with witness dependence caps.

This tool is exploratory historical inference. It does NOT infer physical
efficacy. It answers questions such as:
- is a feature conserved across independent transmission groups?
- is a particular feature state enriched among witnesses sharing a claimed
  function?
- is a feature likely decorative/transmission-noisy or worth experimental
  attention?

Independence groups are collapsed first so copied witnesses cannot multiply
support.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


STATUS_WEIGHT = {
    "observed": 1.0,
    "inferred": 0.7,
    "disputed": 0.35,
    "missing": 0.0,
    "exclusion": 0.0,
}


def entropy(probs: list[float]) -> float:
    out = 0.0
    for p in probs:
        if p > 0:
            out -= p * math.log2(p)
    return out


def normalized_distribution(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in weights.items()}


def collapse_groups(payload: dict[str, Any]) -> dict[str, Any]:
    witnesses = {w["id"]: w for w in payload["witnesses"]}
    features = {f["id"]: f for f in payload["features"]}

    # group -> feature -> state -> effective support
    grouped: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(float))
    )
    group_functions: dict[str, set[str]] = defaultdict(set)

    for w in payload["witnesses"]:
        group_functions[w["independence_group"]].update(w["claimed_functions"])

    for obs in payload["observations"]:
        w = witnesses[obs["witness"]]
        if obs["feature"] not in features:
            raise ValueError(f"unknown feature {obs['feature']!r}")
        group = w["independence_group"]
        support = (
            float(w["weight"])
            * float(obs["confidence"])
            * STATUS_WEIGHT[obs["status"]]
        )
        # Within an independence group, take the strongest support for a
        # state rather than summing copied descendants.
        current = grouped[group][obs["feature"]][obs["state"]]
        grouped[group][obs["feature"]][obs["state"]] = max(current, support)

    return {
        "grouped": grouped,
        "group_functions": group_functions,
        "features": features,
    }


def feature_report(payload: dict[str, Any]) -> list[dict[str, Any]]:
    collapsed = collapse_groups(payload)
    grouped = collapsed["grouped"]
    group_functions = collapsed["group_functions"]
    reports = []

    all_groups = sorted(group_functions)
    all_functions = payload["functions"]

    for feature_id, feature in collapsed["features"].items():
        overall_states: dict[str, float] = defaultdict(float)
        observed_groups = 0

        for group in all_groups:
            states = grouped[group].get(feature_id, {})
            if states:
                observed_groups += 1
                for state, support in states.items():
                    overall_states[state] += support

        dist = normalized_distribution(overall_states)
        state_entropy = entropy(list(dist.values()))
        max_entropy = math.log2(max(1, len(dist))) if dist else 0.0
        normalized_entropy = 0.0 if max_entropy == 0 else state_entropy / max_entropy
        conservation = 1.0 - normalized_entropy if dist else 0.0
        coverage = observed_groups / max(1, len(all_groups))

        function_rows = []
        best_function_signal = 0.0
        for function in all_functions:
            with_groups = [g for g in all_groups if function in group_functions[g]]
            without_groups = [g for g in all_groups if function not in group_functions[g]]

            state_scores = []
            candidate_states = set()
            for g in all_groups:
                candidate_states.update(grouped[g].get(feature_id, {}).keys())

            for state in sorted(candidate_states):
                with_vals = [
                    grouped[g].get(feature_id, {}).get(state, 0.0)
                    for g in with_groups
                ]
                without_vals = [
                    grouped[g].get(feature_id, {}).get(state, 0.0)
                    for g in without_groups
                ]
                with_mean = sum(with_vals) / len(with_vals) if with_vals else 0.0
                without_mean = (
                    sum(without_vals) / len(without_vals) if without_vals else 0.0
                )
                enrichment = with_mean - without_mean
                state_scores.append({
                    "state": state,
                    "with_function_support": with_mean,
                    "without_function_support": without_mean,
                    "enrichment": enrichment,
                })
                best_function_signal = max(best_function_signal, abs(enrichment))

            function_rows.append({
                "function": function,
                "with_group_count": len(with_groups),
                "without_group_count": len(without_groups),
                "state_scores": state_scores,
            })

        # Research priority, not truth probability.
        #
        # A genuine protocol parameter may be globally variable precisely
        # because its state changes with function. Therefore global
        # conservation and function discrimination are complementary signals,
        # not multiplicative prerequisites. Coverage still scales the total
        # because sparse independent evidence should remain low priority.
        priority = coverage * (
            0.35 * conservation +
            0.65 * best_function_signal
        )

        if coverage < 0.34:
            classification = "INSUFFICIENT_INDEPENDENT_COVERAGE"
        elif best_function_signal >= 0.75:
            classification = "CANDIDATE_FUNCTION_CONDITIONED_PROTOCOL_PARAMETER"
        elif conservation >= 0.75 and best_function_signal >= 0.25:
            classification = "CANDIDATE_PROTOCOL_PARAMETER"
        elif conservation < 0.35 and best_function_signal < 0.15:
            classification = "LIKELY_TRANSMISSION_NOISY_OR_DECORATIVE"
        elif conservation >= 0.75:
            classification = "HIGHLY_CONSERVED_FUNCTION_UNRESOLVED"
        else:
            classification = "MIXED_REQUIRES_MORE_WITNESSES"

        reports.append({
            "feature_id": feature_id,
            "feature_class": feature["class"],
            "description": feature["description"],
            "independent_group_coverage": coverage,
            "state_distribution": dist,
            "normalized_state_entropy": normalized_entropy,
            "conservation_score": conservation,
            "best_function_signal": best_function_signal,
            "research_priority": priority,
            "classification": classification,
            "function_analysis": function_rows,
            "interpretation_guard": (
                "Historical transmission/function association only; does not "
                "demonstrate physical efficacy."
            ),
        })

    reports.sort(key=lambda x: (-x["research_priority"], x["feature_id"]))
    for i, row in enumerate(reports, 1):
        row["rank"] = i
    return reports


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "feature_count": len(payload["features"]),
        "independent_group_count": len(
            {w["independence_group"] for w in payload["witnesses"]}
        ),
        "features": feature_report(payload),
        "epistemic_status": "historical_inference_not_physical_evidence",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path)
    args = p.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    print(json.dumps(analyze(payload), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
