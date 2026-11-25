"""Bounded arithmetic calibration of Parallax's covariance attention core.

This is a synthetic next-token trace fixture, NOT a trained language model or a
GPU/chip emulator. Inputs at the core boundary are (positive weights, r.k, v).
The fixed random readout and teacher-sampled token IDs only make numerical
distortion observable through NLL. No private text, downloads, training or
production promotion is performed. See the frozen protocol for claim limits.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
import time

import numpy as np


@dataclass(frozen=True)
class Candidate:
    name: str
    dtype: str
    method: str
    block_rows: int = 0
    role: str = "candidate"


CANDIDATES = (
    Candidate("raw_fp32", "float32", "raw", role="baseline"),
    Candidate("centered_fp32", "float32", "centered"),
    Candidate("block16_fp32", "float32", "block", 16),
    Candidate("block32_fp32", "float32", "block", 32),
    Candidate("raw_fp16", "float16", "raw"),
    Candidate("centered_fp16", "float16", "centered"),
    Candidate("block16_fp16", "float16", "block", 16),
    Candidate("centered_fp64", "float64", "centered", role="control"),
)
SPLITS = {"development": (17001, 96), "validation": (27001, 384), "test": (37001, 384)}
CONTEXT, DIMENSION, VOCABULARY = 64, 8, 32
OFFSETS = (0.0, 64.0, 1024.0)
MAX_ABS_ERROR = 1e-4
MAX_WALL_SECONDS = 300
MAX_WORKSPACE_BYTES = 32 * 1024 * 1024
SCHEMA = "merlin-parallax-calibration/1"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest_arrays(*arrays: np.ndarray) -> str:
    h = sha256()
    for array in arrays:
        value = np.ascontiguousarray(array)
        h.update(canonical({"shape": value.shape, "dtype": value.dtype.str}))
        h.update(value.tobytes())
    return h.hexdigest()


def _inputs(p, a, values, dtype):
    p, a, values = (np.asarray(x, dtype=dtype) for x in (p, a, values))
    if (p.ndim != 1 or a.shape != p.shape or values.ndim != 2
            or values.shape[0] != len(p) or not 1 <= len(p) <= 4096
            or not 1 <= values.shape[1] <= 128):
        raise ValueError("bounded one-head trace dimensions required")
    if not all(np.isfinite(x).all() for x in (p, a, values)) or np.any(p < 0):
        raise ValueError("finite inputs and nonnegative rounded weights required")
    mass = p.sum(dtype=dtype)
    if not np.isfinite(mass) or mass <= 0:
        raise ValueError("positive finite weight mass required")
    return p, a, values, mass


def attention(p, a, values, candidate: Candidate) -> np.ndarray:
    """Cast before centering: no hidden high-precision input preconditioning.

    Block mode computes and merges normalized covariances. Global residual
    coordinates keep a large, mathematically irrelevant score offset out of the
    merge. This does not recover detail already lost to input quantization.
    """
    if candidate not in CANDIDATES:
        raise ValueError("candidate must belong to the frozen catalogue")
    dtype = np.dtype(candidate.dtype)
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        p, a, values, total_mass = _inputs(p, a, values, dtype)
        def mean(weights, x):
            return np.sum(weights[:, None] * x, axis=0, dtype=dtype)
        if candidate.method == "raw":
            mv = mean(p, values) / total_mass
            ma = np.sum(p * a, dtype=dtype) / total_mass
            result = mv * (dtype.type(1) + ma) - mean(p, values * a[:, None]) / total_mass
        else:
            origin_v, origin_a = values[0].copy(), a[0]
            dv, da = values - origin_v, a - origin_a
            if candidate.method == "centered":
                mv = mean(p, dv) / total_mass
                ma = np.sum(p * da, dtype=dtype) / total_mass
                cov = mean(p, dv * da[:, None]) / total_mass - mv * ma
            else:
                mass = dtype.type(0)
                mv, ma, cov = np.zeros(values.shape[1], dtype=dtype), dtype.type(0), np.zeros(values.shape[1], dtype=dtype)
                for start in range(0, len(p), candidate.block_rows):
                    w = p[start:start + candidate.block_rows]
                    bv, ba = dv[start:start + candidate.block_rows], da[start:start + candidate.block_rows]
                    bm = w.sum(dtype=dtype)
                    if bm == 0:  # All rounded weights can underflow in a block.
                        continue
                    bmv, bma = mean(w, bv) / bm, np.sum(w * ba, dtype=dtype) / bm
                    bcov = mean(w, bv * ba[:, None]) / bm - bmv * bma
                    total = mass + bm
                    u, v = mass / total, bm / total
                    cov = u * cov + v * bcov + u * v * (mv - bmv) * (ma - bma)
                    mv, ma, mass = u * mv + v * bmv, u * ma + v * bma, total
            result = origin_v + mv - cov
    if not np.isfinite(result).all():
        raise ValueError("nonfinite attention output")
    return result.astype(np.float64)


def reference_attention(p, a, values) -> np.ndarray:
    """Independent FP64 two-pass central-product formula; not candidate code."""
    p, a, values, mass = _inputs(p, a, values, np.dtype("float64"))
    p = p / mass
    mv = np.einsum("i,ij->j", p, values)
    ma = np.dot(p, a)
    return mv - np.einsum("i,ij,i->j", p, values - mv, a - ma)


def decimal_attention(p, a, values) -> np.ndarray:
    """60-digit oracle for exact real arithmetic on the supplied binary inputs."""
    with localcontext() as ctx:
        ctx.prec = 60
        w = [Decimal.from_float(float(x)) for x in p]
        mass = sum(w)
        w = [x / mass for x in w]
        aa = [Decimal.from_float(float(x)) for x in a]
        ma = sum(x * y for x, y in zip(w, aa))
        result = []
        for column in np.asarray(values).T:
            vv = [Decimal.from_float(float(x)) for x in column]
            mv = sum(x * y for x, y in zip(w, vv))
            cov = sum(x * (v - mv) * (a - ma) for x, v, a in zip(w, vv, aa))
            result.append(float(mv - cov))
        return np.array(result)


def token_losses(logits, targets, mask=None) -> np.ndarray:
    """Natural-log NLL with explicit masking; aggregation is by scored token."""
    logits, targets = np.asarray(logits, dtype=np.float64), np.asarray(targets)
    if logits.ndim != 2 or targets.shape != (len(logits),) or not np.issubdtype(targets.dtype, np.integer):
        raise ValueError("logits [tokens,vocab] and integer targets required")
    if logits.shape[1] < 2 or not np.isfinite(logits).all():
        raise ValueError("finite vocabulary logits required")
    mask = np.ones(len(logits), dtype=bool) if mask is None else np.asarray(mask)
    if mask.dtype != np.dtype(bool) or mask.shape != targets.shape or not mask.any():
        raise ValueError("nonempty Boolean score mask required")
    targets, logits = targets[mask], logits[mask]
    if np.any(targets < 0) or np.any(targets >= logits.shape[1]):
        raise ValueError("scored target outside vocabulary")
    peak = logits.max(axis=1)
    return peak + np.log(np.exp(logits - peak[:, None]).sum(axis=1)) - logits[np.arange(len(targets)), targets]


def summarize_losses(losses) -> dict:
    losses = np.asarray(losses, dtype=np.float64)
    if losses.ndim != 1 or not len(losses) or not np.isfinite(losses).all():
        raise ValueError("finite nonempty per-token losses required")
    nll = float(losses.mean())
    return {"tokens": len(losses), "nll_sum": float(losses.sum()), "mean_nll": nll,
            "perplexity": math.exp(nll)}


def make_fixture(split: str) -> dict:
    if split not in SPLITS:
        raise ValueError("unknown fixed split")
    seed, count = SPLITS[split]
    rng = np.random.default_rng(seed)
    k = rng.normal(size=(count, CONTEXT, DIMENSION))
    q, r = rng.normal(size=(2, count, DIMENSION))
    scores = np.einsum("nd,nld->nl", q, k) / math.sqrt(DIMENSION)
    p = np.exp(scores - scores.max(axis=1, keepdims=True))
    p /= p.sum(axis=1, keepdims=True)
    offsets = np.resize(np.array(OFFSETS), count)
    a = np.einsum("nd,nld->nl", r, k) + offsets[:, None]
    values = rng.normal(scale=0.25, size=(count, CONTEXT, DIMENSION))
    readout = np.random.default_rng(47001).normal(scale=0.9, size=(DIMENSION, VOCABULARY))
    reference = np.array([reference_attention(*x) for x in zip(p, a, values)])
    logits = reference @ readout
    probs = np.exp(logits - logits.max(axis=1, keepdims=True))
    probs /= probs.sum(axis=1, keepdims=True)
    labels_rng = np.random.default_rng(seed + 100000)
    targets = np.array([labels_rng.choice(VOCABULARY, p=row) for row in probs], dtype=np.int64)
    return {"p": p, "a": a, "values": values, "readout": readout, "targets": targets,
            "reference": reference, "offsets": offsets,
            "sha256": digest_arrays(p, a, values, readout, targets)}


def workspace_bound(candidate: Candidate) -> int:
    # Conservative explicit array payload for a single trace, not allocator/RSS.
    return int((12 * CONTEXT * DIMENSION + 12 * CONTEXT + 32 * DIMENSION) * np.dtype(candidate.dtype).itemsize)


def evaluate(fixture: dict, candidate: Candidate, *, deadline: float) -> dict:
    started = time.monotonic()
    if workspace_bound(candidate) > MAX_WORKSPACE_BYTES:
        raise ValueError("candidate exceeds declared workspace bound")
    outputs, rounded_references = [], []
    for inputs in zip(fixture["p"], fixture["a"], fixture["values"]):
        if time.monotonic() >= deadline:
            raise TimeoutError("cycle wall budget exhausted")
        outputs.append(attention(*inputs, candidate))
        rounded_references.append(reference_attention(*(np.asarray(x, dtype=candidate.dtype).astype(np.float64) for x in inputs)))
    outputs = np.array(outputs)
    rounded_references = np.array(rounded_references)
    error = np.abs(outputs - fixture["reference"])
    logits = outputs @ fixture["readout"]  # Same FP64 readout for every core.
    reference_logits = fixture["reference"] @ fixture["readout"]
    logit_error = np.abs(logits - reference_logits)
    losses = token_losses(logits, fixture["targets"])
    reference_losses = token_losses(reference_logits, fixture["targets"])
    def log_softmax(x):
        centered = x - x.max(axis=1, keepdims=True)
        return centered - np.log(np.exp(centered).sum(axis=1, keepdims=True))
    teacher_log_probs, candidate_log_probs = log_softmax(reference_logits), log_softmax(logits)
    teacher_probs = np.exp(teacher_log_probs)
    expected_ce = -np.sum(teacher_probs * candidate_log_probs, axis=1)
    teacher_kl = np.sum(teacher_probs * (teacher_log_probs - candidate_log_probs), axis=1)
    row = {"candidate": asdict(candidate), **summarize_losses(losses),
           "max_abs_output_error": float(error.max()), "rmse": float(np.sqrt(np.mean(error ** 2))),
           "max_abs_arithmetic_error_vs_rounded_inputs": float(np.max(np.abs(outputs - rounded_references))),
           "max_abs_input_quantization_error": float(np.max(np.abs(rounded_references - fixture["reference"]))),
           "max_abs_logit_error": float(logit_error.max()),
           "max_abs_token_nll_delta": float(np.max(np.abs(losses - reference_losses))),
           "nll_delta_bound_twice_max_logit_error": float(2 * logit_error.max()),
           "mean_teacher_kl": float(teacher_kl.mean()),
           "mean_teacher_expected_cross_entropy": float(expected_ce.mean()),
           "equivalence_gate_passed": bool(error.max() <= MAX_ABS_ERROR),
           "workspace_payload_upper_bound_bytes": workspace_bound(candidate),
           "measured_evaluation_host_seconds": time.monotonic() - started,
           "timing_scope": "entire evaluation including rounded-input reference, readout, loss and KL; not isolated core latency",
           "output_sha256": digest_arrays(outputs), "per_token_losses": losses.tolist(),
           "regimes": []}
    for offset in OFFSETS:
        selected = fixture["offsets"] == offset
        row["regimes"].append({"score_offset": offset,
            "max_abs_output_error": float(error[selected].max()), **summarize_losses(losses[selected])})
    return row


def frozen_protocol(source_commit: str) -> dict:
    return {"schema": SCHEMA, "source_commit": source_commit,
            "implementation_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "runtime": {"python": sys.version.split()[0], "numpy": np.__version__, "generator": "NumPy default_rng / PCG64"},
            "scope": "synthetic_teacher_sampled_next_token_trace_calibration",
            "trained_language_model_evaluated": False, "physical_hardware_validated": False,
            "tokenizer": "identity IDs 0..31; no natural-language tokenizer or corpus",
            "training": "none; fixed random core inputs and fixed random FP64 readout",
            "splits": {k: {"seed": seed, "trace_count": n} for k, (seed, n) in SPLITS.items()},
            "shape": {"context": CONTEXT, "dimension": DIMENSION, "vocabulary": VOCABULARY},
            "score_offsets": OFFSETS, "candidates": [asdict(c) for c in CANDIDATES],
            "selection": "minimum validation mean NLL among non-control candidates passing max absolute output error <= 1e-4; deterministic name tie-break; otherwise keep FP64 reference",
            "test": "one opened test episode after selection; selected + baseline + reference; never tune on test",
            "metric": "exp(sum scored token NLL / scored token count), natural logs",
            "max_unique_validation_candidates": 8, "max_test_candidate_executions": 2,
            "max_candidate_executions_total": 10, "max_wall_seconds": MAX_WALL_SECONDS,
            "wall_budget_enforcement": "cooperative per-trace and operation checks; launch under an external 300-second timeout for hard process termination",
            "max_workspace_payload_bytes": MAX_WORKSPACE_BYTES,
            "workspace_bound_scope": "conservative single-trace array payload, excluding resident fixtures, all-trace outputs/oracles, readout/logit/loss arrays, allocator and process RSS",
            "max_model_download_bytes": 0, "automatic_production_promotion": False,
            "limits": ["No learned R/RMSNorm/RoPE/projections/FFN or full LM forward pass",
                       "Weights precomputed in FP64; core casts identical p,a,v before arithmetic",
                       "Core arithmetic only, not GPU kernels or calibrated physical timing",
                       "Block candidates retain full input/residual arrays; block reduction is not a reduced-memory streaming implementation",
                       "Offsets intentionally stress cancellation and are not measured activation statistics",
                       "Teacher reference is population-optimal; a lower sampled-label PPL is not a new quality optimum",
                       "Synthetic PPL cannot establish natural-language quality or global minimum"]}
