"""Read-only cross-domain query facade for Merlin's canonical stores.

The facade composes existing stores; it does not duplicate their schemas or mutate
projects, hypotheses, graph records, evidence or outbox state.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.event_outbox import MerlinEventOutbox
from merlin.knowledge_reconstruction import inspect_knowledge_representation


class MerlinReadAPI:
    def __init__(self, registry: MerlinRegistry, *,
                 hypotheses: HypothesisLedger | None = None,
                 graph: MerlinKnowledgeGraph | None = None,
                 outbox: MerlinEventOutbox | None = None):
        self.registry = registry
        self.hypotheses = hypotheses
        self.graph_store = graph
        self.outbox = outbox

    @staticmethod
    def _page(limit: int, offset: int) -> tuple[int, int]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        return limit, offset

    def project(self, project_id: str) -> dict[str, Any]:
        return self.registry.inventory(project_id)

    def artifact(self, project_id: str, logical_path: str) -> dict[str, Any]:
        inventory = self.registry.inventory(project_id)
        match = next((item for item in inventory["artifacts"]
                      if item["logical_path"] == logical_path), None)
        if match is None:
            raise KeyError(f"artifact not found: {project_id}/{logical_path}")
        if not self.registry.verify_artifact(match["digest"]):
            raise RuntimeError("artifact digest verification failed")
        path = self.registry.blobs / match["digest"][:2] / match["digest"][2:]
        return {**match, "verified": True, "content_bytes": path.stat().st_size}

    def artifact_history(self, project_id: str, logical_path: str, *,
                         limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a verified, paginated immutable artifact-version history."""
        limit, offset = self._page(limit, offset)
        history = self.registry.artifact_history(project_id, logical_path)
        verified_items: list[dict[str, Any]] = []
        for item in history:
            digest = item["digest"]
            if not self.registry.verify_artifact(digest):
                raise RuntimeError(f"artifact version digest verification failed: {digest}")
            blob = self.registry.blobs / digest[:2] / digest[2:]
            if not blob.is_file() or blob.stat().st_size != item["size_bytes"]:
                raise RuntimeError(f"artifact version blob metadata mismatch: {digest}")
            verified_items.append({**item, "verified": True})
        return {
            "schema": "merlin-artifact-history/1",
            "project_id": project_id,
            "logical_path": logical_path,
            "items": verified_items[offset:offset + limit],
            "limit": limit,
            "offset": offset,
            "total": len(verified_items),
        }

    def knowledge_representation(self, representation_ref: Mapping[str, Any]) -> dict[str, Any]:
        """Return a verified representation manifest and exact source bindings.

        This read-only query verifies the manifest and re-resolves each pinned
        source ArtifactRef. It returns metadata only, never original source
        bytes, and does not imply semantic correctness or CACE qualification.
        """
        inspected = inspect_knowledge_representation(self.registry, representation_ref)
        sources = []
        for ref, resolution in zip(
            inspected["source_artifact_refs"], inspected["source_resolutions"],
        ):
            bindings = [
                binding for binding in inspected["source_bindings"]
                if binding["artifact_ref"] == ref
            ]
            sources.append({
                "artifact_ref": ref,
                "resolution": resolution,
                "source_bindings": bindings,
            })
        return {
            "schema": "merlin-knowledge-representation-query/1",
            "representation_ref": inspected["representation_ref"],
            "representation_id": inspected["representation_id"],
            "manifest": inspected["manifest"],
            "producer_provenance": inspected["producer_provenance"],
            "sources": sources,
            "verified": True,
            "verification_scope": "artifact-integrity-only",
            "authority": "derived-representation-only",
            "qualification": False,
            "source_bytes_included": False,
        }

    def hypothesis(self, hypothesis_id: str) -> dict[str, Any]:
        if self.hypotheses is None:
            raise RuntimeError("hypothesis ledger is not configured")
        item = self.hypotheses.get(hypothesis_id)
        return asdict(item)

    def list_hypotheses(self, *, status: str | None = None,
                        limit: int = 100, offset: int = 0) -> dict[str, Any]:
        limit, offset = self._page(limit, offset)
        if self.hypotheses is None:
            raise RuntimeError("hypothesis ledger is not configured")
        items = self.hypotheses.list_hypotheses(status)
        return {"items": [asdict(item) for item in items[offset:offset + limit]],
                "limit": limit, "offset": offset, "total": len(items)}

    def graph(self) -> dict[str, Any]:
        if self.graph_store is None:
            raise RuntimeError("knowledge graph is not configured")
        return self.graph_store.export_snapshot()

    def graph_summary(self) -> dict[str, Any]:
        snapshot = self.graph()
        return {
            "schema": snapshot["schema_version"],
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "node_count": len(snapshot["nodes"]),
            "edge_count": len(snapshot["edges"]),
            "epistemic_notice": snapshot["epistemic_notice"],
        }

    def outbox_status(self) -> dict[str, Any]:
        if self.outbox is None:
            raise RuntimeError("event outbox is not configured")
        return {"schema": "merlin-outbox-status/1", "counts": self.outbox.counts()}

    def project_snapshot(self, project_id: str) -> dict[str, Any]:
        """Compose a read-only project view with optional research/graph status."""
        result: dict[str, Any] = {
            "schema": "merlin-project-query/1",
            "project": self.project(project_id),
            "hypotheses": None,
            "graph": None,
            "outbox": None,
        }
        if self.hypotheses is not None:
            result["hypotheses"] = self.list_hypotheses(limit=100)
        if self.graph_store is not None:
            result["graph"] = self.graph_summary()
        if self.outbox is not None:
            result["outbox"] = self.outbox_status()
        return result


__all__ = ["MerlinReadAPI"]
