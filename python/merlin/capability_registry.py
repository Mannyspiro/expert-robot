"""Canonical capability-state projection and bounded graph validation.

Capability state is deliberately three-valued: configured is not the same as
qualified, and unavailable is not silently promoted by a declaration alone.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

SCHEMA = "merlin-capability-registry/1"
VALID_STATES = {"configured", "unavailable", "unqualified"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _legacy_state(row: Mapping[str, Any], runtime: Mapping[str, Any],
                  outbox_configured: bool) -> str:
    ident = row.get("id")
    legacy = str(row.get("status", "")).upper()
    if ident == "model.remote_openai_compatible":
        state = runtime.get("providers", {}).get("cloud", {}).get("status")
        return "configured" if state == "QUALIFIED_CONFIGURED" else "unqualified"
    if ident == "model.nouscoder":
        state = runtime.get("providers", {}).get("local", {}).get("status")
        return "configured" if state == "QUALIFIED_CONFIGURED" else "unqualified"
    if ident == "voice.kokoro":
        state = runtime.get("providers", {}).get("speech_output", {}).get("status")
        return "configured" if state == "QUALIFIED_CONFIGURED" else "unavailable"
    if legacy == "AVAILABLE_WITH_OUTBOX":
        return "configured" if outbox_configured else "unavailable"
    if legacy in {"AVAILABLE", "CONFIGURED"}:
        return "configured"
    if legacy in {"QUALIFICATION_GATED", "NOT_QUALIFIED"}:
        return "unqualified"
    if legacy in {"CONFIGURED_AT_RUNTIME"}:
        return "unqualified"
    return "unavailable"


def capability_snapshot(rows: Sequence[Mapping[str, Any]],
                        runtime: Mapping[str, Any] | None = None,
                        outbox_configured: bool = False) -> dict[str, Any]:
    runtime = runtime or {}
    records = []
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("capability declarations must be objects")
        ident = row.get("id")
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            raise ValueError("capability IDs must be non-empty and unique")
        seen.add(ident)
        state = _legacy_state(row, runtime, outbox_configured)
        records.append({
            "id": ident,
            "state": state,
            "evidence": str(row.get("evidence", "No qualification evidence recorded.")),
            "provider": row.get("provider"),
            "authority": "declaration_and_runtime_configuration_only",
        })
    records.sort(key=lambda item: item["id"])
    payload = {"schema": SCHEMA, "states": sorted(VALID_STATES),
               "capabilities": records}
    payload["registry_sha256"] = sha256(_canonical(payload)).hexdigest()
    return payload


def validate_graph(graph: Mapping[str, Any], max_nodes: int = 5000,
                   max_edges: int = 20000) -> dict[str, Any]:
    """Validate graph references and acyclicity for prerequisite/dependency edges."""
    if not isinstance(graph, Mapping):
        raise ValueError("graph must be an object")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("graph.nodes and graph.edges must be lists")
    if len(nodes) > max_nodes or len(edges) > max_edges:
        raise ValueError("graph exceeds configured size limits")

    errors: list[dict[str, str]] = []
    node_ids: list[str] = []
    node_set: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            errors.append({"code": "invalid_node", "path": f"nodes[{index}]"})
            continue
        ident = node.get("id")
        if not isinstance(ident, str) or not ident.strip():
            errors.append({"code": "missing_node_id", "path": f"nodes[{index}]"})
            continue
        if ident in node_set:
            errors.append({"code": "duplicate_node_id", "path": f"nodes[{index}]"})
            continue
        node_ids.append(ident)
        node_set.add(ident)

    adjacency: dict[str, set[str]] = {ident: set() for ident in node_ids}
    indegree: dict[str, int] = {ident: 0 for ident in node_ids}
    for index, edge in enumerate(edges):
        if not isinstance(edge, Mapping):
            errors.append({"code": "invalid_edge", "path": f"edges[{index}]"})
            continue
        source, target = edge.get("source"), edge.get("target")
        relation = edge.get("relation", "related")
        if source not in node_set or target not in node_set:
            errors.append({"code": "dangling_edge", "path": f"edges[{index}]"})
            continue
        if not isinstance(relation, str) or not relation.strip():
            errors.append({"code": "invalid_relation", "path": f"edges[{index}]"})
            continue
        if relation in {"prerequisite", "depends_on", "requires"} and target not in adjacency[source]:
            adjacency[source].add(target)
            indegree[target] += 1

    # A topological order exists only when the directed prerequisite graph is acyclic.
    queue = sorted(ident for ident, degree in indegree.items() if degree == 0)
    topology: list[str] = []
    while queue:
        current = queue.pop(0)
        topology.append(current)
        for target in sorted(adjacency[current]):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
                queue.sort()
    if len(topology) != len(node_ids):
        errors.append({"code": "dependency_cycle", "path": "edges"})

    payload = {"schema": "merlin-graph-validation/1",
               "valid": not errors, "node_count": len(nodes),
               "edge_count": len(edges), "topological_order": topology if not errors else [],
               "errors": errors}
    payload["graph_sha256"] = sha256(_canonical({
        "nodes": nodes, "edges": edges
    })).hexdigest()
    return payload
