"""Measured, fail-closed model backend selection for Merlin.

This module defines routing policy and evidence contracts only. It does not
load model weights, make network calls, or treat a configured endpoint as
qualified. Serving engines are replaceable adapters behind this contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re
from typing import Iterable


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_STATES = {"configured", "available", "degraded", "unavailable"}
_ENGINES = {
    "airllm", "vllm", "sglang", "llama_cpp", "mlx",
    "transformers", "litellm_gateway", "ray_serve",
}


class ModelFabricError(ValueError):
    """Invalid model metadata, measurement, or route request."""


@dataclass(frozen=True)
class ModelBackend:
    backend_id: str
    engine: str
    model_id: str
    model_revision: str
    engine_revision: str
    task_scopes: tuple[str, ...]
    data_classes: tuple[str, ...] = ("public", "internal")
    state: str = "configured"
    supports_streaming: bool = False
    supports_tools: bool = False
    context_window: int = 0
    max_concurrency: int = 1
    estimated_ram_bytes: int = 0
    estimated_vram_bytes: int = 0
    endpoint_kind: str = "local"  # local, remote_allowlisted, embedded
    license_id: str = "unknown"

    def validate(self) -> None:
        if not self.backend_id or not self.model_id or not self.model_revision:
            raise ModelFabricError("backend identity and model revision are required")
        if self.engine not in _ENGINES:
            raise ModelFabricError("unsupported model engine")
        if self.state not in _STATES:
            raise ModelFabricError("invalid backend state")
        if self.endpoint_kind not in {"local", "remote_allowlisted", "embedded"}:
            raise ModelFabricError("invalid endpoint kind")
        if not self.task_scopes or not self.data_classes:
            raise ModelFabricError("task scopes and data classes are required")
        if self.context_window < 0 or self.max_concurrency < 1:
            raise ModelFabricError("invalid context window or concurrency")
        if self.estimated_ram_bytes < 0 or self.estimated_vram_bytes < 0:
            raise ModelFabricError("resource estimates must be nonnegative")


@dataclass(frozen=True)
class ModelMeasurement:
    backend_id: str
    task_scope: str
    p95_latency_ms: float
    tokens_per_second: float
    quality_score: float
    cost_per_1k_tokens: float
    peak_ram_bytes: int
    peak_vram_bytes: int
    sample_count: int
    eval_suite_sha256: str
    result_sha256: str
    measured_at: str

    def validate(self) -> None:
        numeric = (self.p95_latency_ms, self.tokens_per_second,
                   self.quality_score, self.cost_per_1k_tokens)
        if not all(math.isfinite(v) for v in numeric):
            raise ModelFabricError("measurement values must be finite")
        if self.p95_latency_ms < 0 or self.tokens_per_second < 0 or self.cost_per_1k_tokens < 0:
            raise ModelFabricError("latency, throughput and cost must be nonnegative")
        if not 0 <= self.quality_score <= 1:
            raise ModelFabricError("quality_score must be within [0, 1]")
        if min(self.peak_ram_bytes, self.peak_vram_bytes) < 0 or self.sample_count < 1:
            raise ModelFabricError("invalid resource measurement or sample count")
        if not _SHA256.fullmatch(self.eval_suite_sha256) or not _SHA256.fullmatch(self.result_sha256):
            raise ModelFabricError("evaluation suite and result digests must be SHA-256")
        try:
            datetime.fromisoformat(self.measured_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ModelFabricError("measured_at must be an ISO-8601 timestamp") from exc


@dataclass(frozen=True)
class ModelQualificationReceipt:
    backend_id: str
    model_revision: str
    engine_revision: str
    heldout_eval_sha256: str
    eval_result_sha256: str
    security_review_sha256: str
    issued_at: str
    approved: bool

    def validate(self) -> None:
        if not all(_SHA256.fullmatch(v) for v in (
            self.heldout_eval_sha256, self.eval_result_sha256,
            self.security_review_sha256,
        )):
            raise ModelFabricError("qualification receipt requires three SHA-256 digests")
        try:
            datetime.fromisoformat(self.issued_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ModelFabricError("issued_at must be an ISO-8601 timestamp") from exc


@dataclass(frozen=True)
class ModelRouteRequest:
    task_scope: str
    data_class: str = "internal"
    min_quality: float = 0.0
    max_p95_latency_ms: float | None = None
    max_cost_per_1k_tokens: float | None = None
    max_ram_bytes: int | None = None
    max_vram_bytes: int | None = None
    require_streaming: bool = False
    require_tools: bool = False
    preferred_engines: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelRouteDecision:
    selected_backend_id: str | None
    reason: str
    ranked_backend_ids: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]
    policy: str = "merlin-measured-quality-first/1"


def _within(value: int, limit: int | None) -> bool:
    return limit is None or value <= limit


def route_model(
    request: ModelRouteRequest,
    backends: Iterable[ModelBackend],
    measurements: Iterable[ModelMeasurement],
    receipts: Iterable[ModelQualificationReceipt],
) -> ModelRouteDecision:
    """Choose only backends with matching held-out qualification and measurements.

    Quality is the primary ordering criterion. Latency, cost and resource use
    break ties. Unqualified or stale/mismatched evidence is never guessed.
    """
    if not request.task_scope or not request.data_class:
        raise ModelFabricError("task scope and data class are required")
    if not math.isfinite(request.min_quality) or not 0 <= request.min_quality <= 1:
        raise ModelFabricError("min_quality must be within [0, 1]")
    for bound in (request.max_p95_latency_ms, request.max_cost_per_1k_tokens):
        if bound is not None and (not math.isfinite(bound) or bound < 0):
            raise ModelFabricError("latency and cost bounds must be finite and nonnegative")
    for bound in (request.max_ram_bytes, request.max_vram_bytes):
        if bound is not None and bound < 0:
            raise ModelFabricError("resource bounds must be nonnegative")

    measurements_by_id: dict[str, list[ModelMeasurement]] = {}
    for measurement in measurements:
        measurement.validate()
        measurements_by_id.setdefault(measurement.backend_id, []).append(measurement)
    receipts_by_id: dict[str, list[ModelQualificationReceipt]] = {}
    for receipt in receipts:
        receipt.validate()
        receipts_by_id.setdefault(receipt.backend_id, []).append(receipt)

    ranked: list[tuple[tuple[float, ...], str]] = []
    excluded: list[tuple[str, str]] = []
    seen: set[str] = set()
    for backend in backends:
        backend.validate()
        if backend.backend_id in seen:
            raise ModelFabricError("duplicate backend_id")
        seen.add(backend.backend_id)
        reason = None
        if backend.state != "available":
            reason = "backend_not_available"
        elif request.task_scope not in backend.task_scopes:
            reason = "task_scope_not_supported"
        elif request.data_class not in backend.data_classes:
            reason = "data_class_not_permitted"
        elif request.require_streaming and not backend.supports_streaming:
            reason = "streaming_not_supported"
        elif request.require_tools and not backend.supports_tools:
            reason = "tool_calls_not_supported"
        elif not _within(backend.estimated_ram_bytes, request.max_ram_bytes):
            reason = "estimated_ram_exceeds_budget"
        elif not _within(backend.estimated_vram_bytes, request.max_vram_bytes):
            reason = "estimated_vram_exceeds_budget"

        evidence = measurements_by_id.get(backend.backend_id, [])
        metric = next((m for m in reversed(evidence) if m.task_scope == request.task_scope), None)
        if reason is None and metric is None:
            reason = "no_task_specific_measurement"
        if reason is None and metric.quality_score < request.min_quality:
            reason = "quality_below_threshold"
        if reason is None and request.max_p95_latency_ms is not None and metric.p95_latency_ms > request.max_p95_latency_ms:
            reason = "latency_exceeds_budget"
        if reason is None and request.max_cost_per_1k_tokens is not None and metric.cost_per_1k_tokens > request.max_cost_per_1k_tokens:
            reason = "cost_exceeds_budget"

        valid_receipt = None
        if reason is None:
            for receipt in reversed(receipts_by_id.get(backend.backend_id, [])):
                if (receipt.approved and receipt.model_revision == backend.model_revision
                        and receipt.engine_revision == backend.engine_revision
                        and receipt.heldout_eval_sha256 == metric.eval_suite_sha256
                        and receipt.eval_result_sha256 == metric.result_sha256):
                    valid_receipt = receipt
                    break
            if valid_receipt is None:
                reason = "no_matching_approved_qualification_receipt"

        if reason:
            excluded.append((backend.backend_id, reason))
            continue
        # Prefer quality, then latency, throughput, cost, lower memory, then ID.
        score = (
            -metric.quality_score,
            metric.p95_latency_ms,
            -metric.tokens_per_second,
            metric.cost_per_1k_tokens,
            metric.peak_ram_bytes + metric.peak_vram_bytes,
        )
        if request.preferred_engines and backend.engine in request.preferred_engines:
            score = (score[0] - 0.000001, *score[1:])
        ranked.append((score, backend.backend_id))

    ranked.sort(key=lambda row: (row[0], row[1]))
    ids = tuple(row[1] for row in ranked)
    return ModelRouteDecision(
        selected_backend_id=ids[0] if ids else None,
        reason="qualified_measured_candidate_selected" if ids else "no_qualified_candidate",
        ranked_backend_ids=ids,
        excluded=tuple(sorted(excluded)),
    )
