"""Connect real Engineering IR revisions and object views to proof evidence.

This is a provenance bridge, not a scientific or engineering certification layer.
It requires existing, revision-bound object-view nodes before linking a benchmark
receipt to theorem-DAG nodes.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import re
from typing import Any, Iterable

from merlin.engineering_project_store import EngineeringProjectStore, project_hash
from merlin.knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph
from merlin.observatory_integrity import verify_theorem_dag
from merlin.proof_observatory import ProofObservatory, canonical_json, sha256_text


def _stable_id(prefix: str, *parts: object) -> str:
    material = "|".join(str(part) for part in parts)
    return prefix + ":" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def _revision_snapshot(project_store: EngineeringProjectStore, project_id: str,
                       revision: int | None) -> tuple[Any, int, str]:
    history = project_store.history(project_id)
    if not history or not project_store.verify_history(project_id):
        raise ValueError("engineering project history is missing or fails hash-chain verification")
    selected_revision = history[-1]["revision"] if revision is None else revision
    row = next((item for item in history if item["revision"] == selected_revision), None)
    if row is None:
        raise KeyError((project_id, selected_revision))
    project = project_store.load(project_id, selected_revision)
    digest = project_hash(project)
    if digest != row["content_hash"]:
        raise ValueError("engineering revision content hash does not match its stored receipt")
    return project, selected_revision, digest


def _add_immutable_node(graph: MerlinKnowledgeGraph, node: GraphNode) -> None:
    existing = graph.get_node(node.node_id)
    if existing is not None:
        if (existing.node_type != node.node_type or existing.label != node.label
                or existing.payload != node.payload):
            raise ValueError("graph node ID already exists with different content: " + node.node_id)
        return
    graph.add_node(node)


def _revision_node_id(project_id: str, revision: int) -> str:
    return _stable_id("engineering-project-revision", project_id, revision)


def register_engineering_revision_views(
    graph: MerlinKnowledgeGraph,
    project_store: EngineeringProjectStore,
    project_id: str,
    revision: int | None = None,
) -> dict[str, Any]:
    """Project one verified Engineering IR revision into immutable Knowledge Graph views."""
    project, selected_revision, digest = _revision_snapshot(project_store, project_id, revision)
    project_node_id = _revision_node_id(project_id, selected_revision)
    _add_immutable_node(graph, GraphNode(
        node_id=project_node_id,
        node_type="project",
        label=project.name,
        payload={
            "engineering_project_id": project_id,
            "engineering_revision": selected_revision,
            "engineering_revision_sha256": digest,
            "units": project.units,
            "part_count": len(project.parts),
            "net_count": len(project.nets),
        },
        evidence_class="structured_engineering_ir",
    ))

    part_ids: dict[str, str] = {}
    for part in sorted(project.parts, key=lambda item: item.ref):
        node_id = _stable_id("object-view-part", project_id, selected_revision, part.ref)
        payload = {
            "engineering_project_id": project_id,
            "engineering_revision": selected_revision,
            "engineering_revision_sha256": digest,
            "object_kind": "part",
            "part": asdict(part),
        }
        _add_immutable_node(graph, GraphNode(
            node_id=node_id, node_type="object_view",
            label=f"{part.ref} — {part.name}", payload=payload,
            evidence_class="structured_engineering_ir",
        ))
        graph.add_edge(GraphEdge(project_node_id, "contains", node_id, {
            "engineering_revision_sha256": digest, "object_kind": "part",
        }))
        part_ids[part.ref] = node_id

    net_ids: dict[str, str] = {}
    for net in sorted(project.nets, key=lambda item: item.name):
        node_id = _stable_id("object-view-net", project_id, selected_revision, net.name)
        payload = {
            "engineering_project_id": project_id,
            "engineering_revision": selected_revision,
            "engineering_revision_sha256": digest,
            "object_kind": "net",
            "net": asdict(net),
        }
        _add_immutable_node(graph, GraphNode(
            node_id=node_id, node_type="object_view",
            label=f"Net — {net.name}", payload=payload,
            evidence_class="structured_engineering_ir",
        ))
        graph.add_edge(GraphEdge(project_node_id, "contains", node_id, {
            "engineering_revision_sha256": digest, "object_kind": "net",
        }))
        net_ids[net.name] = node_id

    return {
        "project_node_id": project_node_id,
        "project_id": project_id,
        "revision": selected_revision,
        "revision_sha256": digest,
        "part_object_views": part_ids,
        "net_object_views": net_ids,
    }


def register_representation_graph_views(
    graph: MerlinKnowledgeGraph,
    representation_graph: object,
    *,
    project_id: str,
    revision: int,
    revision_sha256: str,
    project_node_id: str,
) -> dict[str, str]:
    """Register coordinate frames as object views bound to one Engineering IR revision."""
    project_node = graph.get_node(project_node_id)
    if project_node is None or project_node.node_type != "project":
        raise KeyError("engineering project revision node is not registered")
    expected = (project_id, revision, revision_sha256)
    actual = (
        project_node.payload.get("engineering_project_id"),
        project_node.payload.get("engineering_revision"),
        project_node.payload.get("engineering_revision_sha256"),
    )
    if actual != expected:
        raise ValueError("project node does not match the requested Engineering IR revision")
    frames = getattr(representation_graph, "frames", None)
    if not isinstance(frames, dict) or not frames:
        raise TypeError("representation_graph must expose a non-empty frames mapping")

    result: dict[str, str] = {}
    for frame_id, frame in sorted(frames.items()):
        matrix = getattr(frame, "canonical_to_frame", None)
        if matrix is None:
            raise TypeError("representation frame is missing canonical_to_frame")
        node_id = _stable_id("object-view-frame", project_id, revision, frame_id)
        payload = {
            "engineering_project_id": project_id,
            "engineering_revision": revision,
            "engineering_revision_sha256": revision_sha256,
            "object_kind": "coordinate_frame",
            "frame_id": frame_id,
            "dimension": len(matrix),
            "canonical_to_frame": [[str(value) for value in row] for row in matrix],
        }
        _add_immutable_node(graph, GraphNode(
            node_id=node_id, node_type="object_view",
            label=f"Coordinate frame — {frame_id}", payload=payload,
            evidence_class="exact_representation_graph",
        ))
        graph.add_edge(GraphEdge(project_node_id, "contains", node_id, {
            "engineering_revision_sha256": revision_sha256,
            "object_kind": "coordinate_frame",
        }))
        result[frame_id] = node_id
    return result


def _validate_receipt(receipt: dict[str, Any]) -> str:
    if receipt.get("schema") != "merlin-cross-domain-benchmark-receipt-v1":
        raise ValueError("unsupported benchmark receipt schema")
    supplied = receipt.get("receipt_sha256")
    payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if supplied != sha256_text(canonical_json(payload)):
        raise ValueError("benchmark receipt SHA-256 mismatch")
    if not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("source_commit", ""))):
        raise ValueError("benchmark receipt source commit is invalid")
    if not isinstance(receipt.get("domains"), dict):
        raise ValueError("benchmark receipt domains are required")
    return supplied


def link_observatory_to_graph(
    graph: MerlinKnowledgeGraph,
    project_store: EngineeringProjectStore,
    observatory: ProofObservatory,
    receipt: dict[str, Any],
    theorem_dag: dict[str, Any],
    *,
    project_id: str,
    revision: int,
    object_view_ids_by_domain: dict[str, Iterable[str]],
) -> dict[str, Any]:
    """Bind verified evidence to actual graph nodes and an exact Engineering IR revision."""
    _, selected_revision, revision_sha256 = _revision_snapshot(project_store, project_id, revision)
    if selected_revision != revision:
        raise ValueError("requested Engineering IR revision did not resolve exactly")
    project_node_id = _revision_node_id(project_id, revision)
    project_node = graph.get_node(project_node_id)
    if project_node is None or project_node.node_type != "project":
        raise KeyError("Engineering IR revision has not been registered in the Knowledge Graph")
    project_binding = (
        project_node.payload.get("engineering_project_id"),
        project_node.payload.get("engineering_revision"),
        project_node.payload.get("engineering_revision_sha256"),
    )
    if project_binding != (project_id, revision, revision_sha256):
        raise ValueError("Knowledge Graph project node does not match the exact Engineering IR revision")

    normalized_object_ids: dict[str, tuple[str, ...]] = {}
    for domain, values in object_view_ids_by_domain.items():
        if isinstance(values, (str, bytes)):
            raise TypeError("each object-view domain must map to an iterable of IDs, not one string")
        ids = tuple(values)
        if any(not isinstance(item, str) or not item.strip() for item in ids):
            raise ValueError("object-view IDs must be non-empty strings")
        normalized_object_ids[domain] = tuple(dict.fromkeys(ids))

    snapshot = graph.export_snapshot()
    snapshot_payload = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    snapshot_hash = sha256_text(json.dumps(
        snapshot_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ))
    if snapshot.get("snapshot_sha256") != snapshot_hash:
        raise ValueError("Knowledge Graph snapshot integrity check failed")

    receipt_hash = _validate_receipt(receipt)
    dag_errors = verify_theorem_dag(theorem_dag)
    if dag_errors:
        raise ValueError("theorem DAG failed integrity checks: " + "; ".join(dag_errors))

    mapping = {
        "geometry": ("geometry",),
        "xmg": (),
        "equation_atlas": (),
        "cad": ("manufacturing", "electrical", "thermal"),
    }
    nodes = theorem_dag["nodes"]
    expected_links: list[tuple[str, str, str]] = []
    for domain, benchmark in receipt["domains"].items():
        if not isinstance(benchmark, dict) or benchmark.get("passed") is not True:
            continue
        object_ids = normalized_object_ids.get(domain, ())
        for object_id in object_ids:
            object_node = graph.get_node(object_id)
            if object_node is None or object_node.node_type != "object_view":
                raise KeyError("unknown or non-object-view graph node: " + str(object_id))
            binding = object_node.payload
            if (
                binding.get("engineering_project_id") != project_id
                or binding.get("engineering_revision") != revision
                or binding.get("engineering_revision_sha256") != revision_sha256
            ):
                raise ValueError("object view is not bound to the exact Engineering IR revision: " + object_id)
        for theorem in nodes:
            tags = set(theorem.get("tags", []))
            matches = theorem.get("domain") in mapping.get(domain, ())
            if domain == "xmg":
                matches = "xmg" in tags or "glyph" in tags
            elif domain == "equation_atlas":
                matches = matches or "equation_atlas" in tags
            if matches:
                graph._validate_id(theorem["id"])
                existing = graph.get_node(theorem["id"])
                if existing is not None and existing.node_type != "theorem":
                    raise ValueError("theorem ID is occupied by a non-theorem graph node")
                for object_id in object_ids:
                    expected_links.append((theorem["id"], object_id, domain))

    if not expected_links:
        raise ValueError("no passed benchmark domain maps to a registered object view and theorem")

    # All external references are checked before either evidence store is mutated.
    link_ids = observatory.record_benchmark_theorem_links(
        receipt, theorem_dag, project_id, revision_sha256, normalized_object_ids,
    )
    for theorem_id, object_id, domain in expected_links:
        theorem = next(node for node in nodes if node["id"] == theorem_id)
        if graph.get_node(theorem_id) is None:
            graph.add_node(GraphNode(
                node_id=theorem_id, node_type="theorem", label=theorem_id,
                payload={
                    "theorem_id": theorem_id,
                    "domain": theorem.get("domain", "unspecified"),
                    "registry_status": theorem.get("status", "unclassified"),
                    "source": theorem.get("source"),
                    "source_sha256": theorem.get("source_sha256"),
                    "surface_statement_sha256": (
                        theorem.get("lean_surface_declaration") or {}
                    ).get("surface_statement_sha256"),
                    "formal_qualification_required": True,
                },
                evidence_class="candidate",
            ))
        graph.add_edge(GraphEdge(object_id, "tests", theorem_id, {
            "benchmark_domain": domain,
            "benchmark_receipt_sha256": receipt_hash,
            "source_commit": receipt["source_commit"],
            "engineering_project_id": project_id,
            "engineering_revision": revision,
            "engineering_revision_sha256": revision_sha256,
            "theorem_dag_sha256": theorem_dag["dag_sha256"],
        }))

    final_snapshot = graph.export_snapshot()
    return {
        "project_node_id": project_node_id,
        "engineering_revision": revision,
        "engineering_revision_sha256": revision_sha256,
        "benchmark_receipt_sha256": receipt_hash,
        "theorem_dag_sha256": theorem_dag["dag_sha256"],
        "observatory_link_count": len(link_ids),
        "knowledge_graph_edge_count": len(expected_links),
        "knowledge_graph_snapshot_sha256": final_snapshot["snapshot_sha256"],
        "qualification_claim": "evidence linked; theorem and engineering claims remain separately qualified",
    }
