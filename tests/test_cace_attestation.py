import base64
import hashlib
import json
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from python.merlin.cace_attestation import (
    CaceAttestationError,
    verify_cace_signed_attestation,
)


DOMAIN = b"CACE:SIGNED-ATTESTATION:v1\0"


def make_attestation(private_key, *, claim_id, bundle_sha256, bindings,
                     verifier_id="cace:production-verifier", **overrides):
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    raw_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = "ed25519:" + hashlib.sha256(raw_public).hexdigest()
    statement = {
        "schema": "cace-attestation-statement-v1",
        "signature_algorithm": "ed25519",
        "proof_effect": "none",
        "verifier_id": verifier_id,
        "verifier_key_id": key_id,
        "claim_id": claim_id,
        "bundle_sha256": bundle_sha256,
        "created_at_utc": "2026-11-06T19:00:00Z",
        "purpose": "independent-reproduction",
        "bindings": dict(bindings),
    }
    statement.update(overrides)
    signing_bytes = DOMAIN + json.dumps(
        statement, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return {
        "schema": "cace-signed-attestation-v1",
        "signature_algorithm": "ed25519",
        "proof_effect": "none",
        "statement_sha256": hashlib.sha256(signing_bytes).hexdigest(),
        "statement": statement,
        "public_key_pem": public_pem,
        "signature_b64": base64.b64encode(private_key.sign(signing_bytes)).decode("ascii"),
    }, key_id, public_pem


class CaceAttestationTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        self.claim = "Merlin.Target.theorem"
        self.bundle = "a" * 64
        self.bindings = {
            "repository": "Mannyspiro/expert-robot",
            "commit_sha": "b" * 40,
            "tool_version": "Lean 4.32.1",
        }
        self.envelope, self.key_id, self.public_pem = make_attestation(
            self.private, claim_id=self.claim, bundle_sha256=self.bundle,
            bindings=self.bindings,
        )
        self.trust = {self.key_id: {"verifier_id": "cace:production-verifier", "public_key_pem": self.public_pem}}

    def verify(self, envelope=None, trust=None, **kwargs):
        return verify_cace_signed_attestation(
            envelope or self.envelope,
            trusted_verifier_keys=self.trust if trust is None else trust,
            expected_claim_id=kwargs.get("claim", self.claim),
            expected_bundle_sha256=kwargs.get("bundle", self.bundle),
            expected_bindings=kwargs.get("bindings", self.bindings),
            requester_id=kwargs.get("requester", "merlin:worker"),
        )

    def test_valid_attestation_requires_and_matches_pinned_signer(self):
        result = self.verify()
        self.assertEqual(result["verifier_id"], "cace:production-verifier")
        self.assertEqual(result["verifier_key_id"], self.key_id)
        self.assertEqual(result["purpose"], "independent-reproduction")

    def test_embedded_key_without_trust_anchor_is_rejected(self):
        with self.assertRaisesRegex(CaceAttestationError, "not trusted"):
            self.verify(trust={})

    def test_wrong_artifact_claim_or_commit_binding_is_rejected(self):
        with self.assertRaisesRegex(CaceAttestationError, "different artifact"):
            self.verify(bundle="c" * 64)
        with self.assertRaisesRegex(CaceAttestationError, "different claim"):
            self.verify(claim="Other.theorem")
        with self.assertRaisesRegex(CaceAttestationError, "binding mismatch"):
            self.verify(bindings={**self.bindings, "commit_sha": "d" * 40})

    def test_modified_signature_is_rejected(self):
        damaged = dict(self.envelope)
        damaged["signature_b64"] = base64.b64encode(b"x" * 64).decode("ascii")
        with self.assertRaisesRegex(CaceAttestationError, "signature verification failed"):
            self.verify(envelope=damaged)

    def test_unpinned_or_mismatched_embedded_key_is_rejected(self):
        other = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
        envelope, _, _ = make_attestation(
            other, claim_id=self.claim, bundle_sha256=self.bundle,
            bindings=self.bindings,
        )
        with self.assertRaisesRegex(CaceAttestationError, "not trusted"):
            self.verify(envelope=envelope)

    def test_attestation_cannot_claim_proof_promotion_effect(self):
        envelope, _, _ = make_attestation(
            self.private, claim_id=self.claim, bundle_sha256=self.bundle,
            bindings=self.bindings, proof_effect="promote",
        )
        with self.assertRaisesRegex(CaceAttestationError, "proof_effect"):
            self.verify(envelope=envelope)

    def test_pinned_signer_identity_cannot_be_relabelled(self):
        envelope, _, _ = make_attestation(
            self.private, claim_id=self.claim, bundle_sha256=self.bundle,
            bindings=self.bindings, verifier_id="cace:impostor",
        )
        with self.assertRaisesRegex(CaceAttestationError, "pinned signer identity"):
            self.verify(envelope=envelope)

    def test_verifier_must_be_independent_of_requester(self):
        envelope, _, _ = make_attestation(
            self.private, claim_id=self.claim, bundle_sha256=self.bundle,
            bindings=self.bindings, verifier_id="merlin:worker",
        )
        with self.assertRaisesRegex(CaceAttestationError, "not independent"):
            self.verify(envelope=envelope)


if __name__ == "__main__":
    unittest.main()
