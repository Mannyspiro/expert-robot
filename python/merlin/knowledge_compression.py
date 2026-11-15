"""Provenance-preserving knowledge representations over Merlin's canonical stores.

Derived representations are ordinary versioned registry artifacts linked to exact
source ArtifactRefs in the existing knowledge graph. This module deliberately
creates no second registry, database, authority system, or verification receipt.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from merlin.artifact_ref import ArtifactRef
from merlin.knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry


SCHEMA = "merlin-knowledge-representation/1"
REPRESENTATION_TYPES = frozenset({
    "summary", "atomic_claims", "concept_index", "symbolic",
    "procedure", "media_index", "embedding_metadata", "text_extraction", "other",
})
LOSS_CHARACTERS = frozenset({"lossy", "unknown", "reversible_claim"})
LOCATOR_TYPES = frozenset({
    "page", "section", "line_range", "byte_range", "frame",
    "timecode", "node_id", "whole_artifact",
})
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")


def canonical_json(value: Any) -> bytes:
    """Serialize JSON-compatible data deterministically as UTF-8."""
    def check(item: Any, path: str = "$") -> None:
        if item is None or isinstance(item, (str, bool, int)):
            return
        if isinstance(item, float):
            import math
            if not math.isfinite(item):
                raise ValueError(f"non-finite number at {path}")
            return
        if isinstance(item, list):
            for index, child in enumerate(item):
                check(child, f"{path}[{index}]")
            return
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError(f"non-string object key at {path}")
                check(child, f"{path}.{key}")
            return
        raise ValueError(f"unsupported JSON value at {path}: {type(item).__name__}")

    check(value)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _artifact_ref(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("source artifact reference must be an object")
    return ArtifactRef.from_mapping(value).to_dict()


def _validate_sources(
    source_refs: Sequence[Mapping[str, Any]],
    source_bindings: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(source_refs, (list, tuple)) or not source_refs:
        raise ValueError("at least one exact source ArtifactRef is required")
    refs = [_artifact_ref(item) for item in source_refs]
    ref_keys = [canonical_json(item) for item in refs]
    if len(ref_keys) != len(set(ref_keys)):
        raise ValueError("source ArtifactRefs must be unique")
    allowed = set(ref_keys)

    if not isinstance(source_bindings, (list, tuple)) or not source_bindings:
        raise ValueError("at least one exact source locator binding is required")
    bindings: list[dict[str, Any]] = []
    for binding in source_bindings:
        if not isinstance(binding, Mapping) or set(binding) != {
            "artifact_ref", "locator_type", "locator",
        }:
            raise ValueError("source binding must contain exactly artifact_ref, locator_type and locator")
        ref = _artifact_ref(binding["artifact_ref"])
        if canonical_json(ref) not in allowed:
            raise ValueError("source binding references an artifact outside source_artifacts")
        locator_type = binding["locator_type"]
        locator = binding["locator"]
        if not isinstance(locator_type, str) or locator_type not in LOCATOR_TYPES:
            raise ValueError("unsupported source locator type")
        if not isinstance(locator, (str, int, dict)) or isinstance(locator, bool):
            raise ValueError("source locator must be text, an integer, or an object")
        if isinstance(locator, str) and (not locator.strip() or len(locator) > 2048):
            raise ValueError("source locator text is empty or too long")
        if isinstance(locator, int) and locator < 0:
            raise ValueError("source locator integer must be non-negative")
        if isinstance(locator, dict) and not locator:
            raise ValueError("source locator object must not be empty")
        canonical_json(locator)
        bindings.append({
            "artifact_ref": ref,
            "locator_type": locator_type,
            "locator": locator,
        })
    return refs, bindings


def store_knowledge_representation(
    registry: MerlinRegistry,
    graph: MerlinKnowledgeGraph,
    *,
    project_id: str,
    representation_type: str,
    payload: Any,
    source_refs: Sequence[Mapping[str, Any]],
    source_bindings: Sequence[Mapping[str, Any]],
    tool_id: str,
    tool_version: str,
    loss_character: str = "unknown",
    source_repo: str,
    source_commit: str,
) -> dict[str, Any]:
    """Store a deterministic, source-bound derived representation.

    The registry artifact is written first. Graph projection writes are exact-
    replay idempotent, so a crash between stores can be repaired by retrying.
    This is intentionally not a cross-database atomic transaction. The source
    artifacts are re-resolved and re-hashed before the representation is stored.
    """
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("project_id is required")
    if not isinstance(representation_type, str) or representation_type not in REPRESENTATION_TYPES:
        raise ValueError("unsupported representation_type")
    if not isinstance(loss_character, str) or loss_character not in LOSS_CHARACTERS:
        raise ValueError("unsupported loss_character")
    if not isinstance(tool_id, str) or not tool_id.strip() or len(tool_id) > 256:
        raise ValueError("tool_id must be non-empty bounded text")
    if not isinstance(tool_version, str) or not tool_version.strip() or len(tool_version) > 128:
        raise ValueError("tool_version must be non-empty bounded text")
    if not isinstance(source_repo, str) or not source_repo.strip() or len(source_repo) > 256:
        raise ValueError("source_repo must be non-empty bounded text")
    if not isinstance(source_commit, str) or not _HEX_40.fullmatch(source_commit):
        raise ValueError("source_commit must be a full lowercase Git commit SHA")

    refs, bindings = _validate_sources(source_refs, source_bindings)
    # Re-resolve every source before deriving anything from it.
    for ref in refs:
        registry.resolve_artifact_ref(ref)

    body = {
        "schema": SCHEMA,
        "project_id": project_id,
        "representation_type": representation_type,
        "payload": payload,
        "source_artifacts": refs,
        "source_bindings": bindings,
        "transformation": {"tool_id": tool_id, "tool_version": tool_version},
        "loss_character": loss_character,
    }
    body_bytes = canonical_json(body)
    representation_id = hashlib.sha256(body_bytes).hexdigest()
    manifest = {**body, "representation_id": representation_id}
    manifest_bytes = canonical_json(manifest)
    logical_path = f"knowledge/representations/{representation_id}.json"

    digest = registry.put_artifact(
        project_id,
        logical_path,
        manifest_bytes,
        media_type="application/vnd.merlin.knowledge-representation+json",
        provenance={
            "schema": "merlin-artifact-provenance/1",
            "source_repo": source_repo,
            "source_commit": source_commit,
            "artifact_id": f"knowledge-representation-{representation_id[:24]}",
            "artifact_kind": "knowledge-representation",
            "artifact_schema": SCHEMA,
        },
    )
    representation_ref = registry.artifact_ref(project_id, logical_path)
    registry.resolve_artifact_ref(representation_ref)

    representation_node_id = f"knowledge-representation:{representation_id}"
    graph.add_node(GraphNode(
        node_id=representation_node_id,
        node_type="object_view",
        label=f"{representation_type}:{representation_id[:12]}",
        payload={
            "schema": SCHEMA,
            "representation_id": representation_id,
            "artifact_ref": representation_ref,
            "loss_character": loss_character,
            "epistemic_status": "derived_unverified",
        },
        evidence_class="derived_unverified",
        source_uri=f"merlin://artifact/{project_id}/{logical_path}",
    ))

    binding_by_ref: dict[bytes, list[dict[str, Any]]] = {}
    for binding in bindings:
        binding_by_ref.setdefault(canonical_json(binding["artifact_ref"]), []).append(binding)

    source_node_ids: list[str] = []
    for ref in refs:
        source_identity = hashlib.sha256(canonical_json(ref)).hexdigest()
        source_node_id = f"artifact-reference:{source_identity}"
        source_node_ids.append(source_node_id)
        graph.add_node(GraphNode(
            node_id=source_node_id,
            node_type="artifact_reference",
            label=f"source:{ref['logical_path']}",
            payload={"artifact_ref": ref},
            evidence_class="source_identity_verified",
            source_uri=f"merlin://artifact/{ref['project_id']}/{ref['logical_path']}",
        ))
        graph.add_edge(GraphEdge(
            source_id=representation_node_id,
            relation="derived_from",
            target_id=source_node_id,
            payload={
                "source_bindings": binding_by_ref[canonical_json(ref)],
                "representation_id": representation_id,
            },
        ))

    return {
        "schema": SCHEMA,
        "representation_id": representation_id,
        "representation_ref": representation_ref,
        "representation_digest": digest,
        "source_artifact_refs": refs,
        "graph_node_id": representation_node_id,
        "source_graph_node_ids": source_node_ids,
        "authority": "derived-representation-only",
        "verification": "not-verified",
        "replay_safe": True,
    }


__all__ = [
    "SCHEMA", "canonical_json", "store_knowledge_representation",
]
