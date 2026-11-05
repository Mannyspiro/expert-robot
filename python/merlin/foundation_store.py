"""Unified registry + knowledge graph facade for Merlin foundation.

The registry owns immutable artifact bytes and project inventory. The graph owns
typed semantic relationships. This facade writes the corresponding records to
both stores and exposes an explicit reconciliation report; it is not a
distributed transaction across the two SQLite databases.
"""
from __future__ import annotations

import hashlib
import json
import hashlib
from pathlib import Path
from typing import Any

from .knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph
from .project_registry import MerlinRegistry


class MerlinFoundationStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry = MerlinRegistry(self.root / "registry")
        self.graph = MerlinKnowledgeGraph(self.root / "knowledge-graph.sqlite3")

    def register_project(self, project_id: str, name: str, version: str = "0.1.0",
                         metadata: dict[str, Any] | None = None) -> None:
        payload = metadata or {}
        self.registry.register_project(project_id, name, version, payload)
        self.graph.add_node(GraphNode(
            node_id=f"project:{project_id}", node_type="project", label=name,
            payload={"version": version, **payload}, evidence_class="registry",
        ))

    def put_artifact(self, project_id: str, logical_path: str, content: bytes,
                     media_type: str = "application/octet-stream",
                     artifact_type: str = "artifact",
                     evidence_class: str = "unreviewed",
                     metadata: dict[str, Any] | None = None) -> str:
        if artifact_type not in {"artifact", "source", "dataset", "model", "simulation",
                                 "cad_model", "media", "theorem", "equation"}:
            raise ValueError(f"unsupported artifact graph type: {artifact_type}")
        digest = self.registry.put_artifact(project_id, logical_path, content, media_type)
        artifact_id = f"artifact:sha256:{digest}"
        project_node_id = f"project:{project_id}"

        # The content node is content-addressed and therefore cannot contain
        # path-specific provenance. Multiple archive members may resolve to the
        # same digest while retaining distinct logical paths and source metadata.
        if self.graph.get_node(project_node_id) is None:
            inventory = self.registry.inventory(project_id)
            self.graph.add_node(GraphNode(
                project_node_id, "project", inventory["name"],
                {"version": inventory["version"]}, "registry",
            ))

        content_node = self.graph.get_node(artifact_id)
        if content_node is None:
            self.graph.add_node(GraphNode(
                artifact_id, "artifact", f"sha256:{digest}",
                {"sha256": digest, "size_bytes": len(content)},
                "unreviewed",
            ))
        elif (content_node.payload.get("sha256") != digest
              or content_node.payload.get("size_bytes") != len(content)):
            raise ValueError("content-addressed graph node does not match verified blob")

        reference_digest = hashlib.sha256(
            f"{project_id}\0{logical_path}".encode("utf-8")
        ).hexdigest()
        reference_id = f"artifact-ref:{reference_digest}"
        self.graph.add_node(GraphNode(
            reference_id, "artifact_reference", logical_path,
            {
                "project_id": project_id,
                "logical_path": logical_path,
                "artifact_sha256": digest,
                "media_type": media_type,
                "size_bytes": len(content),
                "artifact_type": artifact_type,
                "metadata": metadata or {},
            },
            evidence_class,
        ))

        # Keep the direct project->content edge for existing graph consumers;
        # its payload is stable and contains no path-specific fields.
        direct_edges = self.graph.neighbors(project_node_id, "out")
        if not any(edge["relation"] == "contains" and edge["target_id"] == artifact_id
                   for edge in direct_edges):
            self.graph.add_edge(GraphEdge(project_node_id, "contains", artifact_id, {}))
        self.graph.add_edge(GraphEdge(
            project_node_id, "contains", reference_id, {"logical_path": logical_path}
        ))
        self.graph.add_edge(GraphEdge(
            reference_id, "uses", artifact_id, {"sha256": digest}
        ))
        return digest

    def add_claim(self, claim_id: str, statement: str, evidence_class: str,
                  assumptions: tuple[str, ...] = (), status: str = "unreviewed",
                  project_id: str | None = None,
                  evidence_artifact_digests: tuple[str, ...] = ()) -> None:
        self.registry.add_claim(claim_id, statement, evidence_class, assumptions, status)
        self.graph.add_node(GraphNode(
            f"claim:{claim_id}", "claim", statement,
            {"assumptions": list(assumptions), "status": status}, evidence_class,
        ))
        if project_id:
            project_node_id = f"project:{project_id}"
            if self.graph.get_node(project_node_id) is None:
                inventory = self.registry.inventory(project_id)
                self.graph.add_node(GraphNode(project_node_id, "project", inventory["name"],
                                              {"version": inventory["version"]}, "registry"))
            self.graph.add_edge(GraphEdge(project_node_id, "contains", f"claim:{claim_id}", {}))
        for digest in evidence_artifact_digests:
            if not self.registry.verify_artifact(digest):
                raise ValueError(f"evidence artifact failed integrity check: {digest}")
            artifact_id = f"artifact:sha256:{digest}"
            if self.graph.get_node(artifact_id) is None:
                raise ValueError(f"evidence artifact is not represented in graph: {digest}")
            self.graph.add_edge(GraphEdge(artifact_id, "supports", f"claim:{claim_id}",
                                          {"integrity_verified_at_link_time": True}))

    def reconcile_project(self, project_id: str) -> dict[str, Any]:
        inventory = self.registry.inventory(project_id)
        project_node_id = f"project:{project_id}"
        graph_project = self.graph.get_node(project_node_id)
        missing_artifacts = []
        missing_references = []
        missing_reference_edges = []
        corrupt_artifacts = []
        expected_reference_ids = set()

        for artifact in inventory["artifacts"]:
            digest = artifact["digest"]
            logical_path = artifact["logical_path"]
            node_id = f"artifact:sha256:{digest}"
            reference_digest = hashlib.sha256(
                f"{project_id}\0{logical_path}".encode("utf-8")
            ).hexdigest()
            reference_id = f"artifact-ref:{reference_digest}"
            expected_reference_ids.add(reference_id)

            if self.graph.get_node(node_id) is None:
                missing_artifacts.append(logical_path)
            if self.graph.get_node(reference_id) is None:
                missing_references.append(logical_path)
            else:
                reference_edges = self.graph.neighbors(reference_id, "out")
                if not any(edge["relation"] == "uses" and edge["target_id"] == node_id
                           for edge in reference_edges):
                    missing_reference_edges.append(logical_path)
            if not self.registry.verify_artifact(digest):
                corrupt_artifacts.append(logical_path)

        graph_edges = self.graph.neighbors(project_node_id, "out") if graph_project else []
        contained = {edge["target_id"] for edge in graph_edges if edge["relation"] == "contains"}
        expected = {f"artifact:sha256:{a['digest']}" for a in inventory["artifacts"]}
        missing_contains = sorted(expected - contained)
        return {
            "project_id": project_id,
            "registry_artifact_count": len(inventory["artifacts"]),
            "graph_project_present": graph_project is not None,
            "graph_artifact_missing": missing_artifacts,
            "graph_artifact_reference_missing": missing_references,
            "graph_artifact_reference_edges_missing": missing_reference_edges,
            "blob_integrity_failures": corrupt_artifacts,
            "missing_contains_edges": missing_contains,
            "consistent": graph_project is not None and not missing_artifacts
                          and not missing_references and not missing_reference_edges
                          and not corrupt_artifacts and not missing_contains,
        }

    def export_snapshot(self) -> dict[str, Any]:
        return self.graph.export_snapshot()
