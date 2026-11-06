"""Verifier-trusted validation for CACE Ed25519 signed attestations.

This implements the CACE signed-attestation v1 wire profile. The embedded public
key is never trusted by itself: its key ID must exist in Merlin's pinned trust
store. Attestations are provenance only and carry no proof-promotion authority.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any, Mapping

DOMAIN = b"CACE:SIGNED-ATTESTATION:v1\0"
ENVELOPE_SCHEMA = "cace-signed-attestation-v1"
STATEMENT_SCHEMA = "cace-attestation-statement-v1"
ALGORITHM = "ed25519"
PROOF_EFFECT = "none"
_HEX = frozenset("0123456789abcdef")
_ENVELOPE_KEYS = {
    "schema", "signature_algorithm", "proof_effect", "statement_sha256",
    "statement", "public_key_pem", "signature_b64",
}
_STATEMENT_KEYS = {
    "schema", "signature_algorithm", "proof_effect", "verifier_id",
    "verifier_key_id", "claim_id", "bundle_sha256", "created_at_utc",
    "purpose", "bindings",
}


class CaceAttestationError(ValueError):
    """Raised when a CACE signed attestation fails closed validation."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _public_key(pem: str):
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:  # pragma: no cover - deployment packaging failure
        raise RuntimeError("CACE Ed25519 verification requires cryptography") from exc
    if not isinstance(pem, str) or not pem.strip():
        raise CaceAttestationError("public key PEM is missing")
    try:
        key = serialization.load_pem_public_key(pem.encode("ascii"))
    except (UnicodeEncodeError, ValueError, TypeError) as exc:
        raise CaceAttestationError("public key PEM is invalid") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise CaceAttestationError("CACE attestation key must be Ed25519")
    raw = key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = "ed25519:" + hashlib.sha256(raw).hexdigest()
    return key, raw, key_id


def trusted_cace_verifier_keys_from_environment() -> dict[str, str]:
    """Load pinned signer PEMs from CACE_VERIFY_TRUSTED_KEYS_JSON.

    The variable must map CACE key IDs to objects containing the pinned verifier_id
    and public_key_pem. Private keys must never be placed in Merlin's environment.
    """
    raw = os.environ.get("CACE_VERIFY_TRUSTED_KEYS_JSON", "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("CACE_VERIFY_TRUSTED_KEYS_JSON must be valid JSON") from exc
    if not isinstance(payload, dict) or not payload:
        raise ValueError("CACE trusted key configuration must be a non-empty object")
    trusted: dict[str, dict[str, str]] = {}
    for key_id, entry in payload.items():
        if not isinstance(key_id, str) or not isinstance(entry, Mapping):
            raise ValueError("CACE trusted key entries must be objects")
        if set(entry) != {"verifier_id", "public_key_pem"}:
            raise ValueError("CACE trusted key entries require verifier_id and public_key_pem")
        verifier_id = entry.get("verifier_id")
        pem = entry.get("public_key_pem")
        if not isinstance(verifier_id, str) or not verifier_id.strip() or not isinstance(pem, str):
            raise ValueError("CACE trusted key verifier identity and PEM are required")
        _, _, actual_id = _public_key(pem)
        if key_id != actual_id:
            raise ValueError("CACE trusted key ID does not match its public key")
        trusted[key_id] = {"verifier_id": verifier_id, "public_key_pem": pem}
    return trusted


def verify_cace_signed_attestation(
    envelope: Mapping[str, Any],
    *,
    trusted_verifier_keys: Mapping[str, str],
    expected_claim_id: str,
    expected_bundle_sha256: str,
    expected_bindings: Mapping[str, Any],
    requester_id: str,
) -> dict[str, str]:
    """Verify CACE signature, trust anchor, identity and exact subject bindings."""
    if not isinstance(envelope, Mapping) or set(envelope) != _ENVELOPE_KEYS:
        raise CaceAttestationError("signed attestation envelope has missing or extra fields")
    if envelope.get("schema") != ENVELOPE_SCHEMA:
        raise CaceAttestationError("unsupported CACE signed attestation schema")
    if envelope.get("signature_algorithm") != ALGORITHM:
        raise CaceAttestationError("CACE attestation must use Ed25519")
    if envelope.get("proof_effect") != PROOF_EFFECT:
        raise CaceAttestationError("CACE signed attestation must have proof_effect=none")
    statement = envelope.get("statement")
    if not isinstance(statement, Mapping) or set(statement) != _STATEMENT_KEYS:
        raise CaceAttestationError("CACE attestation statement has missing or extra fields")
    if statement.get("schema") != STATEMENT_SCHEMA:
        raise CaceAttestationError("unsupported CACE attestation statement schema")
    if statement.get("signature_algorithm") != ALGORITHM or statement.get("proof_effect") != PROOF_EFFECT:
        raise CaceAttestationError("CACE statement algorithm or proof effect is invalid")
    verifier_id = statement.get("verifier_id")
    if not isinstance(verifier_id, str) or not verifier_id.strip() or verifier_id == requester_id:
        raise CaceAttestationError("CACE verifier identity is missing or not independent")
    if statement.get("claim_id") != expected_claim_id:
        raise CaceAttestationError("CACE attestation is bound to a different claim")
    if statement.get("bundle_sha256") != expected_bundle_sha256:
        raise CaceAttestationError("CACE attestation is bound to a different artifact digest")
    created = statement.get("created_at_utc")
    if not isinstance(created, str):
        raise CaceAttestationError("CACE attestation timestamp is missing")
    try:
        from datetime import datetime
        parsed = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise CaceAttestationError("CACE attestation timestamp is not canonical UTC") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != created:
        raise CaceAttestationError("CACE attestation timestamp is not canonical UTC")
    if statement.get("purpose") not in {"artifact-integrity", "independent-reproduction"}:
        raise CaceAttestationError("CACE attestation purpose is unsupported")
    bindings = statement.get("bindings")
    if not isinstance(bindings, Mapping):
        raise CaceAttestationError("CACE attestation bindings must be an object")
    for key, expected in expected_bindings.items():
        if bindings.get(key) != expected:
            raise CaceAttestationError("CACE attestation binding mismatch: " + str(key))

    embedded_pem = envelope.get("public_key_pem")
    embedded_key, embedded_raw, key_id = _public_key(embedded_pem)
    if statement.get("verifier_key_id") != key_id:
        raise CaceAttestationError("CACE verifier key ID does not match embedded public key")
    if not isinstance(trusted_verifier_keys, Mapping) or not trusted_verifier_keys:
        raise RuntimeError("CACE verifier trust store is not configured")
    pinned_entry = trusted_verifier_keys.get(key_id)
    if not isinstance(pinned_entry, Mapping):
        raise CaceAttestationError("CACE verifier signing key is not trusted")
    if set(pinned_entry) != {"verifier_id", "public_key_pem"}:
        raise CaceAttestationError("CACE pinned signer identity record is malformed")
    if pinned_entry.get("verifier_id") != verifier_id:
        raise CaceAttestationError("CACE verifier identity differs from the pinned signer identity")
    pinned_pem = pinned_entry.get("public_key_pem")
    _, pinned_raw, pinned_id = _public_key(pinned_pem)
    if pinned_id != key_id or pinned_raw != embedded_raw:
        raise CaceAttestationError("CACE embedded public key differs from pinned trust anchor")

    signing_bytes = DOMAIN + _canonical(dict(statement))
    expected_statement_digest = hashlib.sha256(signing_bytes).hexdigest()
    if envelope.get("statement_sha256") != expected_statement_digest:
        raise CaceAttestationError("CACE attestation statement digest mismatch")
    signature_b64 = envelope.get("signature_b64")
    if not isinstance(signature_b64, str):
        raise CaceAttestationError("CACE Ed25519 signature is missing")
    try:
        signature = base64.b64decode(signature_b64.encode("ascii"), validate=True)
    except Exception as exc:
        raise CaceAttestationError("CACE signature is not canonical base64") from exc
    if len(signature) != 64 or base64.b64encode(signature).decode("ascii") != signature_b64:
        raise CaceAttestationError("CACE Ed25519 signature has invalid length or encoding")
    try:
        embedded_key.verify(signature, signing_bytes)
    except Exception as exc:
        # Do not expose cryptography internals or key material in service errors.
        raise CaceAttestationError("CACE Ed25519 signature verification failed") from None
    return {
        "verifier_id": verifier_id,
        "verifier_key_id": key_id,
        "statement_sha256": expected_statement_digest,
        "purpose": str(statement["purpose"]),
    }


__all__ = [
    "CaceAttestationError",
    "verify_cace_signed_attestation",
    "trusted_cace_verifier_keys_from_environment",
]
