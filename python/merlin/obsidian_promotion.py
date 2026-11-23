"""Explicit, review-bound promotion of one Obsidian note into Merlin's stores.

Discovery and FTS remain ephemeral. This separate host-facing API does not
authorize itself: a trusted local operator UI must supply an approval callback
for an exact preview. Do not expose the callback to a model/tool planner.
Approving a source stores bytes, not truth, instructions or long-term preference.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Callable, Mapping

from .artifact_ref import ArtifactRef
from .knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph
from .obsidian_vault_bridge import ObsidianVaultBridge, _safe_relative
from .project_registry import MerlinRegistry

_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}\Z")
_PREVIEW_SCHEMA = "merlin-obsidian-note-promotion-preview/1"
_RECEIPT_SCHEMA = "merlin-obsidian-note-promotion/1"


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class ObsidianNotePromotion:
    """Host integration boundary; no background scanning or automatic writes."""

    def __init__(self, vault: ObsidianVaultBridge,
                 registry: MerlinRegistry, graph: MerlinKnowledgeGraph):
        if not isinstance(vault, ObsidianVaultBridge):
            raise TypeError("explicit local vault reader required")
        if not isinstance(registry, MerlinRegistry):
            raise TypeError("canonical MerlinRegistry required")
        if not isinstance(graph, MerlinKnowledgeGraph):
            raise TypeError("canonical MerlinKnowledgeGraph required")
        self.vault, self.registry, self.graph = vault, registry, graph

    def preview(self, project_id: str, relative_path: str, *,
                vault_label: str = "local") -> dict:
        """Describe an exact safe source without copying note bytes to storage."""
        if not isinstance(project_id, str) or not project_id.strip() or len(project_id) > 256:
            raise ValueError("project identifier required")
        if not isinstance(vault_label, str) or not _LABEL.fullmatch(vault_label):
            raise ValueError("vault label must be a short safe identifier")
        path = _safe_relative(relative_path)
        snapshot = self.vault.read()
        note = next((n for n in snapshot["notes"] if n["path"] == path), None)
        if note is None:
            raise ValueError("note missing or excluded from bounded vault scan")
        raw = self.vault._read(path)
        sha = _sha(raw)
        if sha != note["sha256"]:
            raise RuntimeError("note changed during preview; retry")
        if not raw:
            raise ValueError("empty note cannot be promoted")
        path_key = _sha(path.encode("utf-8"))
        logical_path = "obsidian-notes/" + vault_label + "/" + path_key + "/note.md"
        body = {
            "schema": _PREVIEW_SCHEMA,
            "project_id": project_id, "vault_label": vault_label,
            "relative_path": path, "logical_path": logical_path,
            "source_sha256": sha, "size_bytes": len(raw),
            "inventory_status": snapshot["status"],
            "inventory_omissions_count": len(snapshot["omissions"]),
            "note_links_count": len(note["outlinks"]),
            "evidence_class": "unreviewed_source_content",
            "approval_required": True,
            "source_content_emitted": False,
        }
        return {**body, "preview_id": _sha(_canonical(body))}

    @staticmethod
    def _validate_preview(preview: Mapping) -> None:
        if not isinstance(preview, Mapping):
            raise ValueError("review preview must be a mapping")
        expected = {
            "schema", "project_id", "vault_label", "relative_path",
            "logical_path", "source_sha256", "size_bytes",
            "inventory_status", "inventory_omissions_count",
            "note_links_count", "evidence_class", "approval_required",
            "source_content_emitted", "preview_id",
        }
        if set(preview) != expected or preview.get("schema") != _PREVIEW_SCHEMA:
            raise ValueError("unsupported or malformed review preview")
        body = {k: v for k, v in preview.items() if k != "preview_id"}
        if _sha(_canonical(body)) != preview["preview_id"]:
            raise ValueError("tampered review preview")

    def inspect(self, preview: Mapping) -> dict:
        """Read-only reconciliation after success, retry or interrupted writes.

        Artifact and graph writes live in different stores; no distributed
        transaction is asserted. This inspects exact immutable identities and
        never repairs or silently approves an incomplete import.
        """
        self._validate_preview(preview)
        history = self.registry.artifact_history(
            preview["project_id"], preview["logical_path"])
        matched = [item for item in history
                   if item["digest"] == preview["source_sha256"]]
        if not matched:
            return {"schema": "merlin-obsidian-import-inspection/1",
                    "status": "absent", "preview_id": preview["preview_id"],
                    "artifact_ref": None, "graph_complete": False,
                    "source_content_emitted": False, "repaired": False}
        # A content digest can recur across artifact versions. Audit the most
        # recent exact matching version rather than assuming 'current'.
        version = matched[-1]["version"]
        ref_data = self.registry.artifact_ref(
            preview["project_id"], preview["logical_path"], version=version)
        self.registry.resolve_artifact_ref(ref_data)
        node_key = _sha(_canonical(ref_data))
        source_id = "source:obsidian:" + node_key
        artifact_id = "artifact:obsidian:" + node_key
        source = self.graph.get_node(source_id)
        artifact = self.graph.get_node(artifact_id)
        edge = any(
            e["source_id"] == artifact_id
            and e["relation"] == "derived_from"
            and e["target_id"] == source_id
            and e["payload"].get("source_sha256") == preview["source_sha256"]
            and e["payload"].get("review_preview_id") == preview["preview_id"]
            and e["payload"].get("asserts_truth") is False
            for e in self.graph.neighbors(artifact_id, direction="out")
        )
        valid_source = (
            source is not None
            and source.evidence_class == "user_approved_unverified"
            and source.payload.get("artifact_ref") == ref_data
            and source.payload.get("source_sha256") == preview["source_sha256"]
            and source.payload.get("review_preview_id") == preview["preview_id"]
            and source.payload.get("truth_status") == "unverified"
        )
        valid_artifact = (
            artifact is not None
            and artifact.evidence_class == "hash_verified_unreviewed"
            and artifact.payload.get("artifact_ref") == ref_data
            and artifact.payload.get("source_sha256") == preview["source_sha256"]
            and artifact.payload.get("truth_status") == "unverified"
        )
        complete = valid_source and valid_artifact and edge
        return {"schema": "merlin-obsidian-import-inspection/1",
                "status": "complete_unverified" if complete else "partial_requires_review",
                "preview_id": preview["preview_id"],
                "artifact_ref": ref_data,
                "graph_complete": bool(complete),
                "source_content_emitted": False, "repaired": False}

    def promote(self, preview: Mapping, *,
                operator_approve: Callable[[dict], bool] | None = None) -> dict:
        """Persist exact approved note via canonical registry/graph.

        Only a trusted local UI should provide operator_approve. A model is
        not permitted to fabricate or invoke it. No callback => no mutation.
        """
        self._validate_preview(preview)
        if not callable(operator_approve):
            raise PermissionError("a trusted interactive operator approval is required")
        current = self.preview(preview["project_id"], preview["relative_path"],
                               vault_label=preview["vault_label"])
        if current != dict(preview):
            raise RuntimeError("source or review scope changed; new preview required")
        if operator_approve(dict(current)) is not True:
            raise PermissionError("exact note approval denied")
        # Approval can take time. Rebuild preview after it to catch source/link
        # drift and reread once more before any durable content is written.
        approved = self.preview(preview["project_id"], preview["relative_path"],
                                vault_label=preview["vault_label"])
        if approved != current:
            raise RuntimeError("source changed during operator approval")
        raw = self.vault._read(current["relative_path"])
        if _sha(raw) != current["source_sha256"] or len(raw) != current["size_bytes"]:
            raise RuntimeError("source changed before durable import")
        # Project must already exist: an import cannot silently create one.
        self.registry.artifact_history(current["project_id"], current["logical_path"])
        digest = self.registry.put_artifact(
            current["project_id"], current["logical_path"], raw,
            media_type="text/markdown",
        )
        if digest != current["source_sha256"]:
            raise RuntimeError("canonical artifact digest mismatch")
        ref_data = self.registry.artifact_ref(current["project_id"], current["logical_path"])
        ref = ArtifactRef.from_mapping(ref_data)
        if ref.sha256 != digest or not self.registry.resolve_artifact_ref(ref_data)["verified"]:
            raise RuntimeError("promoted artifact identity failed verification")
        # Both nodes represent untrusted content and exact content-addressed
        # provenance. No node or edge asserts that note claims are correct.
        node_key = _sha(_canonical(ref_data))
        source_id = "source:obsidian:" + node_key
        artifact_id = "artifact:obsidian:" + node_key
        source = GraphNode(
            node_id=source_id, node_type="source", label=current["relative_path"],
            payload={"schema": "merlin-obsidian-reviewed-source/1",
                     "relative_path": current["relative_path"],
                     "vault_label": current["vault_label"],
                     "source_sha256": digest, "artifact_ref": ref_data,
                     "review_preview_id": current["preview_id"],
                     "truth_status": "unverified", "approval_scope": "exact_note_bytes"},
            evidence_class="user_approved_unverified",
        )
        artifact = GraphNode(
            node_id=artifact_id, node_type="artifact_reference", label="Obsidian note artifact",
            payload={"schema": "merlin-obsidian-reviewed-artifact/1",
                     "artifact_ref": ref_data, "source_sha256": digest,
                     "content_integrity": "sha256_verified",
                     "truth_status": "unverified"},
            evidence_class="hash_verified_unreviewed",
        )
        # Preflight immutable graph collisions before adding either node.
        for candidate in (source, artifact):
            existing = self.graph.get_node(candidate.node_id)
            if existing is not None and existing != candidate:
                raise ValueError("conflicting immutable graph identity")
        self.graph.add_node(source)
        self.graph.add_node(artifact)
        self.graph.add_edge(GraphEdge(
            source_id=artifact_id, relation="derived_from", target_id=source_id,
            payload={"source_sha256": digest, "review_preview_id": current["preview_id"],
                     "asserts_truth": False},
        ))
        return {
            "schema": _RECEIPT_SCHEMA, "status": "imported_unverified",
            "preview_id": current["preview_id"], "artifact_ref": ref_data,
            "source_node_id": source_id, "artifact_node_id": artifact_id,
            "source_sha256": digest, "source_bytes": len(raw),
            "note_truth_approved": False, "model_weight_calls": 0,
            "production_qualified": False,
        }
