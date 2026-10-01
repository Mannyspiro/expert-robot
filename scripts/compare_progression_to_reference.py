#!/usr/bin/env python3
"""Compare a progression benchmark to a frozen post-G2 reference.

Merit is measured only on hidden progression validation cases. Hidden holdout is
veto-only, and previously saturated core cases are strict regression sentinels.
"""

import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("current", type=Path)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("build/progression-merit.json"))
    args = p.parse_args()

    current = json.loads(args.current.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))

    validation_ids = set(baseline["evaluation_case_ids"]["progression_validation"])
    holdout_ids = set(baseline["evaluation_case_ids"]["progression_holdout"])
    sentinel_ids = set(baseline["evaluation_case_ids"]["required_verified_sentinels"])
    required_ids = validation_ids | holdout_ids | sentinel_ids

    records_by_variant = {}
    for row in current.get("records", []):
        raw_variant = row.get("variant", "")
        variant = raw_variant.split("::", 1)[0]
        records_by_variant.setdefault(variant, {})[row.get("case_id", "")] = row

    evaluated = []
    for variant, old in sorted(baseline["variants"].items()):
        rows = records_by_variant.get(variant, {})
        missing = sorted(required_ids - set(rows))
        if missing:
            raise SystemExit(f"{variant}: missing progression cases: {missing}")

        validation_rows = [rows[x] for x in sorted(validation_ids)]
        holdout_rows = [rows[x] for x in sorted(holdout_ids)]
        sentinel_failures = sorted(
            x for x in sentinel_ids if not bool(rows[x].get("verified"))
        )

        validation_rate = (
            sum(bool(x.get("verified")) for x in validation_rows)
            / len(validation_rows)
        )
        holdout_rate = (
            sum(bool(x.get("verified")) for x in holdout_rows)
            / len(holdout_rows)
        )
        validation_delta = validation_rate - float(old["validation"]["verified_rate"])
        holdout_delta = holdout_rate - float(old["holdout"]["verified_rate"])
        average_attempts = (
            sum(float(x.get("proof_attempts", 0.0)) for x in validation_rows)
            / len(validation_rows)
        )
        average_cost = (
            sum(float(x.get("resource_cost", 0.0)) for x in validation_rows)
            / len(validation_rows)
        )

        evaluated.append({
            "variant": variant,
            "progression_validation_verified_rate": validation_rate,
            "validation_verified_rate_delta": validation_delta,
            "validation_average_proof_attempts": average_attempts,
            "validation_average_resource_cost": average_cost,
            "progression_holdout_verified_rate": holdout_rate,
            "holdout_verified_rate_delta": holdout_delta,
            "blind_holdout_non_regression": holdout_delta >= 0.0,
            "sentinel_non_regression": not sentinel_failures,
            "sentinel_failures": sentinel_failures,
            "merit_demonstrated": validation_delta > 0.0,
        })

    eligible = [
        row for row in evaluated
        if row["merit_demonstrated"]
        and row["blind_holdout_non_regression"]
        and row["sentinel_non_regression"]
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
        "baseline_source_candidate_sha": baseline["source_candidate_sha"],
        "baseline_source_calibration_run_id": baseline["source_calibration_run_id"],
        "merit_demonstrated": selected is not None,
        "blind_holdout_non_regression": bool(
            selected and selected["blind_holdout_non_regression"]
        ),
        "sentinel_non_regression": bool(
            selected and selected["sentinel_non_regression"]
        ),
        "selected_variant": selected["variant"] if selected else None,
        "validation_verified_rate_delta": (
            selected["validation_verified_rate_delta"] if selected else 0.0
        ),
        "holdout_verified_rate_delta": (
            selected["holdout_verified_rate_delta"] if selected else 0.0
        ),
        "variants": evaluated,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
