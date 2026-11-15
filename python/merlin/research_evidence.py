"""Bind exact registry artifacts to hypotheses and graph evidence without copying bytes."""
from __future__ import annotations

from typing import Any, Mapping
import hashlib

from merlin.artifact_ref import ArtifactRef
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry


_RELATION = {
    "source": "derived_from",
    "counterexample": "contradicts",
    "experiment": "tests",
    "proof": "formalizes",
    "assumption": "depends_on",
}


class ResearchEvidenceRecorder:
    """Persist new evidence or attach an already stored ArtifactRef to a hypothesis."""

    def __init__(self, registry: MerlinRegistry, ledger: HypothesisLedger,
                 graph: MerlinKnowledgeGraph):
        self.registry = registry
        self.ledger = ledger
        self.graph = graph

    def _record_verified_ref(
        self,
        *,
        project_id: str,
        hypothesis_id: str,
        artifact_ref: Mapping[str, Any],
        evidence_kind: str,
        description: str,
        source_url: str = "",
        graph_node_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id is required")
        if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
            raise ValueError("hypothesis_id is required")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("evidence description is required")
        if not isinstance(source_url, str):
            raise ValueError("source_url must be text")
        hypothesis = self.ledger.get(hypothesis_id)
        if evidence_kind not in _RELATION:
            raise ValueError("unsupported research evidence kind")
        ref = ArtifactRef.from_mapping(artifact_ref).to_dict()
        if ref["project_id"] != project_id:
            raise ValueError("evidence ArtifactRef must belong to the requested project")
        resolution = self.registry.resolve_artifact_ref(ref)
        if resolution.get("verified") is not True:
            raise RuntimeError("research evidence ArtifactRef failed canonical registry resolution")
        digest = ref["sha256"]

        if graph_node_id is not None:
            if not isinstance(graph_node_id, str) or not graph_node_id.strip():
                raise ValueError("graph_node_id must be non-empty text")
            existing_node = self.graph.get_node(graph_node_id)
            if existing_node is None:
                raise ValueError("provided graph_node_id does not exist")
            existing_payload = existing_node.payload
            if not isinstance(existing_payload, Mapping) or existing_payload.get("artifact_ref") != ref:
                raise ValueError("provided graph node is not bound to the exact ArtifactRef")

        # Sequential retries of the same leased task must not append duplicate
        # ledger evidence. The outbox lease prevents concurrent ownership.
        normalized_url = source_url.strip()
        if normalized_url and not normalized_url.startswith("https://"):
            raise ValueError("source_url must use HTTPS")
        evidence = next((
            item for item in self.ledger.evidence(hypothesis_id)
            if item.kind == evidence_kind
            and item.description == description.strip()
            and item.source_url == normalized_url
            and item.artifact_hash == digest
        ), None)
        if evidence is None:
            evidence = self.ledger.add_evidence(
                hypothesis_id, evidence_kind, description,
                source_url=normalized_url, artifact_hash=digest,
            )

        claim_node_id = "hypothesis:" + hashlib.sha256(
            hypothesis_id.encode("utf-8")
        ).hexdigest()[:32]

        if graph_node_id is not None:
            artifact_node_id = graph_node_id
        else:
            artifact_identity = (
                project_id + "|" + ref["logical_path"] + "|"
                + str(ref["version"]) + "|" + digest
            )
            artifact_node_id = "artifact:" + hashlib.sha256(
                artifact_identity.encode("utf-8")
            ).hexdigest()[:32]
            self.graph.add_node(GraphNode(
                artifact_node_id, "artifact", ref["logical_path"],
                {
                    "sha256": digest,
                    "project_id": project_id,
                    "logical_path": ref["logical_path"],
                    "artifact_ref": ref,
                    "evidence_kind": evidence_kind,
                    "size_bytes": resolution["size_bytes"],
                    "media_type": resolution.get("media_type"),
                },
                evidence_class=evidence_kind,
                source_uri=normalized_url or "registry://sha256/" + digest,
            ))

        self.graph.add_node(GraphNode(
            claim_node_id, "claim", hypothesis.claim,
            {
                "hypothesis_id": hypothesis_id,
                "mathematical_objects": list(hypothesis.mathematical_objects),
                "relation": hypothesis.relation,
                "assumptions": list(hypothesis.assumptions),
            },
            evidence_class="hypothesis",
        ))
        self.graph.add_edge(GraphEdge(
            artifact_node_id, _RELATION[evidence_kind], claim_node_id,
            {
                "hypothesis_id": hypothesis_id,
                "evidence_id": evidence.evidence_id,
                "artifact_sha256": digest,
                "artifact_ref": ref,
                "evidence_kind": evidence_kind,
            },
        ))
        return {
            "schema": "merlin-research-evidence/1",
            "hypothesis_id": hypothesis_id,
            "evidence_id": evidence.evidence_id,
            "evidence_kind": evidence_kind,
            "artifact_sha256": digest,
            "artifact_ref": ref,
            "artifact_verified": True,
            "size_bytes": resolution["size_bytes"],
            "media_type": resolution.get("media_type"),
            "graph_edge": {
                "source_id": artifact_node_id,
                "relation": _RELATION[evidence_kind],
                "target_id": claim_node_id,
            },
            "hypothesis_status_unchanged": self.ledger.get(hypothesis_id).status == hypothesis.status,
        }

    def record_existing_artifact(
        self,
        *,
        project_id: str,
        hypothesis_id: str,
        artifact_ref: Mapping[str, Any],
        evidence_kind: str,
        description: str,
        source_url: str = "",
        graph_node_id: str | None = None,
    ) -> dict[str, Any]:
        """Attach an existing verified ArtifactRef without copying or re-storing bytes."""
        return self._record_verified_ref(
            project_id=project_id,
            hypothesis_id=hypothesis_id,
            artifact_ref=artifact_ref,
            evidence_kind=evidence_kind,
            description=description,
            source_url=source_url,
            graph_node_id=graph_node_id,
        )

    def record(self, *, project_id: str, hypothesis_id: str, logical_path: str,
               content: bytes, evidence_kind: str, description: str,
               source_url: str = "") -> dict[str, Any]:
        """Store immutable evidence bytes, then attach that exact ArtifactRef."""
        if not isinstance(content, bytes) or not content:
            raise ValueError("research evidence content must be non-empty immutable bytes")
        self.ledger.get(hypothesis_id)
        digest = self.registry.put_artifact(project_id, logical_path, content)
        artifact_ref = self.registry.artifact_ref(project_id, logical_path)
        if artifact_ref["sha256"] != digest:
            raise RuntimeError("registry returned an ArtifactRef for a different artifact digest")
        return self._record_verified_ref(
            project_id=project_id,
            hypothesis_id=hypothesis_id,
            artifact_ref=artifact_ref,
            evidence_kind=evidence_kind,
            description=description,
            source_url=source_url,
        )


__all__ = ["ResearchEvidenceRecorder"]
