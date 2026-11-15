"""Exact-source reconstruction for provenance-preserving Merlin representations.

This retrieves and verifies original source bytes. It does not reconstruct a
semantic summary, assert semantic equivalence, or issue a CACE verification
receipt.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from merlin.artifact_ref import ArtifactRef
from merlin.knowledge_compression import (
    LOSS_CHARACTERS,
    REPRESENTATION_TYPES,
    SCHEMA as REPRESENTATION_SCHEMA,
    _validate_sources,
    canonical_json,
)
from merlin.project_registry import (
    ArtifactSizeLimitError,
    MAX_ARTIFACT_READ_BYTES,
    MerlinRegistry,
)


RECONSTRUCTION_SCHEMA = "merlin-knowledge-reconstruction-report/1"
_ID_RE = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_MAX_TOTAL_BYTES = 100 * 1024 * 1024


class ReconstructionLimitError(ValueError):
    """Raised when source reconstruction would exceed an explicit byte budget."""


def reconstruct_source_artifacts(
    registry: MerlinRegistry,
    representation_ref: Mapping[str, Any],
    *,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_source_bytes: int = MAX_ARTIFACT_READ_BYTES,
) -> dict[str, Any]:
    """Recover every exact source ArtifactRef named by a representation.

    The returned report is deterministic for the same manifest and source
    bytes. Recovered byte payloads are returned separately from the JSON-safe
    report. Semantic equivalence and CACE qualification are intentionally not
    assessed here.
    """
    if (isinstance(max_total_bytes, bool) or not isinstance(max_total_bytes, int)
            or not 1 <= max_total_bytes <= 1024 * 1024 * 1024):
        raise ValueError("max_total_bytes must be between 1 byte and 1 GiB")
    if (isinstance(max_source_bytes, bool) or not isinstance(max_source_bytes, int)
            or not 1 <= max_source_bytes <= MAX_ARTIFACT_READ_BYTES):
        raise ValueError("max_source_bytes must be between 1 and 25 MiB")

    ref = ArtifactRef.from_mapping(representation_ref)
    expected_prefix = "knowledge/representations/"
    if (not ref.logical_path.startswith(expected_prefix)
            or not ref.logical_path.endswith(".json")):
        raise ValueError("representation ArtifactRef has an unexpected logical path")

    try:
        stored = registry.read_artifact_ref(
            ref.to_dict(), max_bytes=max_source_bytes,
        )
    except ArtifactSizeLimitError as exc:
        raise ReconstructionLimitError(
            "representation manifest exceeds the configured read budget"
        ) from exc

    provenance = stored["resolution"].get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("representation artifact is missing immutable producer provenance")
    if (
        provenance.get("schema") != "merlin-artifact-provenance/1"
        or provenance.get("artifact_kind") != "knowledge-representation"
        or provenance.get("artifact_schema") != REPRESENTATION_SCHEMA
        or not isinstance(provenance.get("source_repo"), str)
        or not provenance.get("source_repo", "").strip()
        or not isinstance(provenance.get("source_commit"), str)
        or not re.fullmatch(r"[0-9a-f]{40}", provenance.get("source_commit", ""))
    ):
        raise ValueError("representation artifact producer provenance is invalid")

    try:
        manifest = json.loads(stored["content"].decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("representation manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("representation manifest must be a JSON object")

    required = {
        "schema", "project_id", "representation_type", "payload",
        "source_artifacts", "source_bindings", "transformation",
        "loss_character", "representation_id",
    }
    if set(manifest) != required:
        raise ValueError("representation manifest fields do not match schema")
    if manifest["schema"] != REPRESENTATION_SCHEMA:
        raise ValueError("unsupported representation schema")
    if manifest["project_id"] != ref.project_id:
        raise ValueError("representation project_id does not match its ArtifactRef")
    if (not isinstance(manifest["representation_type"], str)
            or manifest["representation_type"] not in REPRESENTATION_TYPES):
        raise ValueError("unsupported representation_type")
    if (not isinstance(manifest["loss_character"], str)
            or manifest["loss_character"] not in LOSS_CHARACTERS):
        raise ValueError("unsupported loss_character")
    if not isinstance(manifest["transformation"], dict) or set(manifest["transformation"]) != {
        "tool_id", "tool_version",
    }:
        raise ValueError("invalid transformation metadata")
    for key in ("tool_id", "tool_version"):
        if not isinstance(manifest["transformation"][key], str) or not manifest["transformation"][key].strip():
            raise ValueError("transformation tool identity and version are required")

    representation_id = manifest["representation_id"]
    if not isinstance(representation_id, str) or not _ID_RE.fullmatch(representation_id):
        raise ValueError("representation_id must be a full lowercase SHA-256 digest")
    if provenance.get("artifact_id") != f"knowledge-representation-{representation_id[:24]}":
        raise ValueError("representation producer artifact_id does not match representation_id")
    expected_path = f"{expected_prefix}{representation_id}.json"
    if ref.logical_path != expected_path:
        raise ValueError("representation path does not match representation_id")

    body = {key: value for key, value in manifest.items() if key != "representation_id"}
    actual_id = hashlib.sha256(canonical_json(body)).hexdigest()
    if actual_id != representation_id:
        raise ValueError("representation manifest identity does not match its canonical content")

    refs, bindings = _validate_sources(
        manifest["source_artifacts"], manifest["source_bindings"],
    )
    bindings_by_ref: dict[bytes, list[dict[str, Any]]] = {}
    for binding in bindings:
        bindings_by_ref.setdefault(canonical_json(binding["artifact_ref"]), []).append(binding)

    source_payloads: list[dict[str, Any]] = []
    source_results: list[dict[str, Any]] = []
    total_bytes = 0
    for source_ref in refs:
        remaining = max_total_bytes - total_bytes
        if remaining <= 0:
            raise ReconstructionLimitError("total source reconstruction byte budget exceeded")
        read_limit = min(max_source_bytes, remaining)
        try:
            source = registry.read_artifact_ref(source_ref, max_bytes=read_limit)
        except ArtifactSizeLimitError as exc:
            raise ReconstructionLimitError(
                "source artifact exceeds the remaining reconstruction byte budget"
            ) from exc

        raw = source["content"]
        actual_digest = hashlib.sha256(raw).hexdigest()
        if actual_digest != source_ref["sha256"]:
            raise RuntimeError("reconstructed source bytes do not match the pinned ArtifactRef")
        total_bytes += len(raw)
        source_payloads.append({
            "artifact_ref": source_ref,
            "content": raw,
        })
        source_results.append({
            "artifact_ref": source_ref,
            "source_sha256": actual_digest,
            "size_bytes": len(raw),
            "exact_bytes_recovered": True,
            "source_bindings": bindings_by_ref[canonical_json(source_ref)],
        })

    report_body = {
        "schema": RECONSTRUCTION_SCHEMA,
        "representation_id": representation_id,
        "representation_ref": ref.to_dict(),
        "source_results": source_results,
        "source_count": len(source_results),
        "total_source_bytes": total_bytes,
        "all_source_bytes_exact": True,
        "semantic_equivalence": "not_assessed",
        "cace_verification": "not_requested",
        "qualification": False,
    }
    report = {
        **report_body,
        "report_sha256": hashlib.sha256(canonical_json(report_body)).hexdigest(),
    }
    return {"report": report, "source_payloads": source_payloads}


__all__ = [
    "RECONSTRUCTION_SCHEMA", "DEFAULT_MAX_TOTAL_BYTES",
    "ReconstructionLimitError", "reconstruct_source_artifacts",
]
