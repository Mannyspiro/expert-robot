#!/usr/bin/env python3
"""Execute one frozen calibration episode; canonical artifacts + fail-closed ledger.

Re-running a finished run returns its receipt. An interrupted running operation
requires reconciliation; it is never silently replayed. No scheduling, downloads,
shell execution, model writes, cloud allocation or production promotion occurs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
import numpy as np
from experimental_self_healing import EvidenceLedger
from merlin.parallax_calibration import (CANDIDATES, MAX_WALL_SECONDS, canonical,
    decimal_attention, evaluate, frozen_protocol, make_fixture, summarize_losses, token_losses)
from merlin.research_window import ResearchWindow
from merlin_loop_coordinator import Loop
from merlin_loop_persistence import checkpoint, restore


def execute(state_dir: Path, output_dir: Path, run_id: str, source_commit: str) -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", run_id) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("bounded run ID and exact source commit required")
    state_dir.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(state_dir / "parallax-calibration.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _execute(state_dir, output_dir, run_id, source_commit)
    finally:
        os.close(descriptor)


def _execute(state_dir, output_dir, run_id, source_commit):
    window = ResearchWindow(state_dir, project_id="parallax-rsi", project_title="Parallax arithmetic and 3D research")
    registry = window.registry
    ledger = EvidenceLedger(state_dir / "parallax-evidence.jsonl")
    loops = restore(ledger, plan_id=run_id)
    prefix = "research/parallax/" + run_id + "/"
    output_dir.mkdir(parents=True, exist_ok=True)

    def read(name):
        ref = registry.artifact_ref(window.project_id, prefix + name, version=1)
        if registry.artifact_ref(window.project_id, prefix + name)["version"] != 1:
            raise RuntimeError("frozen artifact superseded; episode requires review")
        content = registry.read_artifact_ref(ref, max_bytes=8 * 1024 * 1024)["content"]
        loop = loops.loops.get(name.removesuffix(".json"))
        if loop is not None and loop.state == "passed" and "sha256:" + sha256(content).hexdigest() not in loop.evidence:
            raise RuntimeError("artifact does not match checkpoint evidence")
        return json.loads(content)

    def put(name, record):
        if registry.artifact_history(window.project_id, prefix + name):
            raise RuntimeError("frozen artifact already exists; reconcile partial execution")
        payload = canonical(record)
        registry.put_artifact(window.project_id, prefix + name, payload, "application/json")
        (output_dir / name).write_bytes(payload + b"\n")
        return "sha256:" + sha256(payload).hexdigest()

    protocol = frozen_protocol(source_commit)
    protocol["runner_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()

    def finalize(receipt):
        """Idempotent export/HUD recovery; never opens or evaluates test data."""
        receipt_hash = sha256(canonical(receipt)).hexdigest()
        if registry.artifact_history(window.project_id, prefix + "receipt.json"):
            if read("receipt.json") != receipt:
                raise RuntimeError("export does not match pinned test receipt")
        else:
            put("receipt.json", receipt)
        (output_dir / "receipt.json").write_bytes(canonical(receipt) + b"\n")
        if registry.artifact_history(window.project_id, prefix + "finalization.json"):
            if read("finalization.json")["test_receipt_sha256"] != receipt_hash:
                raise RuntimeError("finalization evidence changed")
            return receipt
        window.register_artifact(output_dir / "receipt.json", allowed_roots=[output_dir], run_id=run_id,
            logical_path=prefix + "display/receipt.json", title="Synthetic Parallax calibration receipt", display_kind="data",
            caption="Measured arithmetic fixture; no trained-language-model or hardware qualification", evidence_class="observed")
        window.emit({"source": "runtime", "kind": "task.completed", "run_id": run_id,
            "event_id": "parallax-complete-" + receipt_hash,
            "timestamp": datetime.fromtimestamp(receipt["budget_checkpoint"]["last_seen_unix_seconds"], timezone.utc).isoformat(),
            "payload": {"summary": "Bounded calibration completed; no production promotion", **receipt["selection"]}})
        put("finalization.json", {"test_receipt_sha256": receipt_hash, "status": "exported_and_announced"})
        return receipt
    if loops.loops:
        initial = read("initialization.json")
        for name in ("protocol.json", "clock.json"):
            if sha256(canonical(read(name))).hexdigest() != initial[name + "_sha256"]:
                raise RuntimeError("initialization artifact changed")
        if read("protocol.json") != json.loads(canonical(protocol)):
            raise ValueError("source/protocol changed; frozen episode cannot be reused")
        if any(x.state == "blocked" for x in loops.loops.values()):
            raise RuntimeError("interrupted episode requires review; no replay or renewed budget")
        for name, loop in loops.loops.items():
            if loop.state == "passed":
                read(name + ".json")
        if loops.loops["test"].state == "passed":
            return finalize(read("test.json"))
    else:
        protocol_hash = put("protocol.json", protocol).removeprefix("sha256:")
        now = time.time()
        clock_hash = put("clock.json", {"started_unix_seconds": now, "last_seen_unix_seconds": now, "consumed_seconds": 0}).removeprefix("sha256:")
        loops.add(Loop("initialization", "research"))
        loops.start("initialization")
        evidence = put("initialization.json", {"protocol.json_sha256": protocol_hash, "clock.json_sha256": clock_hash})
        loops.finish("initialization", passed=True, evidence=evidence)
        loops.add(Loop("fixtures", "research", dependencies=("initialization",)))
        for candidate in CANDIDATES:
            loops.add(Loop("evaluate-" + candidate.name, "research", dependencies=("fixtures",)))
        loops.add(Loop("selection", "research", dependencies=tuple("evaluate-" + c.name for c in CANDIDATES)))
        loops.add(Loop("test", "research", dependencies=("selection",)))
        checkpoint(loops, ledger, plan_id=run_id)
        window.emit({"source": "runtime", "kind": "task.started", "run_id": run_id,
                     "payload": {"summary": "Frozen eight-candidate synthetic Parallax calibration", "question": "Does centered unequal-weight covariance preserve numerical fidelity?"}})
    clock = read("clock.json")
    for name, loop in loops.loops.items():
        if loop.state == "passed":
            previous = read(name + ".json").get("budget_checkpoint", {})
            for field in ("last_seen_unix_seconds", "consumed_seconds"):
                clock[field] = max(clock[field], previous.get(field, 0))
    def stop(reason, error_type=TimeoutError):
        for name, loop in loops.loops.items():
            if loop.state in {"pending", "failed"}:
                loops.block(name, reason)
        checkpoint(loops, ledger, plan_id=run_id)
        raise error_type(reason)
    now = time.time()
    if now < clock["last_seen_unix_seconds"]:
        stop("wall clock moved backward; episode requires review", RuntimeError)
    remaining = MAX_WALL_SECONDS - max(now - clock["started_unix_seconds"], clock["consumed_seconds"])
    if remaining <= 0:
        stop("persisted episode wall budget exhausted; no renewal")
    deadline = time.monotonic() + remaining

    def operation(name, callback):
        if loops.loops[name].state == "passed":
            return read(name + ".json")
        if time.monotonic() >= deadline:
            stop("cycle wall budget exhausted")
        loops.start(name)
        checkpoint(loops, ledger, plan_id=run_id)
        result = json.loads(canonical(callback()))
        if time.monotonic() >= deadline:
            raise TimeoutError("operation exhausted cycle wall budget; checkpoint requires review")
        now = time.time()
        if now < clock["last_seen_unix_seconds"]:
            raise RuntimeError("wall clock moved backward; episode requires review")
        clock["last_seen_unix_seconds"] = now
        clock["consumed_seconds"] = max(clock["consumed_seconds"], MAX_WALL_SECONDS - (deadline - time.monotonic()))
        result["budget_checkpoint"] = dict(clock)
        evidence = put(name + ".json", result)
        loops.finish(name, passed=True, evidence=evidence)
        checkpoint(loops, ledger, plan_id=run_id)
        window.emit({"source": "simulation", "kind": "experiment.completed", "run_id": run_id,
            "payload": {"summary": name + " completed", "candidate": result.get("candidate", {}),
                        "mean_nll": result.get("mean_nll"), "equivalence_gate_passed": result.get("equivalence_gate_passed")},
            "evidence_refs": [evidence]})
        return result

    def prepare():
        # Create fixed data and commit content hashes before candidate scoring.
        # Test labels are sealed here, not scored or used for model/candidate selection.
        hashes = {}
        for split in ("development", "validation", "test"):
            fixture = make_fixture(split)
            np.savez_compressed(output_dir / (split + ".npz"), **{k: v for k, v in fixture.items() if isinstance(v, np.ndarray)})
            hashes[split] = fixture["sha256"]
        dev = make_fixture("development")
        indices = (0, 1, 2, 15, 31, 47, 63, 79, 95)
        oracle_error = max(float(np.max(np.abs(decimal_attention(dev["p"][i], dev["a"][i], dev["values"][i]) - dev["reference"][i]))) for i in indices)
        if oracle_error > 1e-11:
            raise ValueError("independent Decimal oracle disagrees with FP64 reference")
        return {"split_content_sha256": hashes, "development_oracle_traces": indices,
                "oracle_precision_decimal_digits": 60, "reference_max_abs_error_vs_decimal": oracle_error,
                "test_labels_used_for_selection": False}

    fixtures = operation("fixtures", prepare)
    validation = make_fixture("validation")
    if validation["sha256"] != fixtures["split_content_sha256"]["validation"]:
        raise ValueError("validation content changed")
    rows = []
    for candidate in CANDIDATES:
        def candidate_run(candidate=candidate):
            try:
                return evaluate(validation, candidate, deadline=deadline)
            except (FloatingPointError, ValueError, OverflowError) as error:
                return {"candidate": {"name": candidate.name, "role": candidate.role},
                        "equivalence_gate_passed": False, "rejected_reason": str(error)}
        rows.append(operation("evaluate-" + candidate.name, candidate_run))

    def select():
        eligible = [r for r in rows if r["equivalence_gate_passed"] and r["candidate"]["role"] != "control"]
        winner = min(eligible, key=lambda r: (r["mean_nll"], r["candidate"]["name"])) if eligible else None
        return {"selected_candidate": winner["candidate"]["name"] if winner else "fp64_reference",
                "selected_on": "validation only", "eligible_count": len(eligible),
                "test_access_count_before_selection": 0, "production_promotion": False,
                "ranking_scope": "fixed synthetic calibration, eight frozen arithmetic candidates"}
    selection = operation("selection", select)

    def test_once():
        test = make_fixture("test")
        if test["sha256"] != fixtures["split_content_sha256"]["test"]:
            raise ValueError("sealed test content changed")
        winner = next((c for c in CANDIDATES if c.name == selection["selected_candidate"]), None)
        baseline = evaluate(test, CANDIDATES[0], deadline=deadline)
        reference_losses = token_losses(test["reference"] @ test["readout"], test["targets"])
        selected = (baseline if winner == CANDIDATES[0] else evaluate(test, winner, deadline=deadline)) if winner else {"candidate": {"name": "fp64_reference"}, **summarize_losses(reference_losses), "per_token_losses": reference_losses.tolist(), "equivalence_gate_passed": True}
        differences = np.asarray(selected["per_token_losses"]) - np.asarray(baseline["per_token_losses"])
        mean_delta = float(differences.mean())
        half_width = 1.96 * float(differences.std(ddof=1)) / math_sqrt(len(differences))
        receipt = {"schema": "merlin-parallax-calibration-receipt/1", "run_id": run_id,
            "scope": protocol["scope"], "protocol_sha256": sha256(canonical(protocol)).hexdigest(),
            "fixtures": fixtures, "validation": rows, "selection": selection,
            "test": {"episode_count": 1, "selected": selected, "baseline": baseline,
                     "reference": summarize_losses(reference_losses),
                     "paired_nll_delta_selected_minus_baseline": mean_delta,
                     "approximate_95pct_paired_normal_interval": [mean_delta - half_width, mean_delta + half_width],
                     "interval_scope": "independent synthetic traces; no generalization to natural language"},
            "elapsed_host_seconds": time.time() - read("clock.json")["started_unix_seconds"],
            "trained_language_model_evaluated": False, "physical_hardware_validated": False,
            "production_promotion": False, "next_target": "Pinned 0.6B checkpoint with fixed licensed natural-language held-out corpus and tokenizer; unavailable in this episode"}
        return receipt
    receipt = operation("test", test_once)
    return finalize(receipt)


def math_sqrt(value):
    return value ** 0.5


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    result = execute(args.state_dir, args.output_dir, args.run_id, args.source_commit)
    print(json.dumps({"run_id": result["run_id"], "selection": result["selection"],
                      "test_reference": result["test"]["reference"], "trained_language_model_evaluated": False}, indent=2))
