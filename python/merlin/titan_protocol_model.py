"""Deterministic Titan envelope protocol model and structural test vectors.

This module specifies protocol structure and abstract transitions only. It does
not implement cryptography, produce ciphertext, or claim primitive conformance.
Rotor, permutation and graph experiments are intentionally outside this module.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping

MODEL_SCHEMA = "titan-protocol-model/1"
VECTOR_SCHEMA = "titan-structural-vectors/1"
ENVELOPE_SCHEMA = "titan-envelope/1"
PRODUCTION_SUITE = {"kdf": "HKDF-SHA-256", "aead": "AES-256-GCM-SIV", "kem": None}
ALLOWED_KEMS = {None, "ML-KEM-768", "ML-KEM-1024"}
TRANSITIONS = {
    "initialized": ("key_established", "rejected"),
    "key_established": ("keys_derived", "rejected"),
    "keys_derived": ("sealed", "rejected"),
    "sealed": ("authenticated", "rejected"),
    "authenticated": ("accepted", "rejected"),
    "accepted": (), "rejected": (),
}
REQUIRED_ENVELOPE_FIELDS = (
    "schema", "version", "suite", "context", "recipient_key_id",
    "nonce_b64", "ciphertext_b64", "tag_b64",
)

def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")

def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def build_protocol_model(kem: str | None = None) -> dict[str, Any]:
    if kem not in ALLOWED_KEMS:
        raise ValueError("KEM must be absent, ML-KEM-768, or ML-KEM-1024")
    return {
        "schema": MODEL_SCHEMA, "protocol": "Titan context-bound envelope", "version": 1,
        "production_boundary": {
            "suite": {**PRODUCTION_SUITE, "kem": kem},
            "context_binding": "required", "authenticated_metadata": "required",
            "canonical_encoding": "sorted-key UTF-8 JSON; compact separators; terminal LF",
            "cryptographic_operations_implemented": False,
        },
        "envelope_fields": list(REQUIRED_ENVELOPE_FIELDS),
        "state_machine": {
            "initial": "initialized",
            "transitions": {state: list(next_states) for state, next_states in TRANSITIONS.items()},
            "terminal_states": ["accepted", "rejected"],
            "failure_rule": "Any failed required stage transitions to rejected; no partial acceptance.",
        },
        "invariants": [
            "Envelope version is explicitly supported before processing.",
            "Suite identifiers are allow-listed; custom cipher identifiers are rejected.",
            "Context is present and included in authenticated metadata by the implementation.",
            "Recipient key identity is explicit and bound to envelope context.",
            "Authentication must succeed before plaintext is released.",
            "Failure is terminal and does not release plaintext.",
            "Protocol metadata is canonicalized before authentication.",
            "No rotor, permutation, lattice, graph mutation, or compute-fabric output enters production key derivation or envelope processing.",
        ],
        "non_goals": [
            "No cryptographic primitive implementation or known-answer ciphertext.",
            "No proof of AES-GCM-SIV, HKDF, ML-KEM, entropy quality, side-channel resistance, or implementation security.",
            "No custom hybrid KEM combiner; any hybrid profile requires a published construction and independent review.",
        ],
        "experimental_boundary": {
            "status": "separate_untrusted_research",
            "excluded_concepts": ["rotors", "Steckerbrett permutations", "changing lattices", "graph mutation", "Ko-memory path dependence"],
            "permitted_use": "standalone hypothesis generation and simulation only",
            "prohibited_use": "production keys, KDF inputs, nonces, authenticated metadata, ciphertext, or suite negotiation",
        },
    }

def validate_envelope_structure(envelope: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(envelope, Mapping):
        return ["envelope must be an object"]
    missing = [field for field in REQUIRED_ENVELOPE_FIELDS if field not in envelope]
    if missing:
        return ["missing required fields: " + ",".join(missing)]
    if envelope.get("schema") != ENVELOPE_SCHEMA:
        errors.append("unsupported envelope schema")
    if envelope.get("version") != 1:
        errors.append("unsupported envelope version")
    suite = envelope.get("suite")
    if not isinstance(suite, Mapping):
        errors.append("suite must be an object")
    else:
        if suite.get("kdf") != "HKDF-SHA-256":
            errors.append("KDF is not allow-listed")
        if suite.get("aead") != "AES-256-GCM-SIV":
            errors.append("AEAD is not allow-listed")
        if suite.get("kem") not in ALLOWED_KEMS:
            errors.append("KEM is not allow-listed")
        if set(suite) != {"kdf", "aead", "kem"}:
            errors.append("suite fields must be exact")
    context = envelope.get("context")
    if not isinstance(context, Mapping) or not context:
        errors.append("context must be a non-empty object")
    else:
        for key in ("purpose", "protocol_version", "tenant_or_domain"):
            if not isinstance(context.get(key), str) or not context[key].strip():
                errors.append("context field is missing or invalid: " + key)
    for key in ("recipient_key_id", "nonce_b64", "ciphertext_b64", "tag_b64"):
        if not isinstance(envelope.get(key), str) or not envelope[key].strip():
            errors.append("field is missing or invalid: " + key)
    forbidden = {"rotor_state", "permutation", "lattice", "graph_topology", "ko_memory"}
    if forbidden.intersection(envelope):
        errors.append("experimental research fields are forbidden in production envelope")
    return errors

def _base_envelope() -> dict[str, Any]:
    return {
        "schema": ENVELOPE_SCHEMA, "version": 1, "suite": dict(PRODUCTION_SUITE),
        "context": {"purpose": "artifact-sealing", "protocol_version": "1",
                    "tenant_or_domain": "merlin-test-domain"},
        "recipient_key_id": "test-recipient-key-01",
        "nonce_b64": "STRUCTURAL-PLACEHOLDER-NONCE",
        "ciphertext_b64": "STRUCTURAL-PLACEHOLDER-CIPHERTEXT",
        "tag_b64": "STRUCTURAL-PLACEHOLDER-TAG",
    }

def generate_structural_test_vectors() -> dict[str, Any]:
    valid = _base_envelope()
    missing_context = deepcopy(valid); missing_context.pop("context")
    bad_suite = deepcopy(valid); bad_suite["suite"]["aead"] = "CUSTOM-ROTOR-CIPHER"
    contaminated = deepcopy(valid); contaminated["rotor_state"] = {"position": [1, 2, 3]}
    unsupported = deepcopy(valid); unsupported["version"] = 99
    cases = [
        ("valid-envelope-structure", valid, True),
        ("missing-context", missing_context, False),
        ("unapproved-suite", bad_suite, False),
        ("experimental-field-contamination", contaminated, False),
        ("unsupported-version", unsupported, False),
    ]
    vectors = []
    for vector_id, envelope, expected_valid in cases:
        errors = validate_envelope_structure(envelope)
        vectors.append({
            "vector_id": vector_id, "input": envelope,
            "expected": {"structurally_valid": expected_valid},
            "oracle": {"structurally_valid": not errors, "errors": errors},
            "cryptographic_known_answer": False,
        })
    return {
        "schema": VECTOR_SCHEMA, "vector_class": "canonical-envelope-structure",
        "deterministic": True, "cryptographic_operations_implemented": False,
        "vectors": vectors,
        "limitations": [
            "Placeholder nonce, ciphertext and tag values are not decryptable cryptographic test data.",
            "These vectors validate schema and structural rejection only.",
            "Authentication, KDF, AEAD and KEM known-answer tests must use published or independently validated vectors.",
        ],
    }

def build_titan_protocol_bundle(kem: str | None = "ML-KEM-768") -> dict[str, Any]:
    import base64
    model = build_protocol_model(kem=kem)
    vectors = generate_structural_test_vectors()
    model_bytes = canonical_json_bytes(model)
    vector_bytes = canonical_json_bytes(vectors)
    return {
        "schema": "titan-protocol-bundle/1", "model": model, "vectors": vectors,
        "model_sha256": sha256_hex(model_bytes), "vectors_sha256": sha256_hex(vector_bytes),
        "model_bytes_b64": base64.b64encode(model_bytes).decode("ascii"),
        "vectors_bytes_b64": base64.b64encode(vector_bytes).decode("ascii"),
        "bundle_limitations": "Deterministic protocol specification and structural vectors only; not cryptographic implementation or security proof.",
    }

def verify_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    if bundle.get("schema") != "titan-protocol-bundle/1":
        raise ValueError("unsupported Titan bundle schema")
    import base64
    model_bytes = canonical_json_bytes(bundle["model"])
    vector_bytes = canonical_json_bytes(bundle["vectors"])
    model_digest, vector_digest = sha256_hex(model_bytes), sha256_hex(vector_bytes)
    if model_digest != bundle.get("model_sha256") or vector_digest != bundle.get("vectors_sha256"):
        raise ValueError("Titan bundle digest mismatch")
    try:
        embedded_model = base64.b64decode(bundle["model_bytes_b64"], validate=True)
        embedded_vectors = base64.b64decode(bundle["vectors_bytes_b64"], validate=True)
    except (KeyError, ValueError) as exc:
        raise ValueError("Titan bundle embedded canonical bytes are invalid") from exc
    if embedded_model != model_bytes or embedded_vectors != vector_bytes:
        raise ValueError("Titan bundle embedded bytes do not match canonical content")
    outcomes = []
    for vector in bundle["vectors"]["vectors"]:
        actual = not validate_envelope_structure(vector["input"])
        outcomes.append(actual == vector["expected"]["structurally_valid"])
    if not all(outcomes):
        raise ValueError("one or more Titan structural vectors failed")
    return {
        "schema": "titan-bundle-verification/1", "model_sha256": model_digest,
        "vectors_sha256": vector_digest, "vector_count": len(outcomes),
        "vectors_passed": sum(outcomes), "identity_verified": True,
        "scope": "canonical bytes, bundle digests, and structural vector oracles only",
        "cryptographic_security_verified": False, "promotion_authority": False,
    }

__all__ = [
    "MODEL_SCHEMA", "VECTOR_SCHEMA", "ENVELOPE_SCHEMA", "canonical_json_bytes",
    "build_protocol_model", "validate_envelope_structure",
    "generate_structural_test_vectors", "build_titan_protocol_bundle", "verify_bundle",
]
