#!/usr/bin/env python3
"""Freeze a post-generation progression reference from trusted benchmark evidence."""

import argparse
import hashlib
import json
from pathlib import Path


def git_blob_sha(data: bytes) -> str:
    payload = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    return hashlib.sha1(payload).hexdigest()


def is_progression_case(case):
    tags=set(case.get("tags", []))
    return "progression" in tags or any(tag.startswith("hard_v") for tag in tags)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("results", type=Path)
    p.add_argument("--suite", type=Path, required=True)
    p.add_argument("--source-candidate-sha", required=True)
    p.add_argument("--source-run-id", type=int, required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--baseline-id", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    results = json.loads(args.results.read_text(encoding="utf-8"))
    suite_bytes = args.suite.read_bytes()
    suite = json.loads(suite_bytes)

    progression_validation = sorted(
        c["case_id"] for c in suite["cases"]
        if c["split"] == "validation" and is_progression_case(c)
    )
    progression_holdout = sorted(
        c["case_id"] for c in suite["cases"]
        if c["split"] == "holdout" and is_progression_case(c)
    )
    sentinels = sorted(
        c["case_id"] for c in suite["cases"]
        if c["split"] in {"validation", "holdout"}
        and not is_progression_case(c)
    )
    if not progression_validation or not progression_holdout or not sentinels:
        raise SystemExit("suite must contain progression validation, progression holdout, and sentinels")

    expected_variants = {v["variant_id"] for v in suite["variants"]}
    by_variant = {}
    for row in results.get("records", []):
        variant = row.get("variant", "").split("::", 1)[0]
        by_variant.setdefault(variant, {})[row.get("case_id", "")] = row
    if set(by_variant) != expected_variants:
        raise SystemExit(
            f"variant mismatch: got {sorted(by_variant)}, expected {sorted(expected_variants)}"
        )

    variants = {}
    case_evidence = {}
    required = set(progression_validation + progression_holdout + sentinels)
    for variant in sorted(expected_variants):
        rows = by_variant[variant]
        missing = sorted(required - set(rows))
        if missing:
            raise SystemExit(f"{variant}: missing cases: {missing}")
        sentinel_failures = [x for x in sentinels if not bool(rows[x].get("verified"))]
        if sentinel_failures:
            raise SystemExit(f"{variant}: G2 sentinel regression during calibration: {sentinel_failures}")

        val_rate = sum(bool(rows[x].get("verified")) for x in progression_validation) / len(progression_validation)
        hold_rate = sum(bool(rows[x].get("verified")) for x in progression_holdout) / len(progression_holdout)
        variants[variant] = {
            "validation": {"verified_rate": val_rate},
            "holdout": {"verified_rate": hold_rate},
        }
        case_evidence[variant] = {
            x: bool(rows[x].get("verified")) for x in sorted(required)
        }

    out = {
        "schema_version": 1,
        "baseline_id": args.baseline_id,
        "source_candidate_sha": args.source_candidate_sha,
        "source_calibration_run_id": args.source_run_id,
        "source_calibration_commit": args.source_commit,
        "suite_id": suite["suite_id"],
        "suite_git_blob_sha": git_blob_sha(suite_bytes),
        "purpose": (
            "Frozen post-G2 reference. Progression validation must improve; "
            "progression holdout is veto-only; saturated legacy cases are strict sentinels."
        ),
        "evaluation_case_ids": {
            "progression_validation": progression_validation,
            "progression_holdout": progression_holdout,
            "required_verified_sentinels": sentinels,
        },
        "variants": variants,
        "case_evidence": case_evidence,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
