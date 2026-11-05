"""Bind research outputs to registry artifacts, hypotheses and graph evidence."""
from __future__ import annotations

from typing import Any

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
    """Persist immutable output bytes and link them to one canonical hypothesis."""

    def __init__(self, registry: MerlinRegistry, ledger: HypothesisLedger,
                 graph: MerlinKnowledgeGraph):
        self.registry = registry
        self.ledger = ledger
        self.graph = graph

    def record(self, *, project_id: str, hypothesis_id: str, logical_path: str,
               content: bytes, evidence_kind: str, description: str,
               source_url: str = "") -> dict[str, Any]:
        hypothesis = self.ledger.get(hypothesis_id)
        digest = self.registry.put_artifact(project_id, logical_path, content)
        evidence = self.ledger.add_evidence(
            hypothesis_id, evidence_kind, description,
            source_url=source_url, artifact_hash=digest,
        )
        claim_node_id = "hypothesis:" + hypothesis_id
        artifact_node_id = "artifact:" + digest
        self.graph.add_node(GraphNode(
            claim_node_id, "claim", hypothesis.claim,
            {"hypothesis_id": hypothesis_id,
             "mathematical_objects": list(hypothesis.mathematical_objects),
             "relation": hypothesis.relation,
             "assumptions": list(hypothesis.assumptions)},
            evidence_class="hypothesis",
        ))
        self.graph.add_node(GraphNode(
            artifact_node_id, "artifact", logical_path,
            {"sha256": digest, "project_id": project_id,
             "logical_path": logical_path, "evidence_kind": evidence_kind,
             "size_bytes": len(content)},
            evidence_class=evidence_kind,
            source_uri=source_url or "registry://sha256/" + digest,
        ))
        self.graph.add_edge(GraphEdge(
            artifact_node_id, _RELATION[evidence_kind], claim_node_id,
            {"hypothesis_id": hypothesis_id, "evidence_id": evidence.evidence_id,
             "artifact_sha256": digest, "evidence_kind": evidence_kind},
        ))
        return {
            "schema": "merlin-research-evidence/1",
            "hypothesis_id": hypothesis_id,
            "evidence_id": evidence.evidence_id,
            "evidence_kind": evidence_kind,
            "artifact_sha256": digest,
            "artifact_verified": self.registry.verify_artifact(digest),
            "graph_edge": {
                "source_id": artifact_node_id,
                "relation": _RELATION[evidence_kind],
                "target_id": claim_node_id,
            },
            "hypothesis_status_unchanged": self.ledger.get(hypothesis_id).status == hypothesis.status,
        }


__all__ = ["ResearchEvidenceRecorder"]
