#!/usr/bin/env python3
"""Turn one already-captured public HTTPS receipt into a durable Merlin research cycle.

No fetched Python source is imported or executed. A tiny exact-rational identity
is checked against independent integer arithmetic, not used to claim general
scientific truth or model performance. On restart only saved Artifacts and
ResearchSession checkpoints are reread; no public network action is repeated.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "scripts"))

from experimental_self_healing import EvidenceLedger
from merlin.project_registry import MerlinRegistry
from merlin.scientific_loop import Observation, Prediction
from merlin_research_session import ResearchFrame, ResearchReceipt, ResearchSession, STAGES
from merlin_public_https_acceptance import LIMIT, URL

PROJECT = "merlin-public-source-research-v1"
CYCLE = "cpython-fraction-source-and-reference-v1"
SOURCE_PATH = "sources/cpython-fractions-v3.12.1.py.txt"
RECEIPT_PATH = "sources/public-https-receipt.json"


def source_commit():
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, timeout=10, check=False)
    sha = process.stdout.strip()
    if process.returncode or not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise RuntimeError("complete pinned Git checkout required")
    if os.environ.get("MERLIN_EXPECTED_SHA", sha) != sha:
        raise RuntimeError("live research input differs from requested exact commit")
    return sha


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def source_receipt(source_dir: Path, sha: str):
    raw_path = source_dir / "public-source-raw.py.txt"
    receipt_path = source_dir / "receipt.json"
    for path in (raw_path, receipt_path):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > LIMIT:
            raise ValueError("missing, symbolic or oversized live source artifact")
    source = raw_path.read_bytes()
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    if (not isinstance(receipt, dict)
            or receipt.get("schema") != "merlin-public-https-source-acceptance/1"
            or receipt.get("source_commit") != sha
            or receipt.get("source_url") != URL
            or receipt.get("final_url") != URL
            or receipt.get("retrieval_kind") != "https_http"
            or receipt.get("status") != 200
            or receipt.get("source_observed") is not True
            or receipt.get("private_context_included") is not False
            or receipt.get("promotion_authority") is not False
            or receipt.get("raw_path") != "public-source-raw.py.txt"
            or receipt.get("raw_bytes") != len(source)
            or receipt.get("raw_sha256") != hashlib.sha256(source).hexdigest()
            or not 200 <= len(source) <= LIMIT
            or b"class Fraction" not in source):
        raise ValueError("live source receipt has unsupported identity or data")
    try:
        date = datetime.fromisoformat(receipt["observed_at_utc"].replace("Z", "+00:00"))
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise ValueError("source receipt requires recorded UTC observation") from exc
    if date.tzinfo is None:
        raise ValueError("source receipt observation time must include timezone")
    return source, receipt_bytes, receipt


def store_once(registry, logical_path, content, media_type):
    history = registry.artifact_history(PROJECT, logical_path)
    if history:
        if len(history) != 1:
            raise ValueError("unexpected extra versions of canonical research input")
        ref = registry.artifact_ref(PROJECT, logical_path, version=1)
        read = registry.read_artifact_ref(ref, max_bytes=2 * 1024 * 1024)["content"]
        if read != content:
            raise ValueError("durable evidence path already bound to different content")
        return ref
    registry.put_artifact(PROJECT, logical_path, content, media_type)
    return registry.artifact_ref(PROJECT, logical_path, version=1)


def frame_for(sha, source_ref):
    return ResearchFrame(
        cycle_id=CYCLE, plan_id="MERLIN-PRODUCTION-MASTER-20261117", plan_version=6,
        source_commit=sha,
        question="Does a fixed exact-rational sum satisfy an independent integer identity?",
        metric="scaled_residual", unit="integer",
        baseline_ref="reference:2*(1*6+1*3)-(3*6)=0",
        hypotheses=("exact-rational identity holds", "identity has a nonzero residual"),
        predictions=(Prediction("scaled_residual", 0, 0, "integer"),),
        falsifier="The measured scaled integer residual differs from zero",
        stopping_rule="One fixed pair of rational inputs and one counterexample; no retries",
        acceptance_rule="Runtime Fraction output and separate integer algebra both have residual zero",
        source_refs=(URL, "artifact-sha256:" + source_ref["sha256"]),
        unknowns=("This single coding example does not establish general model or math ability",),
    )


def arithmetic():
    measured = Fraction(1, 3) + Fraction(1, 6)
    residual = 2 * measured.numerator - measured.denominator
    # Independent simple integer formula, not a second Fraction invocation.
    reference = 2 * (1 * 6 + 1 * 3) - (3 * 6)
    counterexample = Fraction(1, 3) + Fraction(1, 5)
    counter_residual = 2 * counterexample.numerator - counterexample.denominator
    if reference != 0 or residual != reference or counter_residual == 0:
        raise RuntimeError("reference or negative control fails")
    return {"runtime_result": str(measured), "scaled_residual": residual,
            "independent_reference_residual": reference,
            "counterexample_result": str(counterexample),
            "counterexample_residual": counter_residual,
            "counterexample_rejects_target": True}


def stage_document(stage, source_ref, original_receipt_ref, result):
    return {"schema": "merlin-public-source-scientific-stage/1",
            "stage": stage, "source_artifact_ref": source_ref,
            "public_https_receipt_ref": original_receipt_ref,
            "competing_explanations":
                ["correct rational summation", "nonzero residual"]
                if stage == "explain" else None,
            "prediction":
                {"metric": "scaled_residual", "expected": 0,
                 "unit": "integer", "tolerance": 0}
                if stage == "predict" else None,
            "calculation": result if stage in ("experiment", "challenge") else None,
            "plan_update":
                {"parent_plan": "MERLIN-PRODUCTION-MASTER-20261117", "version": 6,
                 "decision": "local source-cited exact arithmetic fixture only",
                 "next_gate": "held-out real model/independent real-world research"}
                if stage == "update" else None,
            "scientific_claim_established": False,
            "model_inference_qualified": False,
            "promotion_authority": False}


def run(source_dir: Path, output: Path):
    sha = source_commit()
    raw, receipt_bytes, receipt = source_receipt(source_dir, sha)
    output.mkdir(parents=True, exist_ok=True)
    success_path = output / "summary.json"
    if success_path.exists():
        success_path.unlink()
    registry = MerlinRegistry(output / "registry")
    registry.register_project(PROJECT, "Public source and independent arithmetic fixture")
    source_ref = store_once(registry, SOURCE_PATH, raw, "text/plain")
    receipt_ref = store_once(registry, RECEIPT_PATH, receipt_bytes, "application/json")
    if source_ref["sha256"] != receipt["raw_sha256"]:
        raise ValueError("canonical registry source bytes differ from public HTTPS receipt")
    frame = frame_for(sha, source_ref)
    ledger = EvidenceLedger(output / "research-ledger.jsonl")
    session = ResearchSession.open(frame, ledger)
    result = arithmetic()
    if session.next_stage() is not None:
        # Restart of an interrupted stage never silently replays the calculation.
        if any(item["state"] != "pending" for item in session.scheduler.snapshot().values()):
            raise RuntimeError("research session is partially complete; manual evidence review required")
        for stage in STAGES:
            doc = canonical(stage_document(stage, source_ref, receipt_ref, result))
            artifact_ref = store_once(registry, "stages/" + stage + ".json", doc,
                                      "application/json")
            observation = None
            if stage == "experiment":
                observation = Observation(
                    observation_id="fraction-runtime-fixture", question=frame.question,
                    method="stdlib Fraction vs independent integer formula",
                    measurements={"scaled_residual": result["scaled_residual"]},
                    units={"scaled_residual": "integer"},
                    uncertainty={"scaled_residual": 0},
                    conditions={"source_kind": "public_HTTPS_technical_reference",
                                "sample_count": "1", "purpose": "bounded_software_fixture"},
                    source_refs=frame.source_refs,
                    observed_at=receipt["observed_at_utc"],
                    artifact_sha256=artifact_ref["sha256"])
            record = ResearchReceipt(
                stage=stage, artifact_sha256=artifact_ref["sha256"],
                source_refs=frame.source_refs,
                tool_name="merlin_cited_research_cycle", tool_version="1",
                evidence_class="observed" if stage == "experiment" else "simulated",
                status="recorded", interpretation="single source-cited arithmetic reference, not discovery",
                observation=observation,
                challenge_scope="nonzero residual for 1/3+1/5 against 1/2"
                if stage == "challenge" else "",
                plan_update_ref="registry://stages/update.json" if stage == "update" else "")
            session.record(record, artifact_ref=artifact_ref,
                           registry=registry, project_id=PROJECT)
            session = ResearchSession.open(frame, ledger)
    report = session.verify_registry_bindings(registry, project_id=PROJECT)
    if not (session.status()["procedural_record_complete"]
            and report["all_six_stages_bound"]
            and result["scaled_residual"] == 0 and result["counterexample_rejects_target"]):
        raise RuntimeError("research/counterexample acceptance incomplete")
    success = {
        "schema": "merlin-source-cited-research-result/1",
        "source_commit": sha,
        "source_url": URL,
        "source_blob_ref": source_ref,
        "source_receipt_ref": receipt_ref,
        "cycle_id": frame.cycle_id,
        "source_citation_available": True,
        "independent_exact_arithmetic_reference": True,
        "exact_artifact_readback": report,
        "public_source_bytes": len(raw),
        "public_source_sha256": receipt["raw_sha256"],
        "research_stages": session.status()["stages"],
        "negative_control_rejected": True,
        "scientific_claim_established": False,
        "model_inference_performed": False,
        "browser_rendering_performed": False,
        "generalization_qualified": False,
        "promotion_authority": False,
        "external_spend_usd": 0,
    }
    success_path.write_bytes(canonical(success))
    return success


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = run(args.source_dir.resolve(), args.output.resolve())
    except Exception as exc:
        print("source-cited research BLOCKED: " + type(exc).__name__
              + ": " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"status": "source_cited_research_fixture_passed",
                      "source_sha256": result["public_source_sha256"],
                      "stages": len(result["research_stages"]),
                      "scientific_truth_claim": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
