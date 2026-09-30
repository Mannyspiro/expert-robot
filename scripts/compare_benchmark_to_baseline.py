#!/usr/bin/env python3
"""Compare a benchmark run to the frozen G0 baseline without using holdout to rank candidates."""

import argparse
import json
from pathlib import Path


def all_summary(payload, variant, split):
    for item in payload.get("summaries", []):
        if item.get("variant") == variant and item.get("split") == split and item.get("domain") == "all":
            return item
    raise KeyError(f"missing all-domain summary for {variant}/{split}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("current", type=Path)
    p.add_argument("--baseline", type=Path, default=Path("config/benchmarks/g0_baseline.json"))
    p.add_argument("--output", type=Path, default=Path("build/benchmark-merit.json"))
    args = p.parse_args()

    current = json.loads(args.current.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    overlap_ids = set(baseline["evaluation_case_ids"]["holdout_overlap"])

    records_by_variant = {}
    for row in current.get("records", []):
        raw_variant = row.get("variant", "")
        variant = raw_variant.split("::", 1)[0]
        records_by_variant.setdefault(variant, {})[row.get("case_id", "")] = row

    evaluated = []
    for variant, old in sorted(baseline["variants"].items()):
        validation = all_summary(current, variant, "validation")
        validation_delta = float(validation["verified_rate"]) - float(old["validation"]["verified_rate"])

        overlap_rows = [
            records_by_variant.get(variant, {}).get(case_id)
            for case_id in sorted(overlap_ids)
        ]
        overlap_rows = [row for row in overlap_rows if row is not None]
        if len(overlap_rows) != len(overlap_ids):
            missing = sorted(overlap_ids - {row["case_id"] for row in overlap_rows})
            raise SystemExit(f"{variant}: missing frozen holdout overlap cases: {missing}")

        current_holdout_rate = sum(bool(row.get("verified")) for row in overlap_rows) / len(overlap_rows)
        baseline_holdout_rate = float(old["holdout"]["verified_rate"])
        holdout_delta = current_holdout_rate - baseline_holdout_rate

        evaluated.append({
            "variant": variant,
            "validation_verified_rate": float(validation["verified_rate"]),
            "validation_verified_rate_delta": validation_delta,
            "validation_average_proof_attempts": float(validation["average_proof_attempts"]),
            "validation_average_resource_cost": float(validation["average_resource_cost"]),
            "holdout_overlap_verified_rate": current_holdout_rate,
            "holdout_verified_rate_delta": holdout_delta,
            "holdout_non_regression": holdout_delta >= 0.0,
            "merit_demonstrated": validation_delta > 0.0,
        })

    # Holdout is a veto only. Among non-regressing variants, rank solely by
    # validation improvement and then validation efficiency.
    eligible = [
        row for row in evaluated
        if row["merit_demonstrated"] and row["holdout_non_regression"]
    ]
    eligible.sort(key=lambda row: (
        -row["validation_verified_rate_delta"],
        row["validation_average_resource_cost"],
        row["validation_average_proof_attempts"],
        row["variant"],
    ))
    selected = eligible[0] if eligible else None

    output = {
        "schema_version": 1,
        "baseline_id": baseline["baseline_id"],
        "baseline_source_run_id": baseline["source_run_id"],
        "current_run_id": current.get("run_id", ""),
        "selection_policy": "holdout is veto-only; ranking uses validation gain then validation efficiency",
        "merit_demonstrated": selected is not None,
        "selected_variant": selected["variant"] if selected else None,
        "validation_verified_rate_delta": selected["validation_verified_rate_delta"] if selected else 0.0,
        "holdout_verified_rate_delta": selected["holdout_verified_rate_delta"] if selected else 0.0,
        "blind_holdout_non_regression": bool(selected and selected["holdout_non_regression"]),
        "evaluated_variants": evaluated,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
