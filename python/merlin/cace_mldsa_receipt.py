"""Verify CACE ML-DSA v2 receipts against an exact CACE checkout.

This adapter verifies provenance and subject-byte integrity only. It deliberately
returns INCONCLUSIVE for semantic artifact validation unless a separate validator
is added at the CACE boundary.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Callable, Mapping

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_MLDSA_SCHEMA = "cace-signed-attestation-v2"
_DOMAIN = "CACE:TITAN:SIGNED-ATTESTATION:v2\0"
_CANONICALIZATION = "sha256/cace-canonical-json-v1"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _read_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(label + " must be a JSON object")
    return value


def _require_sha(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(label + " must be a lowercase SHA-256/Git digest")
    return value


class CaceMldsaReceiptVerifier:
    """Verify a CACE-signed bundle using the pinned CACE CLI and bundle checker."""

    def __init__(
        self,
        *,
        cace_root: str | Path,
        cace_commit_sha: str,
        trusted_verifier_id: str,
        trusted_key_id: str,
        source_commit_verifier: Callable[[str, str], bool],
        python_executable: str = "python",
        timeout_seconds: int = 120,
    ) -> None:
        self.cace_root = Path(cace_root).resolve()
        self.cace_commit_sha = _require_sha(cace_commit_sha, _SHA40, "CACE commit")
        if not trusted_verifier_id.strip():
            raise ValueError("trusted_verifier_id is required")
        if not trusted_key_id.startswith("ml-dsa-65:") or not _SHA256.fullmatch(trusted_key_id.split(":", 1)[-1]):
            raise ValueError("trusted_key_id must use ml-dsa-65:<sha256>")
        if not callable(source_commit_verifier):
            raise ValueError("source_commit_verifier is required")
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        self.trusted_verifier_id = trusted_verifier_id
        self.trusted_key_id = trusted_key_id
        self.source_commit_verifier = source_commit_verifier
        self.python_executable = python_executable
        self.timeout_seconds = timeout_seconds

    def _run_json(self, command: list[str], *, label: str) -> dict[str, Any]:
        result = subprocess.run(
            command,
            cwd=self.cace_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=self.timeout_seconds,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"{label} failed with exit {result.returncode}: "
                + (result.stderr.strip() or result.stdout.strip())
            )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} did not return one JSON object on stdout") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{label} output must be a JSON object")
        return payload

    def _verify_cace_checkout(self) -> None:
        if not (self.cace_root / "scripts/verify_titan_bundle.py").is_file():
            raise FileNotFoundError("pinned CACE bundle verifier is missing")
        if not (self.cace_root / "cace_studio/attest_cli.py").is_file():
            raise FileNotFoundError("pinned CACE attestation CLI is missing")
        result = subprocess.run(
            ["git", "-C", str(self.cace_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False,
            timeout=self.timeout_seconds,
        )
        if result.returncode != 0 or result.stdout.strip() != self.cace_commit_sha:
            raise ValueError("CACE checkout does not match the configured exact commit")

    def verify_transport_response(
        self,
        request: Mapping[str, Any],
        response: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Verify a CACE transport response and return Merlin's canonical receipt.

        The transport returns the CACE bundle document and signed attestation as
        base64 JSON. The artifact bytes are taken from Merlin's exact request,
        never from a caller-supplied path or an unrelated file.
        """
        if not isinstance(request, Mapping) or not isinstance(response, Mapping):
            raise TypeError("CACE signed transport request and response must be objects")
        if response.get("schema") != "cace-mldsa-signed-artifact-response/1":
            raise ValueError("unsupported CACE ML-DSA transport response schema")
        if response.get("proof_effect") != "none":
            raise ValueError("CACE ML-DSA transport response proof_effect must be none")
        if response.get("cace_source_commit") != self.cace_commit_sha:
            raise ValueError("CACE transport used a different source commit")

        def decode_field(name: str) -> bytes:
            encoded = response.get(name)
            if not isinstance(encoded, str) or not encoded:
                raise ValueError(name + " is missing")
            try:
                raw = base64.b64decode(encoded, validate=True)
            except Exception as exc:
                raise ValueError(name + " is not valid base64") from exc
            if base64.b64encode(raw).decode("ascii") != encoded:
                raise ValueError(name + " is not canonical base64")
            return raw

        try:
            artifact_bytes = base64.b64decode(
                request["artifact_content_base64"], validate=True
            )
        except Exception as exc:
            raise ValueError("request artifact_content_base64 is invalid") from exc
        artifact_digest = hashlib.sha256(artifact_bytes).hexdigest()
        if artifact_digest != request.get("artifact_sha256"):
            raise ValueError("request artifact bytes do not match artifact_sha256")

        logical_path = request.get("logical_path")
        if not isinstance(logical_path, str) or not logical_path.strip():
            raise ValueError("request logical_path is required")
        relative = Path(logical_path)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("request logical_path is unsafe")

        with tempfile.TemporaryDirectory(prefix="merlin-cace-mldsa-") as temporary:
            root = Path(temporary)
            artifact_root = root / "artifact-root"
            target = artifact_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(artifact_bytes)
            bundle_path = root / "bundle.json"
            attestation_path = root / "attestation.json"
            bundle_path.write_bytes(decode_field("bundle_document_base64"))
            attestation_path.write_bytes(decode_field("attestation_document_base64"))
            return self.verify_artifact_receipt(
                bundle_path=bundle_path,
                artifact_root=artifact_root,
                attestation_path=attestation_path,
                repository=str(request["repository"]),
                commit_sha=str(request["commit_sha"]),
                workflow_run_id=request["workflow_run_id"],
                provider_commit=str(request["provider_commit"]),
                vector_source_commit=str(request["vector_source_commit"]),
                verification_scope=str(request["verification_scope"]),
                claim_id=str(request["claim_id"]),
                artifact_sha256=artifact_digest,
                artifact_kind=str(request["artifact_kind"]),
                artifact_schema=str(request["artifact_schema"]),
                logical_path=logical_path,
                requester_id=str(request["requester_id"]),
            )

    def verify_artifact_receipt(
        self,
        *,
        bundle_path: str | Path,
        artifact_root: str | Path,
        attestation_path: str | Path,
        repository: str,
        commit_sha: str,
        workflow_run_id: int,
        provider_commit: str,
        vector_source_commit: str,
        verification_scope: str,
        claim_id: str,
        artifact_sha256: str,
        artifact_kind: str,
        artifact_schema: str,
        logical_path: str,
        requester_id: str,
    ) -> dict[str, Any]:
        if not repository or "/" not in repository:
            raise ValueError("repository must be owner/name")
        commit_sha = _require_sha(commit_sha, _SHA40, "source commit")
        provider_commit = _require_sha(provider_commit, _SHA40, "provider commit")
        vector_source_commit = _require_sha(vector_source_commit, _SHA40, "vector source commit")
        artifact_sha256 = _require_sha(artifact_sha256, _SHA256, "artifact SHA-256")
        if not isinstance(workflow_run_id, int) or isinstance(workflow_run_id, bool) or workflow_run_id <= 0:
            raise ValueError("workflow_run_id must be a positive integer")
        for value, label in (
            (verification_scope, "verification_scope"),
            (claim_id, "claim_id"),
            (artifact_kind, "artifact_kind"),
            (artifact_schema, "artifact_schema"),
            (logical_path, "logical_path"),
            (requester_id, "requester_id"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(label + " is required")

        self._verify_cace_checkout()
        bundle_file = Path(bundle_path).resolve()
        root = Path(artifact_root).resolve()
        attestation_file = Path(attestation_path).resolve()
        bundle_document = _read_object(bundle_file, "CACE bundle document")
        if bundle_document.get("command") != "titan-bundle" or bundle_document.get("proof_effect") != "none":
            raise ValueError("unsupported CACE Titan bundle envelope")
        bundle = bundle_document.get("bundle")
        if not isinstance(bundle, Mapping):
            raise ValueError("CACE bundle payload is missing")
        bundle_digest = _require_sha(bundle_document.get("bundle_sha256"), _SHA256, "bundle SHA-256")
        bindings = bundle.get("bindings")
        if not isinstance(bindings, Mapping):
            raise ValueError("CACE bundle bindings are missing")
        expected_bindings = {
            "source_repository": repository,
            "source_commit_sha": commit_sha,
            "workflow_run_id": workflow_run_id,
            "provider_commit": provider_commit,
            "vector_source_commit": vector_source_commit,
            "verification_scope": verification_scope,
        }
        for key, expected in expected_bindings.items():
            if bindings.get(key) != expected:
                raise ValueError("CACE bundle binding mismatch: " + key)
        artifacts = bundle.get("artifacts")
        if not isinstance(artifacts, list):
            raise ValueError("CACE bundle artifacts must be an array")
        matches = [
            item for item in artifacts
            if isinstance(item, Mapping)
            and item.get("path") == logical_path
            and item.get("sha256") == artifact_sha256
        ]
        if len(matches) != 1:
            raise ValueError("CACE bundle must contain exactly one matching subject artifact")

        bundle_check = self._run_json(
            [
                self.python_executable, "scripts/verify_titan_bundle.py",
                "--bundle", str(bundle_file), "--artifact-root", str(root),
            ],
            label="CACE artifact-bundle verification",
        )
        if bundle_check.get("valid") is not True or bundle_check.get("proof_effect") != "none":
            raise ValueError("CACE bundle verifier did not return a provenance-only PASS")
        if bundle_check.get("bundle_sha256") != bundle_digest:
            raise ValueError("CACE bundle verifier returned a different bundle digest")

        attestation_document = _read_object(attestation_file, "CACE attestation document")
        if attestation_document.get("proof_effect") != "none":
            raise ValueError("CACE attestation proof_effect must be none")
        envelope = attestation_document.get("attestation")
        if not isinstance(envelope, Mapping):
            raise ValueError("CACE signed attestation envelope is missing")
        if envelope.get("schema") != _MLDSA_SCHEMA or envelope.get("signature_algorithm") != "ML-DSA-65":
            raise ValueError("unsupported CACE ML-DSA attestation schema or algorithm")
        if envelope.get("proof_effect") != "none":
            raise ValueError("CACE ML-DSA attestation cannot have proof effect")
        if envelope.get("canonicalization") != _CANONICALIZATION or envelope.get("domain_separator") != _DOMAIN:
            raise ValueError("CACE ML-DSA canonicalization or domain separator mismatch")
        statement = envelope.get("statement")
        if not isinstance(statement, Mapping):
            raise ValueError("CACE ML-DSA statement is missing")
        if statement.get("verifier_id") != self.trusted_verifier_id:
            raise ValueError("CACE verifier identity is not trusted")
        if statement.get("verifier_key_id") != self.trusted_key_id:
            raise ValueError("CACE verifier key is not trusted")
        if statement.get("claim_id") != claim_id or statement.get("bundle_sha256") != bundle_digest:
            raise ValueError("CACE attestation is bound to a different claim or bundle")
        statement_bindings = statement.get("bindings")
        if not isinstance(statement_bindings, Mapping):
            raise ValueError("CACE signed statement bindings are missing")
        for key, expected in expected_bindings.items():
            if statement_bindings.get(key) != expected:
                raise ValueError("CACE signed statement binding mismatch: " + key)

        signature_check = self._run_json(
            [
                self.python_executable, "-m", "cace_studio.attest_cli",
                "pqc-verify", str(attestation_file),
                "--trusted-verifier-id", self.trusted_verifier_id,
                "--trusted-key-id", self.trusted_key_id,
            ],
            label="CACE ML-DSA signature verification",
        )
        if signature_check.get("valid") is not True:
            raise ValueError("CACE ML-DSA signature did not verify")
        if (
            signature_check.get("verifier_key_id") != self.trusted_key_id
            or signature_check.get("bundle_sha256") != bundle_digest
            or signature_check.get("claim_id") != claim_id
        ):
            raise ValueError("CACE signature verifier returned mismatched subject bindings")

        if self.source_commit_verifier(repository, commit_sha) is not True:
            raise ValueError("source repository commit was not independently verified")

        receipt = {
            "schema": "cace-artifact-verification/1",
            "repository": repository,
            "commit_sha": commit_sha,
            "artifact_sha256": artifact_sha256,
            "artifact_kind": artifact_kind,
            "artifact_schema": artifact_schema,
            "logical_path": logical_path,
            "verifier_id": self.trusted_verifier_id,
            "source_commit_verified": True,
            "artifact_digest_verified": True,
            "verification_status": "inconclusive",
            "artifact_schema_validated": False,
            "artifact_content_verified": False,
            "signature_status": "verified",
            "signature_algorithm": "ML-DSA-65",
            "verifier_key_id": self.trusted_key_id,
            "bundle_sha256": bundle_digest,
            "cace_source_commit": self.cace_commit_sha,
            "workflow_run_id": workflow_run_id,
            "provider_commit": provider_commit,
            "vector_source_commit": vector_source_commit,
            "proof_effect": "none",
            "promotion_authority": False,
        }
        receipt["receipt_sha256"] = hashlib.sha256(_canonical(receipt)).hexdigest()
        return receipt


__all__ = ["CaceMldsaReceiptVerifier"]
