"""Deterministic, read-only qualification evidence DAG projection.

This module validates and hashes supplied evidence projections. It does not
retrieve evidence, verify signatures, qualify capabilities, or grant authority.
Canonical records remain owned by MerlinRegistry, GitHub, CACE, OCI and Lean.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict, deque
from typing import Any, Iterable, Mapping


SCHEMA = "merlin-qualification-evidence-dag/1"
AUTHORITY = "read-only-projection"
NODE_TYPES = frozenset({
    "source_commit", "artifact_version", "workflow_run", "cace_attestation",
    "trust_root", "verification_receipt", "oci_execution",
    "protected_orchestrator", "lean_compile",
})
RELATIONS = frozenset({
    "derived_from", "built_by", "attests", "verifies", "executes", "qualifies",
})
STATUSES = frozenset({"qualified", "unqualified", "stale", "revoked", "blocked"})
_STATUS_RANK = {
    "qualified": 0, "unqualified": 1, "blocked": 2, "stale": 3, "revoked": 4,
}
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: Any) -> bytes:
    """Return the single canonical UTF-8 JSON representation used by v1."""
    _validate_json_value(value)
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("value is not canonical JSON data") from exc


def _validate_json_value(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite number at {path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"object key must be a string at {path}")
            _validate_json_value(item, f"{path}.{key}")
        return
    raise ValueError(f"unsupported JSON value at {path}: {type(value).__name__}")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_digest(value: Any, field: str) -> None:
    if not isinstance(value, str) or not _HEX_64.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


def _require_text(identity: Mapping[str, Any], field: str) -> None:
    value = identity.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"identity.{field} must be a non-empty string")


def _require_positive_int(identity: Mapping[str, Any], field: str) -> None:
    value = identity.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"identity.{field} must be a positive integer")


def _validate_identity(node_type: str, identity: Mapping[str, Any]) -> None:
    """Validate the stable minimum identity for each evidence node type."""
    if not isinstance(identity, Mapping) or not identity:
        raise ValueError("node identity must be a non-empty object")
    _validate_json_value(dict(identity), "$.identity")

    if node_type == "source_commit":
        _require_text(identity, "repository")
        if not isinstance(identity.get("commit"), str) or not _HEX_40.fullmatch(identity["commit"]):
            raise ValueError("identity.commit must be a full lowercase Git commit SHA")
    elif node_type == "artifact_version":
        _require_text(identity, "project_id")
        _require_text(identity, "logical_path")
        path = identity["logical_path"]
        if (path.startswith("/") or "\\" in path or "\x00" in path
                or any(part in {"", ".", ".."} for part in path.split("/"))):
            raise ValueError("identity.logical_path must be normalized and traversal-free")
        _require_positive_int(identity, "version")
        _require_digest(identity.get("digest"), "identity.digest")
        size = identity.get("size_bytes")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("identity.size_bytes must be a non-negative integer")
    elif node_type == "workflow_run":
        _require_text(identity, "repository")
        _require_text(identity, "workflow_id")
        _require_positive_int(identity, "run_id")
        _require_positive_int(identity, "attempt")
        if not isinstance(identity.get("head_sha"), str) or not _HEX_40.fullmatch(identity["head_sha"]):
            raise ValueError("identity.head_sha must be a full lowercase Git commit SHA")
        _require_text(identity, "conclusion")
        _require_digest(identity.get("artifact_digest"), "identity.artifact_digest")
    elif node_type == "cace_attestation":
        _require_digest(identity.get("statement_sha256"), "identity.statement_sha256")
        for field in ("verifier_id", "key_id", "purpose"):
            _require_text(identity, field)
        if not isinstance(identity.get("artifact_ref"), dict):
            raise ValueError("identity.artifact_ref must be an object")
    elif node_type == "trust_root":
        for field in ("authority_id", "version"):
            _require_text(identity, field)
        _require_digest(identity.get("root_sha256"), "identity.root_sha256")
    elif node_type == "verification_receipt":
        _require_digest(identity.get("receipt_sha256"), "identity.receipt_sha256")
        _require_text(identity, "verifier_id")
        if not isinstance(identity.get("artifact_ref"), dict):
            raise ValueError("identity.artifact_ref must be an object")
    elif node_type == "oci_execution":
        for field in ("execution_id", "runner_profile", "task_ref"):
            _require_text(identity, field)
        if not isinstance(identity.get("input_refs"), list):
            raise ValueError("identity.input_refs must be an array")
    elif node_type == "protected_orchestrator":
        _require_text(identity, "repository")
        _require_text(identity, "workflow_id")
        _require_positive_int(identity, "run_id")
        _require_positive_int(identity, "attempt")
        _require_text(identity, "execution_id")
    elif node_type == "lean_compile":
        for field in ("module", "lean_version", "mathlib_revision", "result"):
            _require_text(identity, field)
        _require_digest(identity.get("source_sha256"), "identity.source_sha256")


def node_id_for(node_type: str, identity: Mapping[str, Any]) -> str:
    """Derive the stable node ID from the complete type and identity."""
    if node_type not in NODE_TYPES:
        raise ValueError("unknown evidence node type")
    _validate_identity(node_type, identity)
    payload = {"node_type": node_type, "identity": dict(identity)}
    return "sha256:" + _sha256(canonical_json(payload))


def make_node(
    node_type: str, identity: Mapping[str, Any], record_sha256: str,
    evidence_class: str, status: str,
) -> dict[str, Any]:
    """Build a fully identified node; record_sha256 must come from its verifier."""
    _require_digest(record_sha256, "record_sha256")
    if not isinstance(evidence_class, str) or not evidence_class or len(evidence_class) > 128:
        raise ValueError("evidence_class must be a non-empty string of at most 128 characters")
    if status not in STATUSES:
        raise ValueError("unknown evidence status")
    return {
        "node_id": node_id_for(node_type, identity),
        "node_type": node_type,
        "identity": dict(identity),
        "record_sha256": record_sha256,
        "evidence_class": evidence_class,
        "status": status,
    }


def _validate_node(node: Any) -> dict[str, Any]:
    required = {"node_id", "node_type", "identity", "record_sha256", "evidence_class", "status"}
    if not isinstance(node, dict) or set(node) != required:
        raise ValueError("node must contain exactly the v1 node fields")
    expected_id = node_id_for(node["node_type"], node["identity"])
    if node["node_id"] != expected_id:
        raise ValueError("node_id does not match the complete node identity")
    _require_digest(node["record_sha256"], "record_sha256")
    if not isinstance(node["evidence_class"], str) or not node["evidence_class"] or len(node["evidence_class"]) > 128:
        raise ValueError("evidence_class must be a non-empty string of at most 128 characters")
    if node["status"] not in STATUSES:
        raise ValueError("unknown evidence status")
    return dict(node)


def _validate_edge(edge: Any) -> dict[str, str]:
    required = {"dependent_node_id", "prerequisite_node_id", "relation"}
    if not isinstance(edge, dict) or set(edge) != required:
        raise ValueError("edge must contain exactly the v1 edge fields")
    for field in ("dependent_node_id", "prerequisite_node_id"):
        value = edge[field]
        if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
            raise ValueError(f"{field} must be a node SHA-256 identity")
    if edge["relation"] not in RELATIONS:
        raise ValueError("unknown evidence edge relation")
    if edge["dependent_node_id"] == edge["prerequisite_node_id"]:
        raise ValueError("self-dependency is not allowed")
    return dict(edge)


def _topological_order(nodes: list[dict[str, Any]], edges: list[dict[str, str]]) -> list[str]:
    """Return prerequisite-first order; reject every directed cycle."""
    node_ids = {node["node_id"] for node in nodes}
    indegree = {node_id: 0 for node_id in node_ids}
    dependents: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        dependent = edge["dependent_node_id"]
        prerequisite = edge["prerequisite_node_id"]
        if dependent not in node_ids or prerequisite not in node_ids:
            raise ValueError("edge references an unknown node")
        if dependent in dependents[prerequisite]:
            # Distinct relation labels for the same pair are permitted; the
            # adjacency is unique for cycle detection and status propagation.
            continue
        dependents[prerequisite].add(dependent)
        indegree[dependent] += 1

    ready = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    ordered: list[str] = []
    while ready:
        prerequisite = ready.popleft()
        ordered.append(prerequisite)
        for dependent in sorted(dependents[prerequisite]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    if len(ordered) != len(node_ids):
        raise ValueError("evidence dependency graph contains a cycle")
    return ordered


def build_snapshot(
    nodes: Iterable[Mapping[str, Any]], edges: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate, deterministically sort, and hash a v1 evidence snapshot."""
    validated_nodes = [_validate_node(dict(node)) for node in nodes]
    validated_edges = [_validate_edge(dict(edge)) for edge in edges]
    node_ids = [node["node_id"] for node in validated_nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("duplicate evidence node identity")
    edge_keys = [
        (edge["dependent_node_id"], edge["prerequisite_node_id"], edge["relation"])
        for edge in validated_edges
    ]
    if len(edge_keys) != len(set(edge_keys)):
        raise ValueError("duplicate evidence edge")
    _topological_order(validated_nodes, validated_edges)
    validated_nodes.sort(key=lambda node: node["node_id"])
    validated_edges.sort(key=lambda edge: (
        edge["dependent_node_id"], edge["prerequisite_node_id"], edge["relation"],
    ))
    snapshot = {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "nodes": validated_nodes,
        "edges": validated_edges,
    }
    snapshot["snapshot_sha256"] = _sha256(canonical_json(snapshot))
    return snapshot


def validate_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Revalidate a snapshot envelope and its digest; return canonical form."""
    if not isinstance(snapshot, Mapping):
        raise ValueError("snapshot must be an object")
    if set(snapshot) != {"schema", "authority", "nodes", "edges", "snapshot_sha256"}:
        raise ValueError("snapshot must contain exactly the v1 envelope fields")
    if snapshot["schema"] != SCHEMA or snapshot["authority"] != AUTHORITY:
        raise ValueError("unsupported qualification evidence snapshot")
    if not isinstance(snapshot["nodes"], list) or not isinstance(snapshot["edges"], list):
        raise ValueError("snapshot nodes and edges must be arrays")
    rebuilt = build_snapshot(snapshot["nodes"], snapshot["edges"])
    _require_digest(snapshot["snapshot_sha256"], "snapshot_sha256")
    if rebuilt["snapshot_sha256"] != snapshot["snapshot_sha256"]:
        raise ValueError("snapshot SHA-256 does not match canonical contents")
    return rebuilt


def prerequisite_first_order(snapshot: Mapping[str, Any]) -> list[str]:
    validated = validate_snapshot(snapshot)
    return _topological_order(validated["nodes"], validated["edges"])


def transitive_dependents(
    snapshot: Mapping[str, Any], changed_node_ids: Iterable[str],
) -> list[str]:
    """Return only downstream dependents invalidated by changed prerequisites."""
    validated = validate_snapshot(snapshot)
    known = {node["node_id"] for node in validated["nodes"]}
    seeds = set(changed_node_ids)
    if not seeds or not seeds.issubset(known):
        raise ValueError("changed node IDs must be a non-empty subset of the snapshot")
    reverse: dict[str, set[str]] = defaultdict(set)
    for edge in validated["edges"]:
        reverse[edge["prerequisite_node_id"]].add(edge["dependent_node_id"])
    invalidated: set[str] = set()
    pending = deque(sorted(seeds))
    while pending:
        prerequisite = pending.popleft()
        for dependent in sorted(reverse[prerequisite]):
            if dependent not in seeds and dependent not in invalidated:
                invalidated.add(dependent)
                pending.append(dependent)
    return sorted(invalidated)


def derive_statuses(snapshot: Mapping[str, Any]) -> dict[str, str]:
    """Propagate prerequisite failures without allowing graph connectivity to qualify."""
    validated = validate_snapshot(snapshot)
    nodes = {node["node_id"]: node for node in validated["nodes"]}
    prerequisites: dict[str, set[str]] = defaultdict(set)
    for edge in validated["edges"]:
        prerequisites[edge["dependent_node_id"]].add(edge["prerequisite_node_id"])
    statuses: dict[str, str] = {}
    for node_id in _topological_order(validated["nodes"], validated["edges"]):
        own = nodes[node_id]["status"]
        dependency_statuses = [statuses[item] for item in prerequisites[node_id]]
        statuses[node_id] = max([own, *dependency_statuses], key=_STATUS_RANK.__getitem__)
    return statuses
