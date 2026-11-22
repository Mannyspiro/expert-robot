"""Bounded gradient-free weight editing experiment inspired by arXiv:2611.21885.

A *small synthetic linear model* really changes numerical weights on a
detached candidate copy, then tests that copy against frozen questions.
This is NOT editing Merlin's 1.5B GGUF, reproducing the 27B paper, or
automatically promoting a model. No untrusted generated Python is executed.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Mapping

SCHEMA = "merlin-weight-self-edit/1"
PROPOSAL_SCHEMA = "merlin-bounded-rank-one-proposal/1"
MAX_DIM = 64
MAX_RELATIVE_DELTA = 0.6


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _scalar(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("weight coordinates must be finite numbers")
    if abs(value) > 1e4:
        raise ValueError("weight coordinates exceed bounded magnitude")
    return float(value)


def matrix(value):
    if (not isinstance(value, (list, tuple)) or not 1 <= len(value) <= MAX_DIM
            or not isinstance(value[0], (list, tuple))
            or not 1 <= len(value[0]) <= MAX_DIM):
        raise ValueError("bounded rectangular weight tensor required")
    width = len(value[0])
    if any(not isinstance(row, (list, tuple)) or len(row) != width for row in value):
        raise ValueError("weight tensor must be rectangular")
    return [[_scalar(x) for x in row] for row in value]


def apply_projection(weights, direction, fraction):
    """Apply W' = W - alpha*u*(u^T*W); u must be a unit output direction."""
    w = matrix(weights)
    if (not isinstance(direction, (list, tuple))
            or len(direction) != len(w)):
        raise ValueError("direction must match output channels")
    u = [_scalar(x) for x in direction]
    norm = math.sqrt(sum(x * x for x in u))
    if abs(norm - 1.0) > 1e-8:
        raise ValueError("self-edit direction must be unit norm")
    alpha = _scalar(fraction)
    if not 0.0 < alpha <= 0.5:
        raise ValueError("fraction must preserve bounded edit strength")
    projection = [sum(u[i] * w[i][j] for i in range(len(w)))
                  for j in range(len(w[0]))]
    edited = [[w[i][j] - alpha * u[i] * projection[j]
               for j in range(len(w[0]))] for i in range(len(w))]
    baseline_norm = math.sqrt(sum(v * v for row in w for v in row))
    delta_norm = math.sqrt(sum((w[i][j] - edited[i][j]) ** 2
                               for i in range(len(w))
                               for j in range(len(w[0]))))
    if baseline_norm == 0 or delta_norm / baseline_norm > MAX_RELATIVE_DELTA:
        raise ValueError("self-edit violates relative weight change bound")
    return edited


def validate_proposal(proposal, weights):
    """Typed proposal from an untrusted model. No executable source is accepted."""
    w = matrix(weights)
    if type(proposal) is not dict or set(proposal) != {
        "schema", "target", "weight_sha256", "direction", "fraction"
    }:
        raise ValueError("only exact structured self-edit proposals are supported")
    if proposal["schema"] != PROPOSAL_SCHEMA or proposal["target"] != "synthetic.output":
        raise ValueError("target is not an approved editable tensor")
    if proposal["weight_sha256"] != digest(w):
        raise ValueError("stale or foreign weight tensor")
    edited = apply_projection(w, proposal["direction"], proposal["fraction"])
    return edited


def predict(weights, inputs):
    w = matrix(weights)
    if not isinstance(inputs, (list, tuple)) or len(inputs) != len(w[0]):
        raise ValueError("input dimension differs")
    x = [_scalar(z) for z in inputs]
    return [sum(a * b for a, b in zip(row, x)) for row in w]


def _sample(sample, output_count, input_count):
    if (not isinstance(sample, (list, tuple)) or len(sample) != 2
            or not isinstance(sample[0], (list, tuple))
            or not isinstance(sample[1], (list, tuple))
            or len(sample[0]) != input_count or len(sample[1]) != output_count):
        raise ValueError("typed example dimensions differ")
    return tuple(_scalar(v) for v in sample[0]), tuple(_scalar(v) for v in sample[1])


def score(weights, examples):
    w = matrix(weights)
    if not isinstance(examples, (tuple, list)) or not 1 <= len(examples) <= 64:
        raise ValueError("bounded frozen examples required")
    errors = []
    correct = 0
    for example in examples:
        x, target = _sample(example, len(w), len(w[0]))
        answer = predict(w, x)
        error = sum((a - b) ** 2 for a, b in zip(answer, target))
        errors.append(error)
        correct += error <= 1e-10
    return {"correct": correct, "count": len(examples),
            "sum_squared_error": round(sum(errors), 12),
            "per_case_correct": [e <= 1e-10 for e in errors]}


def propose_self_repair(weights, practice):
    """Toy model's own error-based diagnosis; no gradient/autograd/optimizer.

    Restrict the proposal to one measured output axis. Real Merlin needs the
    separate model/editor interface and a trainable checkpoint to propose edits.
    """
    w = matrix(weights)
    if len(w) != len(w[0]):
        raise ValueError("toy diagnosis requires a square output tensor")
    if not isinstance(practice, (tuple, list)) or not 1 <= len(practice) <= 32:
        raise ValueError("bounded diagnosis examples required")
    diagnostics = []
    for example in practice:
        x, expected = _sample(example, len(w), len(w[0]))
        observed = predict(w, x)
        for i, (actual, desired) in enumerate(zip(observed, expected)):
            if abs(actual) < 1e-8 or abs(actual - desired) < 1e-8:
                continue
            fraction = 1.0 - desired / actual
            if 0 < fraction <= 0.5:
                diagnostics.append((abs(actual - desired), i, fraction))
    if not diagnostics:
        raise ValueError("no bounded repair diagnosed on practice cases")
    _, axis, fraction = sorted(diagnostics, reverse=True)[0]
    direction = [float(int(i == axis)) for i in range(len(w))]
    return {"schema": PROPOSAL_SCHEMA, "target": "synthetic.output",
            "weight_sha256": digest(w), "direction": direction,
            "fraction": round(fraction, 10)}


def gate(base, edited, practice, holdout):
    """Immutable holdout gate; improvement and zero regressions are mandatory."""
    baseline = score(base, holdout)
    changed = score(edited, holdout)
    base_train = score(base, practice)
    changed_train = score(edited, practice)
    regressions = sum(a and not b for a, b in zip(
        baseline["per_case_correct"], changed["per_case_correct"]))
    improved = sum(not a and b for a, b in zip(
        baseline["per_case_correct"], changed["per_case_correct"]))
    accepted = (improved > 0 and regressions == 0
                and changed["sum_squared_error"] < baseline["sum_squared_error"]
                and changed_train["sum_squared_error"] <= base_train["sum_squared_error"])
    return {"accepted_as_research_candidate": accepted,
            "baseline_holdout_correct": baseline["correct"],
            "candidate_holdout_correct": changed["correct"],
            "improved": improved, "regressed": regressions,
            "baseline_holdout_sse": baseline["sum_squared_error"],
            "candidate_holdout_sse": changed["sum_squared_error"],
            "production_qualified": False}


def synthetic_repair(output_dir):
    """Real, persistent tiny weight edit; base weights never overwritten."""
    output = Path(output_dir)
    if not output.is_dir() or output.is_symlink():
        raise ValueError("preexisting isolated output directory required")
    base = [[1.0, 0.0], [0.0, 2.0]]
    practice = [([0, 1], [0, 1]), ([1, 0], [1, 0])]
    holdout = [([0.5, 0.5], [0.5, 0.5]),
               ([1, 1], [1, 1]), ([0.25, 0.75], [0.25, 0.75])]
    proposal = propose_self_repair(base, practice)
    candidate = validate_proposal(proposal, base)
    decision = gate(base, candidate, practice, holdout)
    if not decision["accepted_as_research_candidate"]:
        raise RuntimeError("candidate did not pass independent frozen examples")
    report = {"schema": SCHEMA, "model_kind": "synthetic-float-linear-2x2",
              "edit": "gradient_free_rank_one_projection",
              "original_sha256": digest(base),
              "candidate_sha256": digest(candidate),
              "proposal_sha256": digest(proposal),
              "candidate_weights_changed": candidate != base,
              "actual_numeric_weights_rewritten": True,
              "merlin_gguf_weights_changed": False,
              "model_weights_fine_tuned": False,
              "model_editor_was_language_model": False,
              "training_examples_used": len(practice),
              "heldout_examples_used": len(holdout),
              "operator_promotion_required": True,
              **decision}
    if not report["candidate_weights_changed"]:
        raise RuntimeError("proposed change was a no-op")
    artifacts = {
        "synthetic-base-weights.json": canonical(base),
        "synthetic-candidate-weights.json": canonical(candidate),
        "synthetic-edit-proposal.json": canonical(proposal),
        "synthetic-edit-receipt.json": canonical(report),
    }
    for name, payload in artifacts.items():
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    return report


__all__ = ["SCHEMA", "PROPOSAL_SCHEMA", "matrix", "apply_projection",
           "validate_proposal", "propose_self_repair", "predict", "score",
           "gate", "synthetic_repair", "digest"]
