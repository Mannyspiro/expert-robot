"""Production bridge from Merlin wire evidence records to authenticated CACE.

This adapter is intentionally thin: the CACEVerificationAdapter owns registry
rehashing, signed-attestation validation, trusted-key checks, receipt storage,
and outbox publication. This bridge adds wire-specific subject bindings.
"""
from __future__ import annotations

import re
from typing import Any, Mapping


_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEX_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def make_cace_wire_evidence_verifier(
    cace_adapter: Any,
    *,
    project_id: str,
    repository: str,
    commit_sha: str,
    requester_id: str,
    tool_identity: str,
):
    """Return the verifier callback consumed by build_qualification_report.

    Each evidence item must already exist in the canonical Merlin artifact
    registry and include artifact_kind, artifact_schema, and logical_path.
    CACE independently rehashes the registered bytes and signs a receipt bound
    to the requirement ID and canonical evidence-record digest.
    """
    verify_artifact = getattr(cace_adapter, "verify_artifact", None)
    if not callable(verify_artifact):
        raise TypeError("cace_adapter must expose verify_artifact")
    for value, label in (
        (project_id, "project_id"),
        (repository, "repository"),
        (requester_id, "requester_id"),
        (tool_identity, "tool_identity"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(label + " is required")
    if not _HEX_GIT_SHA.fullmatch(commit_sha):
        raise ValueError("commit_sha must be a lowercase 40-character Git SHA")

    def verify(request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise TypeError("wire evidence verification request must be a mapping")
        requirement = request.get("requirement")
        artifact_sha256 = request.get("artifact_sha256")
        evidence_record_sha256 = request.get("evidence_record_sha256")
        evidence = request.get("evidence")
        if not isinstance(requirement, str) or not requirement.strip():
            raise ValueError("wire evidence requirement is missing")
        if not isinstance(artifact_sha256, str) or not _HEX_SHA256.fullmatch(artifact_sha256):
            raise ValueError("wire evidence artifact digest is invalid")
        if not isinstance(evidence_record_sha256, str) or not _HEX_SHA256.fullmatch(evidence_record_sha256):
            raise ValueError("wire evidence record digest is invalid")
        if not isinstance(evidence, Mapping):
            raise ValueError("wire evidence metadata is missing")
        artifact_kind = evidence.get("artifact_kind")
        artifact_schema = evidence.get("artifact_schema")
        logical_path = evidence.get("logical_path")
        for value, label in (
            (artifact_kind, "artifact_kind"),
            (artifact_schema, "artifact_schema"),
            (logical_path, "logical_path"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(label + " is required in each evidence record")
        result = verify_artifact(
            project_id=project_id,
            repository=repository,
            commit_sha=commit_sha,
            artifact_sha256=artifact_sha256,
            artifact_kind=artifact_kind,
            artifact_schema=artifact_schema,
            requester_id=requester_id,
            logical_path=logical_path,
            tool_identity=tool_identity,
            additional_bindings={
                "wire_requirement": requirement,
                "evidence_record_sha256": evidence_record_sha256,
            },
        )
        if not isinstance(result, Mapping):
            raise TypeError("CACE adapter returned a non-mapping result")
        status = result.get("verification_status")
        verifier_id = result.get("verifier_id")
        receipt_sha256 = result.get("receipt_artifact_sha256")
        additional = result.get("additional_bindings")
        expected = {
            "wire_requirement": requirement,
            "evidence_record_sha256": evidence_record_sha256,
        }
        if not isinstance(additional, Mapping) or any(additional.get(k) != v for k, v in expected.items()):
            raise ValueError("CACE result does not bind the exact wire evidence subject")
        if not isinstance(verifier_id, str) or not verifier_id.strip():
            raise ValueError("CACE result is missing independent verifier identity")
        if not isinstance(receipt_sha256, str) or not _HEX_SHA256.fullmatch(receipt_sha256):
            raise ValueError("CACE result is missing a canonical receipt digest")
        return {
            "verification_status": "VERIFIED" if status == "verified" else str(status).upper(),
            "verifier_id": verifier_id,
            "receipt_sha256": receipt_sha256,
            "bindings": {
                "requirement": requirement,
                "artifact_sha256": artifact_sha256,
                "evidence_record_sha256": evidence_record_sha256,
            },
        }

    return verify


__all__ = ["make_cace_wire_evidence_verifier"]
