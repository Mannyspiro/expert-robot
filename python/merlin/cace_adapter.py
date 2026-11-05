"""Independent CACE verification adapter with exact-input receipt binding.

A real CACE service is injected; this adapter validates its response and stores
the receipt. It never promotes hypotheses or grants execution authority.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping

from merlin.event_outbox import MerlinEventOutbox
from merlin.project_registry import MerlinRegistry
from merlin.telemetry import agent_event_sink


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


class CaceVerificationAdapter:
    def __init__(self, *, verify_transport: Callable[[dict[str, Any]], Mapping[str, Any]] | None,
                 registry: MerlinRegistry, outbox: MerlinEventOutbox):
        self.verify_transport = verify_transport
        self.registry = registry
        self.outbox = outbox
        self.emit_event = agent_event_sink(outbox, "cace")

    def verify(self, *, project_id: str, repository: str, commit_sha: str,
               artifact_sha256: str, theorem: str, requester_id: str,
               logical_path: str | None = None) -> dict[str, Any]:
        if self.verify_transport is None:
            raise RuntimeError("CACE verification transport is not configured")
        if not repository or "/" not in repository:
            raise ValueError("repository must be owner/name")
        if len(commit_sha) != 40 or any(c not in "0123456789abcdef" for c in commit_sha):
            raise ValueError("commit_sha must be a lowercase 40-character Git SHA")
        if len(artifact_sha256) != 64 or any(c not in "0123456789abcdef" for c in artifact_sha256):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256 digest")
        if not theorem.strip() or not requester_id.strip():
            raise ValueError("theorem and requester identity are required")
        request = {
            "schema": "merlin-cace-verification-request/1",
            "repository": repository,
            "commit_sha": commit_sha,
            "artifact_sha256": artifact_sha256,
            "theorem": theorem,
            "requester_id": requester_id,
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
        result = {
            "schema": "merlin-cace-verification-result/1",
            "verification_status": status,
            "verifier_id": verifier_id,
            "source_commit": commit_sha,
            "artifact_sha256": artifact_sha256,
            "receipt_artifact_sha256": digest,
            "promotion_authority": False,
        }
        self.outbox.enqueue("cace-verification:" + digest,
                            "merlin.cace.verification.completed", result)
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


__all__ = ["CaceVerificationAdapter"]
