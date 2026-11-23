#!/usr/bin/env python3
"""Explicit, restartable Merlin simulated-computation research episode.

One invocation advances at most --steps tasks and checkpoints after every
attempt. A host scheduler may re-invoke it if *separately authorized*. This
script does not run in the background or touch models, browsers, cloud, code
branches, hardware or private vaults.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from merlin.bounded_research_loop import Question, ResearchSubloops
from merlin.simulated_parallax_models import run_reference_experiment

_SCHEMA = "merlin-simulated-research-episode/1"
CHILDREN = (
    {"task_id": "recurrence_identity", "hypothesis": "Recurrence reproduces weighted history",
     "baseline": "Direct weighted-history evaluation", "falsifier": "Error exceeds declared tolerance",
     "independent_check": "Matched output comparison against direct reference"},
    {"task_id": "simulated_channel", "hypothesis": "Virtual two-channel method has measurable host cost",
     "baseline": "Direct history and single recurrence", "falsifier": "Missing or nonfinite measurement",
     "independent_check": "Compare elapsed time and output error; no architecture gain implied"},
)


def experiment(question):
    if question.task_id == "root":
        return {"observation": {"kind": "research_protocol",
                                "source": "local synthetic proposal",
                                "hypothesis_count": len(CHILDREN)},
                "children": list(CHILDREN)}
    if question.task_id in ("recurrence_identity", "simulated_channel"):
        report = run_reference_experiment(n=64, seed=23)
        return {"observation": {
            "kind": "synthetic_simulated_recurrence",
            "trial": question.task_id,
            "reference": "direct weighted history",
            "simulation": report,
        }, "children": []}
    raise ValueError("unrecognized research task; no dynamic source execution")


def verify(question, observation):
    if question.task_id == "root":
        accepted = observation.get("kind") == "research_protocol" and observation.get("hypothesis_count") == 2
        return {"accepted": accepted, "checker": "static_protocol_identity",
                "reason": "Only the declared finite subtask catalogue was admitted"}
    report = observation.get("simulation", {})
    variants = report.get("variants", {})
    required = {"quadratic_history", "scalar_recurrence", "local_window", "simulated_two_channel"}
    accepted = (report.get("schema") == "merlin-simulated-parallax-memory-benchmark/1"
                and set(variants) == required
                and variants["scalar_recurrence"]["max_abs_error_vs_reference"] <= 1e-12
                and report.get("trained_model_evaluated") is False
                and report.get("production_qualified") is False)
    return {"accepted": bool(accepted), "checker": "direct_reference_and_structural_checks",
            "reason": "Toy numerical agreement checked; no formal, physical or model gain verified"}


def save_atomic(path: Path, state: ResearchSubloops):
    path = Path(path)
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise ValueError("checkpoint must be a regular nonsymlink file")
    if path.parent.is_symlink():
        raise ValueError("checkpoint parent symlink refused")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(state.snapshot(), sort_keys=True, indent=2).encode()
    if len(raw) > 524288:
        raise ValueError("checkpoint exceeds 512 KiB")
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".merlin-research-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load_or_initialize(path: Path) -> ResearchSubloops:
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 524288:
            raise ValueError("invalid research state file")
        def reject_duplicates(pairs):
            result = {}
            for key, val in pairs:
                if key in result:
                    raise ValueError("duplicate research checkpoint JSON key")
                result[key] = val
            return result
        saved = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
        return ResearchSubloops.restore(saved)
    loop = ResearchSubloops(max_steps=3, max_tasks=3, max_depth=1)
    loop.add(Question("root", "Two bounded simulated research questions",
                      "Single reference computation", "Failed integrity condition",
                      "Independent source identity and numerical check"))
    return loop


def run_episode(path: Path, steps: int) -> dict:
    if type(steps) is not int or not 1 <= steps <= 3:
        raise ValueError("1..3 steps per explicit episode invocation")
    loop = load_or_initialize(path)
    receipts = []
    for _ in range(steps):
        receipt = loop.step(experiment, verify)
        if receipt is None:
            break
        receipts.append(receipt)
        save_atomic(path, loop)
    if not receipts and not path.exists():
        save_atomic(path, loop)
    return {"schema": _SCHEMA, "checkpoint": str(path), "summary": loop.summary(),
            "latest_receipts": receipts, "source_class": "synthetic_host_simulation",
            "model_calls": 0, "background_worker_running": False,
            "proof_or_model_gain_established": False, "production_qualified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=1)
    args = parser.parse_args()
    report = run_episode(args.checkpoint, args.steps)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if all(x["status"] == "checked" for x in report["latest_receipts"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
