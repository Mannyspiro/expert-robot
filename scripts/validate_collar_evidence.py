#!/usr/bin/env python3
"""Validate trusted collared-generation evidence before qualification can promote it."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument("evidence",type=Path)
    p.add_argument("--candidate-sha",required=True)
    p.add_argument("--base-sha",required=True)
    p.add_argument("--output",type=Path)
    args=p.parse_args()

    raw=args.evidence.read_bytes()
    payload=json.loads(raw)
    runtime=payload.get("runtime_result",{})
    budget=payload.get("generation_budget",{})

    checks={
        "candidate_sha_matches": payload.get("candidate_sha")==args.candidate_sha,
        "base_sha_matches": payload.get("parent_sha")==args.base_sha,
        "generation_budget_estimated": budget.get("estimated") is True and int(budget.get("recommended_runs",0))>=1,
        "actual_runs_bounded": 1 <= int(budget.get("actual_runs",0)) <= int(budget.get("recommended_runs",0)),
        "collar_not_tripped": runtime.get("tripped") is False,
        "no_promotion_authority": runtime.get("promotion_authority") is False,
        "image_digest_pinned": runtime.get("image_digest_pinned") is True,
        "plaintext_not_persisted": runtime.get("plaintext_persisted") is False,
        "key_not_persisted": runtime.get("generation_key_persisted") is False,
        "lineage_verified": payload.get("lineage_verified") is True,
        "core_integrity_verified": payload.get("core_integrity_verified") is True,
        "authority_same_or_less": payload.get("authority_change") in {"same","less"},
    }
    failed=[name for name,ok in checks.items() if not ok]
    result={
        "schema_version":1,
        "candidate_id":payload.get("candidate_id",""),
        "candidate_sha":args.candidate_sha,
        "parent_sha":args.base_sha,
        "source_run_id":payload.get("source_run_id"),
        "generation_budget_estimated":checks["generation_budget_estimated"],
        "collared_execution":not failed,
        "lineage_verified":checks["lineage_verified"],
        "core_integrity_verified":checks["core_integrity_verified"],
        "authority_change":payload.get("authority_change","unverified"),
        "collar_tripped":runtime.get("tripped",True),
        "evidence_sha256":hashlib.sha256(raw).hexdigest(),
        "checks":checks,
        "failed_checks":failed,
    }
    rendered=json.dumps(result,indent=2)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(rendered,encoding="utf-8")
    print(rendered,end="")
    if failed:
        raise SystemExit(2)


if __name__=="__main__":
    main()
