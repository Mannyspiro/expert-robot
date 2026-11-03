"""Runtime capability, bounded async streaming, qualification and evidence contracts.

This module is deliberately advisory: it reports evidence and candidate choices but
never grants execution authority, promotes providers, or mutates CACE state.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from typing import Any, AsyncIterable, AsyncIterator, Awaitable, Callable, Mapping, Sequence


CAPABILITY_STATES = {"unavailable", "configured", "unqualified", "qualified"}


@dataclass(frozen=True)
class ProviderQualificationReceipt:
    schema: str
    provider_id: str
    model_id: str
    model_revision: str
    artifact_sha256: str
    held_out_task_ids: tuple[str, ...]
    held_out_seed_ids: tuple[str, ...]
    metrics: Mapping[str, float]
    privacy_review: str
    privacy_policy_sha256: str
    evaluator_revision: str
    created_at: str
    passed: bool
    promotion_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["held_out_task_ids"] = list(self.held_out_task_ids)
        value["held_out_seed_ids"] = list(self.held_out_seed_ids)
        return value


@dataclass(frozen=True)
class CapabilityRecord:
    capability_id: str
    state: str
    provider_id: str | None = None
    model_id: str | None = None
    model_revision: str | None = None
    modalities: tuple[str, ...] = ()
    reason: str = ""
    receipt_sha256: str | None = None
    promotion_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["modalities"] = list(self.modalities)
        return row


class RuntimeCapabilityRegistry:
    """Explicit runtime state; configuration alone never implies qualification."""

    def __init__(self) -> None:
        self._records: dict[str, CapabilityRecord] = {}

    def set_unavailable(self, capability_id: str, reason: str) -> CapabilityRecord:
        return self._put(CapabilityRecord(capability_id, "unavailable", reason=reason))

    def configure(self, capability_id: str, *, provider_id: str, model_id: str,
                  model_revision: str, modalities: Sequence[str] = ()) -> CapabilityRecord:
        if not all(isinstance(x, str) and x.strip() for x in
                   (capability_id, provider_id, model_id, model_revision)):
            raise ValueError("capability and provider/model identity fields are required")
        return self._put(CapabilityRecord(
            capability_id, "configured", provider_id, model_id, model_revision,
            tuple(sorted(set(modalities))), "configured_but_not_qualified"))

    def mark_unqualified(self, capability_id: str, reason: str) -> CapabilityRecord:
        old = self._records.get(capability_id)
        if old is None:
            raise KeyError(capability_id)
        return self._put(CapabilityRecord(
            capability_id, "unqualified", old.provider_id, old.model_id,
            old.model_revision, old.modalities, reason))

    def qualify(self, capability_id: str, receipt: ProviderQualificationReceipt) -> CapabilityRecord:
        old = self._records.get(capability_id)
        if old is None:
            raise KeyError(capability_id)
        if not receipt.passed or receipt.promotion_authorized:
            raise ValueError("receipt must pass qualification and must not authorize promotion")
        if (old.provider_id, old.model_id, old.model_revision) != (
                receipt.provider_id, receipt.model_id, receipt.model_revision):
            raise ValueError("receipt identity does not match configured provider/model revision")
        digest = canonical_sha256(receipt.to_dict())
        return self._put(CapabilityRecord(
            capability_id, "qualified", old.provider_id, old.model_id,
            old.model_revision, old.modalities, "held_out_qualification_passed", digest))

    def get(self, capability_id: str) -> CapabilityRecord:
        return self._records[capability_id]

    def snapshot(self) -> dict[str, Any]:
        return {"schema": "merlin-runtime-capabilities/1",
                "capabilities": [self._records[k].to_dict() for k in sorted(self._records)],
                "authority_expanded": False}

    def _put(self, record: CapabilityRecord) -> CapabilityRecord:
        if record.state not in CAPABILITY_STATES:
            raise ValueError("invalid capability state")
        self._records[record.capability_id] = record
        return record


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class StreamChunk:
    index: int
    byte_count: int
    elapsed_ms: float
    since_previous_ms: float
    first_byte_ms: float | None


@dataclass(frozen=True)
class StreamResult:
    request_id: str
    chunks: tuple[StreamChunk, ...]
    total_bytes: int
    total_ms: float
    completed: bool
    cancelled: bool = False


class AsyncStreamingGateway:
    """Bounded async byte-stream relay with queue-inclusive deadline and cancellation."""

    def __init__(self, *, max_concurrency: int = 4, max_response_bytes: int = 64_000_000,
                 max_chunk_bytes: int = 1_048_576) -> None:
        if max_concurrency < 1 or max_response_bytes < 1 or max_chunk_bytes < 1:
            raise ValueError("gateway limits must be positive")
        self._slots = asyncio.Semaphore(max_concurrency)
        self.max_response_bytes = max_response_bytes
        self.max_chunk_bytes = max_chunk_bytes

    async def stream(self, request_id: str,
                     open_stream: Callable[[], Awaitable[AsyncIterable[bytes]]],
                     *, deadline_seconds: float = 180.0,
                     on_chunk: Callable[[bytes], Any] | None = None,
                     on_timing: Callable[[StreamChunk], Any] | None = None
                     ) -> AsyncIterator[bytes]:
        if not request_id or deadline_seconds <= 0 or not math.isfinite(deadline_seconds):
            raise ValueError("request_id and finite positive deadline are required")
        started = time.monotonic()
        deadline = started + deadline_seconds
        acquired = False
        iterator: Any = None
        total = 0
        previous = started
        chunks: list[StreamChunk] = []
        try:
            await asyncio.wait_for(self._slots.acquire(), timeout=max(0.001, deadline-time.monotonic()))
            acquired = True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError
            source = await asyncio.wait_for(open_stream(), timeout=remaining)
            iterator = source.__aiter__()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise asyncio.TimeoutError
                try:
                    chunk = await asyncio.wait_for(iterator.__anext__(), timeout=remaining)
                except StopAsyncIteration:
                    break
                if not isinstance(chunk, (bytes, bytearray, memoryview)):
                    raise TypeError("stream chunks must be bytes-like")
                chunk = bytes(chunk)
                if len(chunk) > self.max_chunk_bytes:
                    raise ValueError("stream chunk exceeds configured limit")
                total += len(chunk)
                if total > self.max_response_bytes:
                    raise ValueError("stream exceeds configured response limit")
                now = time.monotonic()
                chunks.append(StreamChunk(len(chunks), len(chunk),
                    (now-started)*1000.0, (now-previous)*1000.0,
                    (now-started)*1000.0 if not chunks else None))
                previous = now
                if on_timing is not None:
                    timing_result = on_timing(chunks[-1])
                    if asyncio.iscoroutine(timing_result):
                        await timing_result
                if on_chunk is not None:
                    result = on_chunk(chunk)
                    if asyncio.iscoroutine(result):
                        await result
                yield chunk
        finally:
            if iterator is not None and hasattr(iterator, "aclose"):
                try:
                    await iterator.aclose()
                except (RuntimeError, asyncio.CancelledError):
                    pass
            if acquired:
                self._slots.release()


def build_qualification_receipt(*, provider_id: str, model_id: str,
        model_revision: str, artifact_sha256: str, held_out_task_ids: Sequence[str],
        held_out_seed_ids: Sequence[str], metrics: Mapping[str, float],
        privacy_review: str, privacy_policy_sha256: str, evaluator_revision: str,
        created_at: str, quality_floor: float, max_latency_ms: float) -> ProviderQualificationReceipt:
    """Create a receipt from independently collected held-out evidence; no hidden test runner."""
    if len(artifact_sha256) != 64 or any(c not in "0123456789abcdef" for c in artifact_sha256):
        raise ValueError("artifact_sha256 must be lowercase SHA-256")
    if len(privacy_policy_sha256) != 64 or any(c not in "0123456789abcdef" for c in privacy_policy_sha256):
        raise ValueError("privacy_policy_sha256 must be lowercase SHA-256")
    if not held_out_task_ids or not held_out_seed_ids:
        raise ValueError("held-out task and seed sets must be non-empty")
    if len(set(held_out_task_ids)) != len(held_out_task_ids) or len(set(held_out_seed_ids)) != len(held_out_seed_ids):
        raise ValueError("held-out identifiers must be unique")
    if privacy_review not in {"approved", "rejected", "pending"}:
        raise ValueError("privacy_review must be approved, rejected, or pending")
    clean = dict(metrics)
    if not clean or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                        or not math.isfinite(v) for v in clean.values()):
        raise ValueError("metrics must be finite numeric values")
    passed = (privacy_review == "approved" and clean.get("quality", -math.inf) >= quality_floor
              and clean.get("latency_ms", math.inf) <= max_latency_ms)
    return ProviderQualificationReceipt(
        "merlin-provider-qualification/1", provider_id, model_id, model_revision,
        artifact_sha256, tuple(held_out_task_ids), tuple(held_out_seed_ids),
        clean, privacy_review, privacy_policy_sha256, evaluator_revision, created_at,
        passed, False)


def paired_heldout_comparison(evaluators: Mapping[str, Callable[[int], Mapping[str, float]]],
                              seeds: Sequence[int], *, order_seed: int = 0) -> dict[str, Any]:
    """Evaluate all candidates on identical held-out seeds and return paired deltas."""
    if "baseline" not in evaluators or not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("baseline and unique held-out seeds are required")
    import random
    rng = random.Random(order_seed)
    rows: dict[str, dict[str, list[float]]] = {
        name: {} for name in evaluators}
    orders = []
    for seed in seeds:
        order = list(evaluators)
        rng.shuffle(order)
        orders.append({"seed": seed, "order": order})
        for name in order:
            result = dict(evaluators[name](seed))
            for metric, value in result.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError("evaluation metrics must be finite numbers")
                rows[name].setdefault(metric, []).append(float(value))
    baseline = rows["baseline"]
    comparisons: dict[str, Any] = {}
    for name, metrics in rows.items():
        if name == "baseline":
            continue
        comparisons[name] = {}
        for metric, values in metrics.items():
            if metric not in baseline or len(values) != len(baseline[metric]):
                raise ValueError("candidates must return identical metric sets")
            deltas = [a-b for a, b in zip(values, baseline[metric])]
            comparisons[name][metric] = {
                "mean_difference_vs_baseline": sum(deltas)/len(deltas),
                "paired_differences": deltas}
    return {"schema": "merlin-heldout-routing-comparison/1",
            "held_out_seeds": list(seeds), "randomized_order": orders,
            "candidate_metrics": rows, "paired_comparisons": comparisons,
            "promotion_authorized": False}


def select_measured_route(comparison: Mapping[str, Any], *, quality_metric: str = "quality",
                          latency_metric: str = "latency_ms") -> dict[str, Any]:
    """Select only from candidates with positive paired quality and non-worse latency."""
    deltas = comparison.get("paired_comparisons", {})
    eligible = []
    for candidate, metrics in deltas.items():
        quality = metrics.get(quality_metric, {}).get("mean_difference_vs_baseline", -math.inf)
        latency = metrics.get(latency_metric, {}).get("mean_difference_vs_baseline", math.inf)
        if quality > 0 and latency <= 0:
            eligible.append((quality, -latency, candidate))
    winner = max(eligible)[2] if eligible else "baseline"
    return {"selected_candidate": winner, "reason": "heldout_paired_evidence" if winner != "baseline"
            else "no_candidate_dominates_baseline", "promotion_authorized": False}


def make_cace_evidence_envelope(*, source_repository: str, source_revision: str,
        artifact_path: str, artifact_sha256: str, evidence_type: str,
        evidence: Mapping[str, Any], verifier_id: str, verified: bool) -> dict[str, Any]:
    """Create a typed, hash-addressed envelope; verification remains an external claim."""
    if not source_repository or not source_revision or not artifact_path or not verifier_id:
        raise ValueError("source, revision, artifact path and verifier are required")
    if len(artifact_sha256) != 64 or any(c not in "0123456789abcdef" for c in artifact_sha256):
        raise ValueError("artifact_sha256 must be lowercase SHA-256")
    if evidence_type not in {"test", "proof", "qualification", "benchmark", "review"}:
        raise ValueError("unsupported evidence_type")
    evidence_digest = canonical_sha256(evidence)
    body = {"schema": "cace-evidence-envelope/1", "source_repository": source_repository,
            "source_revision": source_revision, "artifact_path": artifact_path,
            "artifact_sha256": artifact_sha256, "evidence_type": evidence_type,
            "evidence": dict(evidence), "evidence_sha256": evidence_digest,
            "verifier_id": verifier_id, "verified": bool(verified),
            "authority_expanded": False}
    body["envelope_sha256"] = canonical_sha256(body)
    return body
