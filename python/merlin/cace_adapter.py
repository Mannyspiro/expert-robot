"""Independent CACE verification adapter with exact-input receipt binding.

A real CACE service is injected; this adapter validates its response and stores
the receipt. It never promotes hypotheses or grants execution authority.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, Callable, Mapping

from .event_outbox import MerlinEventOutbox
from .project_registry import MerlinRegistry
from .knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph
from .telemetry import agent_event_sink
from .cace_attestation import verify_cace_signed_attestation


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


class CaceVerificationAdapter:
    def __init__(self, *, verify_transport: Callable[[dict[str, Any]], Mapping[str, Any]] | None,
                 registry: MerlinRegistry, outbox: MerlinEventOutbox,
                 graph: MerlinKnowledgeGraph | None = None,
                 trusted_verifier_keys: Mapping[str, Mapping[str, str]] | None = None):
        self.verify_transport = verify_transport
        self.registry = registry
        self.outbox = outbox
        self.graph = graph
        self.trusted_verifier_keys = dict(trusted_verifier_keys or {})
        self.emit_event = agent_event_sink(outbox, "cace")

    def _verified_artifact_bytes(self, digest: str) -> bytes:
        if not self.registry.verify_artifact(digest):
            raise ValueError("CACE input artifact is absent from the registry or failed digest verification")
        path = self.registry.blobs / digest[:2] / digest[2:]
        content = path.read_bytes()
        if len(content) > 25 * 1024 * 1024:
            raise ValueError("CACE artifact exceeds the 25 MiB verification transport limit")
        return content

    def verify(self, *, project_id: str, repository: str, commit_sha: str,
               artifact_sha256: str, theorem: str, requester_id: str,
               tool_version: str, logical_path: str | None = None) -> dict[str, Any]:
        if self.verify_transport is None:
            raise RuntimeError("CACE verification transport is not configured")
        if not self.trusted_verifier_keys:
            raise RuntimeError("CACE verifier trust store is not configured")
        if not isinstance(tool_version, str) or not tool_version.strip() or len(tool_version) > 200:
            raise ValueError("tool_version must identify the exact verifier toolchain")
        if not repository or "/" not in repository:
            raise ValueError("repository must be owner/name")
        if len(commit_sha) != 40 or any(c not in "0123456789abcdef" for c in commit_sha):
            raise ValueError("commit_sha must be a lowercase 40-character Git SHA")
        if len(artifact_sha256) != 64 or any(c not in "0123456789abcdef" for c in artifact_sha256):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256 digest")
        if not theorem.strip() or not requester_id.strip():
            raise ValueError("theorem and requester identity are required")
        # Refuse to ask an independent verifier to attest to an artifact that
        # the canonical registry cannot currently re-hash from stored bytes.
        artifact_bytes = self._verified_artifact_bytes(artifact_sha256)
        request = {
            "schema": "merlin-cace-verification-request/1",
            "repository": repository,
            "commit_sha": commit_sha,
            "artifact_sha256": artifact_sha256,
            "theorem": theorem,
            "tool_version": tool_version,
            "requester_id": requester_id,
            "artifact_registry_verified": True,
            "artifact_size_bytes": len(artifact_bytes),
            "artifact_content_base64": base64.b64encode(artifact_bytes).decode("ascii"),
        }
        response = self.verify_transport(request)
        if not isinstance(response, Mapping):
            raise TypeError("CACE verifier must return a mapping receipt")
        receipt = dict(response)
        if receipt.get("schema") != "cace-independent-verification/1":
            raise ValueError("unsupported CACE verification receipt schema")
        if receipt.get("repository") != repository or receipt.get("commit_sha") != commit_sha:
            raise ValueError("CACE receipt is bound to a different repository revision")
        if receipt.get("artifact_sha256") != artifact_sha256 or receipt.get("theorem") != theorem:
            raise ValueError("CACE receipt is bound to a different artifact or theorem")
        verifier_id = receipt.get("verifier_id")
        if not isinstance(verifier_id, str) or not verifier_id.strip() or verifier_id == requester_id:
            raise ValueError("CACE verifier must have an independent identity")
        signed = verify_cace_signed_attestation(
            receipt.get("signed_attestation"),
            trusted_verifier_keys=self.trusted_verifier_keys,
            expected_claim_id=theorem,
            expected_bundle_sha256=artifact_sha256,
            expected_bindings={
                "repository": repository, "commit_sha": commit_sha,
                "theorem": theorem, "tool_version": tool_version,
            },
            requester_id=requester_id,
        )
        if signed["verifier_id"] != verifier_id or signed["purpose"] != "independent-reproduction":
            raise ValueError("CACE signed attestation identity or purpose mismatch")
        if receipt.get("source_commit_verified") is not True:
            raise ValueError("CACE did not authenticate the source commit")
        if receipt.get("artifact_digest_verified") is not True:
            raise ValueError("CACE did not verify the artifact digest")
        status = receipt.get("verification_status")
        if status not in {"verified", "rejected", "inconclusive"}:
            raise ValueError("unsupported CACE verification status")
        axioms = receipt.get("axiom_dependencies")
        if not isinstance(axioms, list) or any(not isinstance(item, str) for item in axioms):
            raise ValueError("CACE receipt must enumerate axiom dependencies")
        if status == "verified":
            if receipt.get("kernel_checked") is not True:
                raise ValueError("verified proof receipt requires kernel_checked=true")
            if receipt.get("axiom_audit_passed") is not True:
                raise ValueError("verified proof receipt requires a passing axiom audit")
            if receipt.get("contains_sorry") is not False:
                raise ValueError("verified proof receipt must confirm contains_sorry=false")
            if receipt.get("exact_target_declaration") is not True:
                raise ValueError("verified proof receipt must bind the exact target declaration")
        supplied_digest = receipt.get("receipt_sha256")
        body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        expected_digest = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
        if supplied_digest != expected_digest:
            raise ValueError("CACE receipt SHA-256 mismatch")
        receipt_bytes = (_canonical(receipt) + "\n").encode("utf-8")
        selected_path = logical_path or (
            "cace-receipts/" + commit_sha + "/" + artifact_sha256 + "/" +
            hashlib.sha256(theorem.encode("utf-8")).hexdigest() + ".json"
        )
        digest = self.registry.put_artifact(project_id, selected_path, receipt_bytes,
                                            "application/vnd.merlin.cace-receipt+json")
        if not self.registry.verify_artifact(digest):
            raise RuntimeError("stored CACE receipt failed registry digest verification")
        receipt_graph_node = None
        if self.graph is not None:
            artifact_identity = project_id + "|" + (logical_path or selected_path) + "|" + artifact_sha256
            artifact_node_id = "artifact:" + hashlib.sha256(
                artifact_identity.encode("utf-8")
            ).hexdigest()[:32]
            if self.graph.get_node(artifact_node_id) is None:
                self.graph.add_node(GraphNode(
                    artifact_node_id, "artifact", logical_path or selected_path,
                    {"sha256": artifact_sha256, "project_id": project_id,
                     "logical_path": logical_path or selected_path,
                     "independently_submitted_to_cace": True},
                    evidence_class="submitted_for_verification",
                    source_uri="registry://sha256/" + artifact_sha256,
                ))
            receipt_graph_node = "cace-receipt:" + digest[:40]
            self.graph.add_node(GraphNode(
                receipt_graph_node, "proof_receipt", "CACE " + status + " receipt",
                {"receipt_sha256": digest, "subject_artifact_sha256": artifact_sha256,
                 "repository": repository, "commit_sha": commit_sha,
                 "theorem": theorem, "verifier_id": verifier_id,
                 "verification_status": status, "promotion_authority": False},
                evidence_class="independent_verification",
                source_uri="registry://sha256/" + digest,
            ))
            self.graph.add_edge(GraphEdge(
                receipt_graph_node, "reviews", artifact_node_id,
                {"receipt_sha256": digest, "subject_artifact_sha256": artifact_sha256,
                 "verification_status": status, "independent": True},
            ))
        result = {
            "schema": "merlin-cace-verification-result/1",
            "verification_status": status,
            "verifier_id": verifier_id,
            "verifier_key_id": signed["verifier_key_id"],
            "tool_version": tool_version,
            "source_commit": commit_sha,
            "artifact_sha256": artifact_sha256,
            "receipt_artifact_sha256": digest,
            "receipt_graph_node_id": receipt_graph_node,
            "promotion_authority": False,
        }
        verification_key = "cace-verification:" + digest
        verification_event_id = "evt_" + hashlib.sha256(verification_key.encode()).hexdigest()
        already_recorded = self.outbox.get(verification_event_id) is not None
        self.outbox.enqueue(verification_key, "merlin.cace.verification.completed", result)
        if not already_recorded:
            evidence_ref = "sha256:" + digest
            self.emit_event(
                kind="proof.checked", run_id=commit_sha, task_id=artifact_sha256,
                payload={"agent_id": verifier_id, "role": "independent verifier",
                         "status": status, "activity": "proof receipt checked",
                         "theorem": theorem, "kernel_checked": receipt.get("kernel_checked"),
                         "axiom_audit_passed": receipt.get("axiom_audit_passed"),
                         "contains_sorry": receipt.get("contains_sorry"),
                         "axiom_dependencies": axioms},
                evidence_refs=[evidence_ref],
            )
            self.emit_event(
                kind="verification.completed", run_id=commit_sha, task_id=artifact_sha256,
                payload={"agent_id": verifier_id, "status": status,
                         "independent": True, "source_commit": commit_sha,
                         "artifact_sha256": artifact_sha256,
                         "receipt_artifact_sha256": digest},
                evidence_refs=[evidence_ref],
            )
            self.emit_event(
                kind="agent.status", run_id=commit_sha, task_id=artifact_sha256,
                payload={"agent_id": verifier_id, "role": "CACE verifier",
                         "status": "completed", "activity": "independent verification receipt stored"},
                evidence_refs=[evidence_ref],
            )
        return result


    def verify_artifact(self, *, project_id: str, repository: str, commit_sha: str,
                        artifact_sha256: str, artifact_kind: str,
                        artifact_schema: str, requester_id: str,
                        logical_path: str, tool_identity: str) -> dict[str, Any]:
        """Independently attest a non-theorem artifact and store its signed receipt."""
        if self.verify_transport is None:
            raise RuntimeError("CACE verification transport is not configured")
        if not self.trusted_verifier_keys:
            raise RuntimeError("CACE verifier trust store is not configured")
        if not repository or "/" not in repository:
            raise ValueError("repository must be owner/name")
        if len(commit_sha) != 40 or any(c not in "0123456789abcdef" for c in commit_sha):
            raise ValueError("commit_sha must be a lowercase 40-character Git SHA")
        if len(artifact_sha256) != 64 or any(c not in "0123456789abcdef" for c in artifact_sha256):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256 digest")
        for value, label in ((artifact_kind, "artifact_kind"),
                             (artifact_schema, "artifact_schema"),
                             (requester_id, "requester_id"),
                             (logical_path, "logical_path"),
                             (tool_identity, "tool_identity")):
            if not isinstance(value, str) or not value.strip() or len(value) > 500:
                raise ValueError(label + " is required")
        artifact_bytes = self._verified_artifact_bytes(artifact_sha256)
        request = {
            "schema": "merlin-cace-artifact-verification-request/1",
            "repository": repository,
            "commit_sha": commit_sha,
            "artifact_sha256": artifact_sha256,
            "artifact_kind": artifact_kind,
            "artifact_schema": artifact_schema,
            "logical_path": logical_path,
            "tool_identity": tool_identity,
            "requester_id": requester_id,
            "artifact_registry_verified": True,
            "artifact_size_bytes": len(artifact_bytes),
            "artifact_content_base64": base64.b64encode(artifact_bytes).decode("ascii"),
        }
        response = self.verify_transport(request)
        if not isinstance(response, Mapping):
            raise TypeError("CACE artifact verifier must return a mapping receipt")
        receipt = dict(response)
        if receipt.get("schema") != "cace-artifact-verification/1":
            raise ValueError("unsupported CACE artifact receipt schema")
        for key in ("repository", "commit_sha", "artifact_sha256",
                    "artifact_kind", "artifact_schema", "logical_path", "tool_identity"):
            if receipt.get(key) != request[key]:
                raise ValueError("CACE artifact receipt is bound to a different " + key)
        verifier_id = receipt.get("verifier_id")
        if not isinstance(verifier_id, str) or not verifier_id.strip() or verifier_id == requester_id:
            raise ValueError("CACE artifact verifier must have an independent identity")
        signed = verify_cace_signed_attestation(
            receipt.get("signed_attestation"),
            trusted_verifier_keys=self.trusted_verifier_keys,
            expected_claim_id="artifact:" + artifact_kind,
            expected_bundle_sha256=artifact_sha256,
            expected_bindings={
                "repository": repository, "commit_sha": commit_sha,
                "artifact_kind": artifact_kind, "artifact_schema": artifact_schema,
                "logical_path": logical_path, "tool_identity": tool_identity,
            },
            requester_id=requester_id,
        )
        if signed["verifier_id"] != verifier_id or signed["purpose"] != "artifact-integrity":
            raise ValueError("CACE signed artifact attestation identity or purpose mismatch")
        if receipt.get("source_commit_verified") is not True or receipt.get("artifact_digest_verified") is not True:
            raise ValueError("CACE did not independently authenticate the source commit and artifact digest")
        status = receipt.get("verification_status")
        if status not in {"verified", "rejected", "inconclusive"}:
            raise ValueError("unsupported CACE artifact verification status")
        if status == "verified":
            if receipt.get("artifact_schema_validated") is not True:
                raise ValueError("verified artifact receipt requires artifact_schema_validated=true")
            if receipt.get("artifact_content_verified") is not True:
                raise ValueError("verified artifact receipt requires artifact_content_verified=true")
        supplied_digest = receipt.get("receipt_sha256")
        body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        expected_digest = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
        if supplied_digest != expected_digest:
            raise ValueError("CACE artifact receipt SHA-256 mismatch")
        receipt_bytes = (_canonical(receipt) + "\n").encode("utf-8")
        receipt_path = ("cace-artifact-receipts/" + commit_sha + "/" +
                        artifact_sha256 + "/" + hashlib.sha256(
                            artifact_kind.encode("utf-8")).hexdigest() + ".json")
        receipt_digest = self.registry.put_artifact(
            project_id, receipt_path, receipt_bytes,
            "application/vnd.merlin.cace-artifact-receipt+json",
        )
        if not self.registry.verify_artifact(receipt_digest):
            raise RuntimeError("stored CACE artifact receipt failed registry digest verification")
        receipt_node_id = None
        if self.graph is not None:
            artifact_identity = project_id + "|" + logical_path + "|" + artifact_sha256
            artifact_node_id = "artifact:" + hashlib.sha256(
                artifact_identity.encode("utf-8")).hexdigest()[:32]
            if self.graph.get_node(artifact_node_id) is None:
                self.graph.add_node(GraphNode(
                    artifact_node_id, "artifact", logical_path,
                    {"sha256": artifact_sha256, "project_id": project_id,
                     "logical_path": logical_path, "artifact_kind": artifact_kind,
                     "artifact_schema": artifact_schema},
                    evidence_class="submitted_for_verification",
                    source_uri="registry://sha256/" + artifact_sha256,
                ))
            receipt_node_id = "cace-receipt:" + receipt_digest[:40]
            self.graph.add_node(GraphNode(
                receipt_node_id, "proof_receipt", "CACE artifact " + status,
                {"receipt_sha256": receipt_digest,
                 "subject_artifact_sha256": artifact_sha256,
                 "artifact_kind": artifact_kind, "artifact_schema": artifact_schema,
                 "repository": repository, "commit_sha": commit_sha,
                 "verifier_id": verifier_id, "verification_status": status,
                 "promotion_authority": False},
                evidence_class="independent_verification",
                source_uri="registry://sha256/" + receipt_digest,
            ))
            self.graph.add_edge(GraphEdge(
                receipt_node_id, "reviews", artifact_node_id,
                {"receipt_sha256": receipt_digest,
                 "subject_artifact_sha256": artifact_sha256,
                 "verification_status": status, "independent": True},
            ))
        result = {
            "schema": "merlin-cace-artifact-verification-result/1",
            "verification_status": status,
            "verifier_id": verifier_id,
            "source_commit": commit_sha,
            "artifact_sha256": artifact_sha256,
            "receipt_artifact_sha256": receipt_digest,
            "receipt_graph_node_id": receipt_node_id,
            "promotion_authority": False,
        }
        key = "cace-artifact-verification:" + receipt_digest
        event_id = "evt_" + hashlib.sha256(key.encode()).hexdigest()
        already_recorded = self.outbox.get(event_id) is not None
        self.outbox.enqueue(key, "merlin.cace.verification.completed", result)
        if not already_recorded:
            evidence_ref = "sha256:" + receipt_digest
            self.emit_event(
                kind="verification.completed", run_id=commit_sha,
                task_id=artifact_sha256,
                payload={"agent_id": verifier_id, "status": status,
                         "independent": True, "artifact_kind": artifact_kind,
                         "artifact_sha256": artifact_sha256,
                         "receipt_artifact_sha256": receipt_digest},
                evidence_refs=[evidence_ref],
            )
        return result


__all__ = ["CaceVerificationAdapter"]
