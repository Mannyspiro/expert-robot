#!/usr/bin/env python3
"""Offline, restartable six-stage Merlin research software fixture.

Records real canonical artifact bytes and one declared negative control.
It does not run a model, produce a scientific discovery or grant authority.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from experimental_self_healing import EvidenceLedger
from merlin.project_registry import MerlinRegistry
from merlin.scientific_loop import Observation, Prediction
from merlin_research_session import ResearchFrame, ResearchReceipt, ResearchSession, STAGES

PROJECT = "merlin-offline-research-fixture"
RAW = b"hello-merlin!"
EXPECTED = 13


def commit_sha():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                            capture_output=True, timeout=10, check=False)
    sha = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("exact Git checkout required")
    if os.environ.get("MERLIN_EXPECTED_SHA", sha) != sha:
        raise RuntimeError("actual checkout differs from pinned source")
    return sha


def frame(sha):
    return ResearchFrame(
        cycle_id="merlin-reference-fixture-v1",
        plan_id="MERLIN-PRODUCTION-MASTER-20261117",
        plan_version=6, source_commit=sha,
        question="Does the pinned source still contain exactly thirteen bytes?",
        metric="bytes_count", unit="byte", baseline_ref="fixture:expected-thirteen-bytes",
        hypotheses=("raw bytes unchanged", "raw bytes changed"),
        predictions=(Prediction("bytes_count", EXPECTED, 0, "byte"),),
        falsifier="A source of a different length, version or digest",
        stopping_rule="One source read and one declared byte-append negative control",
        acceptance_rule="Observed exact byte count and SHA-256 match frozen reference",
        source_refs=("fixture:hello-merlin-v1",),
        unknowns=("Scientific generalization and real model use are not assessed",),
    )


def stage_payload(stage, ref, n):
    return {
        "schema": "merlin-local-reference-fixture/1",
        "stage": stage, "source_ref": ref, "expected_bytes": EXPECTED,
        "measured_bytes": n if stage in ("experiment", "challenge") else None,
        "negative_control_bytes": n + 1 if stage == "challenge" else None,
        "negative_control_rejects": n + 1 != EXPECTED if stage == "challenge" else None,
        "competing_explanations": ["intact", "mutated"] if stage == "explain" else None,
        "parent_plan": {"id": "MERLIN-PRODUCTION-MASTER-20261117", "version": 6}
        if stage == "update" else None,
        "decision": "fixture only, no master-plan completion or promotion"
        if stage == "update" else None,
        "independent_scientific_verification": False, "promotion_authority": False,
    }


def finish_report(session, registry):
    status = session.status()
    audit = session.verify_registry_bindings(registry, project_id=PROJECT)
    if not status["procedural_record_complete"] or not audit["all_six_stages_bound"]:
        raise RuntimeError("incomplete or unbound research stages; explicit review required")
    return {
        "schema": "merlin-local-reference-result/1",
        "status": "software_fixture_passed",
        "source_commit": session.frame.source_commit,
        "cycle_id": session.frame.cycle_id,
        "stages": status["stages"], "registry_readback": audit,
        "control": {"mutation": "append one zero byte", "count": EXPECTED + 1,
                    "predicted_count": EXPECTED, "rejected": True},
        "scientific_claim_established": False, "independent_scientific_verification": False,
        "real_model_qualified": False, "production_release_qualified": False,
        "promotion_authority": False, "external_spend_usd": 0,
    }


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    registry = MerlinRegistry(output / "registry")
    ledger = EvidenceLedger(output / "research-ledger.jsonl")
    protocol = frame(commit_sha())
    if ledger.path.exists():
        # A completed cycle can be read repeatedly. Interrupted cycles do not rerun.
        session = ResearchSession.open(protocol, ledger)
        report = finish_report(session, registry)
    else:
        registry.register_project(PROJECT, "Offline research reference")
        registry.put_artifact(PROJECT, "fixtures/source.bin", RAW)
        source_ref = registry.artifact_ref(PROJECT, "fixtures/source.bin")
        source = registry.read_artifact_ref(source_ref, max_bytes=4096)["content"]
        n = len(source)
        if n != EXPECTED or hashlib.sha256(source).hexdigest() != source_ref["sha256"]:
            raise RuntimeError("preregistered source baseline disagrees with raw bytes")
        session = ResearchSession.open(protocol, ledger)
        for stage in STAGES:
            data = stage_payload(stage, source_ref, n)
            payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
            logical_path = "stages/" + stage + ".json"
            registry.put_artifact(PROJECT, logical_path, payload, "application/json")
            ref = registry.artifact_ref(PROJECT, logical_path)
            observation = None
            if stage == "experiment":
                observation = Observation(
                    observation_id="fixture-sample-v1", question=protocol.question,
                    method="canonical immutable blob byte count",
                    measurements={"bytes_count": n}, units={"bytes_count": "byte"},
                    uncertainty={"bytes_count": 0},
                    conditions={"sample_count": "1", "test_kind": "deterministic_software_fixture"},
                    source_refs=protocol.source_refs,
                    observed_at=datetime.now(timezone.utc).isoformat(),
                    artifact_sha256=ref["sha256"],
                )
            receipt = ResearchReceipt(
                stage=stage, artifact_sha256=ref["sha256"],
                source_refs=protocol.source_refs,
                tool_name="merlin_research_reference_demo", tool_version="1",
                evidence_class="observed" if stage == "experiment" else "simulated",
                status="recorded", interpretation="software integrity fixture only",
                observation=observation,
                challenge_scope="one byte append negative control" if stage == "challenge" else "",
                plan_update_ref="registry://stages/update.json" if stage == "update" else "",
            )
            result = session.record(receipt, artifact_ref=ref,
                                    registry=registry, project_id=PROJECT)
            if result["state"] != "passed":
                raise RuntimeError("research stage not recorded: " + stage)
            session = ResearchSession.open(protocol, ledger)
        report = finish_report(session, registry)
    (output / "summary.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = run(args.output.resolve())
    except Exception as exc:
        print("research demo BLOCKED: " + type(exc).__name__ + ": " + str(exc),
              file=sys.stderr)
        return 2
    print(json.dumps({"status": result["status"],
                      "source_commit": result["source_commit"],
                      "blob_checks": result["registry_readback"]["verified_registry_blob_count"],
                      "scientific_claim_established": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
