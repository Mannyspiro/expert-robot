#!/usr/bin/env python3
"""Export Titan evidence into a read-only Merlin dashboard projection."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys

SHA = re.compile(r"^[0-9a-f]{40}$")


def load(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=Path("docs/titan/evidence"))
    parser.add_argument("--provider-lock", type=Path, default=Path("config/titan/provider-lock.v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        lock = load(args.provider_lock)
        records = []
        for path in sorted(args.evidence_dir.glob("*.json")):
            item = load(path)
            workflow = item.get("workflow", {})
            source = item.get("source", {})
            commit = (workflow.get("commit_sha") or source.get("commit_sha")
                      or item.get("titan_source_commit") or item.get("source_commit_sha"))
            if not isinstance(commit, str) or not SHA.fullmatch(commit):
                raise ValueError(f"{path}: missing full source commit")
            run_id = workflow.get("run_id") or item.get("workflow_run_id") or item.get("source_workflow_run_id")
            if not isinstance(run_id, int):
                raise ValueError(f"{path}: missing workflow run_id")
            artifact = item.get("artifact", {})
            artifact_digest = (artifact.get("sha256") or artifact.get("zip_sha256")
                               or item.get("source_workflow_artifact_sha256"))
            runner = item.get("runner", {})
            evidence_type = item.get("evidence_type", "titan-evidence")
            known_answer = item.get("known_answer_tests_run", False)
            conclusion = workflow.get("conclusion")
            if known_answer:
                test_result = "pass" if conclusion == "success" else "fail"
            elif evidence_type == "titan-provider-inventory":
                test_result = "blocked"
            elif evidence_type == "cace-independent-titan-avrea-verification":
                test_result = item.get("cace_bundle_verification", "not_run")
            else:
                test_result = "pass" if conclusion == "success" else "not_run"
            records.append({
                "record_type": "merlin.research.titan-pqc",
                "record_id": f"titan-pqc:{commit}:{run_id}:{evidence_type}",
                "evidence_type": evidence_type,
                "candidate_id": "titan:pqc-standard-baselines",
                "source_repository": "Mannyspiro/expert-robot",
                "source_commit": commit,
                "provider_release": lock["provider"]["release"],
                "provider_commit": lock["provider"]["commit"],
                "vector_source_tag": lock["vectors"]["tag"],
                "vector_source_commit": lock["vectors"]["commit"],
                "workflow_run_id": run_id,
                "workflow_name": workflow.get("name") or item.get("workflow_name") or evidence_type,
                "workflow_url": workflow.get("run_url") or workflow.get("url") or item.get("workflow_url"),
                "verification_workflow_run_id": item.get("verification_workflow_run_id"),
                "runner_identity": (runner.get("name") or runner.get("runner_name") or runner.get("label")
                                    or item.get("runner_name") or item.get("runner_host")),
                "test_suites": ["FIPS203", "FIPS204", "FIPS205"] if known_answer else [],
                "test_result": test_result,
                "artifact_sha256": artifact_digest,
                "verification_artifact_sha256": item.get("cace_verification_artifact_sha256"),
                "cace_verification_status": item.get("cace_independent_verification")
                    or item.get("cace_bundle_verification", "not_run"),
                "receipt_profile": "cace-signed-attestation-v2/ML-DSA-65",
                "signature_status": item.get("signature_status", "unsigned"),
                "qualification_status": "research_only",
                "promotion_authority": False,
                "limitations": item.get("limitations", []),
                "evidence_path": str(path),
            })
        projection = {
            "schema_version": 1,
            "projection": "merlin-titan-research-read-only",
            "generated_from": "canonical Titan evidence files; no dashboard mutation",
            "records": records,
            "record_count": len(records),
            "production_eligible": False,
            "authority_expansion": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "record_count": len(records), "output": str(args.output)}))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "error_type": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
