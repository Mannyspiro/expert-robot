import unittest
import os
import sqlite3
import time
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from python.merlin.identity import (OIDCIdentityResolver, PyJWTJWKSVerifier, SQLiteTokenRevocationStore, learning_identity_resolver_from_environment)
from python.merlin.learning_platform import Actor


ISSUER = "https://identity.example.test/"
AUDIENCE = "merlin-learning-api"
NOW = 1_800_000_000


class OIDCIdentityResolverTests(unittest.TestCase):
    def setUp(self):
        self.claims = {
            "iss": ISSUER,
            "aud": [AUDIENCE, "other-service"],
            "sub": "faculty-17",
            "tenant_id": "tenant-north",
            "role": "instructor",
            "exp": NOW + 600,
            "nbf": NOW - 10,
            "jti": "token-123",
        }
        self.calls = []

        def verify(token, issuer, audience):
            self.calls.append((token, issuer, audience))
            if token != "signed.access.token":
                raise ValueError("invalid signature")
            return dict(self.claims)

        self.verifier = verify
        self.resolver = OIDCIdentityResolver(
            issuer=ISSUER,
            audience=AUDIENCE,
            token_verifier=self.verifier,
            clock=lambda: NOW,
        )

    def headers(self, token="signed.access.token", **extra):
        values = {"Authorization": f"Bearer {token}"}
        values.update(extra)
        return values

    def test_maps_only_verified_claims_to_actor(self):
        actor = self.resolver(self.headers(
            X_Tenant_Id="tenant-attacker",
            X_Role="tenant_admin",
        ))
        self.assertEqual(actor, Actor("tenant-north", "faculty-17", "instructor"))
        self.assertEqual(self.calls, [("signed.access.token", ISSUER, AUDIENCE)])

    def test_unconfigured_resolver_fails_closed(self):
        resolver = OIDCIdentityResolver(
            issuer=ISSUER, audience=AUDIENCE, token_verifier=None,
            clock=lambda: NOW,
        )
        self.assertIsNone(resolver(self.headers()))
        self.assertFalse(resolver.configured)

    def test_missing_or_malformed_bearer_fails_closed(self):
        self.assertIsNone(self.resolver({}))
        self.assertIsNone(self.resolver({"Authorization": "Basic abc"}))
        self.assertIsNone(self.resolver({"Authorization": "Bearer two tokens"}))
        self.assertIsNone(self.resolver({"Authorization": "Bearer " + "x" * 9000}))

    def test_verifier_rejection_fails_closed(self):
        self.assertIsNone(self.resolver(self.headers("forged.token")))

    def test_issuer_and_audience_are_bound(self):
        self.claims["iss"] = "https://attacker.example/"
        self.assertIsNone(self.resolver(self.headers()))
        self.claims["iss"] = ISSUER
        self.claims["aud"] = ["another-api"]
        self.assertIsNone(self.resolver(self.headers()))

    def test_expiry_and_not_before_are_enforced(self):
        self.claims["exp"] = NOW - 120
        self.assertIsNone(self.resolver(self.headers()))
        self.claims["exp"] = NOW + 600
        self.claims["nbf"] = NOW + 120
        self.assertIsNone(self.resolver(self.headers()))

    def test_required_subject_tenant_and_role_are_enforced(self):
        for key in ("sub", "tenant_id", "role"):
            original = self.claims.pop(key)
            self.assertIsNone(self.resolver(self.headers()), key)
            self.claims[key] = original
        self.claims["role"] = "superuser"
        self.assertIsNone(self.resolver(self.headers()))

    def test_revoked_or_unidentifiable_token_fails_closed(self):
        resolver = OIDCIdentityResolver(
            issuer=ISSUER,
            audience=AUDIENCE,
            token_verifier=self.verifier,
            revocation_checker=lambda issuer, token_id: token_id == "token-123",
            clock=lambda: NOW,
        )
        self.assertIsNone(resolver(self.headers()))
        self.claims.pop("jti")
        self.assertIsNone(resolver(self.headers()))

    def test_nonfinite_or_boolean_expiry_is_rejected(self):
        self.claims["exp"] = float("nan")
        self.assertIsNone(self.resolver(self.headers()))
        self.claims["exp"] = True
        self.assertIsNone(self.resolver(self.headers()))



class FakeJWKSClient:
    def __init__(self, public_key):
        self.public_key = public_key
        self.lookups = 0

    def get_signing_key_from_jwt(self, token):
        self.lookups += 1
        return SimpleNamespace(key=self.public_key)


class PyJWTJWKSVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.private_key.public_key()

    def token(self, private_key=None, **overrides):
        now = time.time()
        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "faculty-17",
            "tenant_id": "tenant-north",
            "role": "instructor",
            "iat": now,
            "exp": now + 600,
            "nbf": now - 5,
            "jti": "oidc-token-17",
        }
        claims.update(overrides)
        return jwt.encode(
            claims,
            private_key or self.private_key,
            algorithm="RS256",
            headers={"kid": "merlin-signing-key-1"},
        )

    def verifier(self, public_key=None, algorithms=("RS256",), **kwargs):
        return PyJWTJWKSVerifier(
            issuer=ISSUER,
            audience=AUDIENCE,
            jwks_url="https://identity.example.test/.well-known/jwks.json",
            allowed_algorithms=list(algorithms),
            jwks_client=FakeJWKSClient(public_key or self.public_key),
            **kwargs,
        )

    def test_real_rsa_signature_and_registered_claims_produce_actor(self):
        verifier = self.verifier()
        resolver = OIDCIdentityResolver(
            issuer=ISSUER, audience=AUDIENCE, token_verifier=verifier,
            clock=time.time,
        )
        actor = resolver({"Authorization": "Bearer " + self.token()})
        self.assertEqual(actor, Actor("tenant-north", "faculty-17", "instructor"))

    def test_wrong_signature_is_rejected(self):
        verifier = self.verifier()
        with self.assertRaises(jwt.InvalidSignatureError):
            verifier(self.token(self.other_private_key), ISSUER, AUDIENCE)

    def test_issuer_audience_and_expiry_are_verified_by_pyjwt(self):
        verifier = self.verifier()
        with self.assertRaises(jwt.InvalidIssuerError):
            verifier(self.token(iss="https://wrong.example/"), ISSUER, AUDIENCE)
        with self.assertRaises(jwt.InvalidAudienceError):
            verifier(self.token(aud="different-api"), ISSUER, AUDIENCE)
        with self.assertRaises(jwt.ExpiredSignatureError):
            verifier(self.token(exp=time.time() - 120), ISSUER, AUDIENCE)

    def test_algorithm_allowlist_rejects_hmac_and_none(self):
        with self.assertRaisesRegex(ValueError, "asymmetric allowlist"):
            self.verifier(algorithms=("HS256",))
        hmac_token = jwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": "x",
             "exp": time.time() + 60},
            "not-a-production-secret-with-more-than-thirty-two-bytes",
            algorithm="HS256",
        )
        with self.assertRaises(jwt.InvalidAlgorithmError):
            self.verifier()(hmac_token, ISSUER, AUDIENCE)


    def test_revocation_store_is_durable_idempotent_and_append_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteTokenRevocationStore(Path(tmp) / "revocations.sqlite3")
            self.assertFalse(store.is_revoked(ISSUER, "jti-1"))
            self.assertTrue(store.revoke(ISSUER, "jti-1", "logout"))
            self.assertFalse(store.revoke(ISSUER, "jti-1", "duplicate"))
            self.assertTrue(store.is_revoked(ISSUER, "jti-1"))
            with sqlite3.connect(store.database_path) as db:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("DELETE FROM revoked_tokens WHERE issuer=? AND token_id=?",
                               (ISSUER, "jti-1"))
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("UPDATE revoked_tokens SET reason='changed' WHERE issuer=? AND token_id=?",
                               (ISSUER, "jti-1"))

    def test_maximum_access_token_lifetime_is_enforced(self):
        now = time.time()
        verifier = self.verifier(max_token_lifetime_seconds=600)
        with self.assertRaises(jwt.InvalidTokenError):
            verifier(self.token(exp=now + 1200, iat=now), ISSUER, AUDIENCE)

    def test_external_http_jwks_and_invalid_issuer_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            PyJWTJWKSVerifier(
                issuer=ISSUER, audience=AUDIENCE,
                jwks_url="http://identity.example.test/jwks.json",
                allowed_algorithms=["RS256"],
                jwks_client=FakeJWKSClient(self.public_key),
            )
        with self.assertRaisesRegex(ValueError, "issuer"):
            PyJWTJWKSVerifier(
                issuer="http://identity.example.test/",
                audience=AUDIENCE,
                jwks_url="https://identity.example.test/jwks.json",
                allowed_algorithms=["RS256"],
                jwks_client=FakeJWKSClient(self.public_key),
            )

    def test_environment_factory_stays_unconfigured_without_trusted_settings(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(learning_identity_resolver_from_environment())

    def test_environment_factory_builds_verifier_with_claim_mapping(self):
        env = {
            "MERLIN_OIDC_ISSUER": ISSUER,
            "MERLIN_OIDC_AUDIENCE": AUDIENCE,
            "MERLIN_OIDC_JWKS_URL": "https://identity.example.test/.well-known/jwks.json",
            "MERLIN_OIDC_ALLOWED_ALGORITHMS": "RS256",
            "MERLIN_OIDC_TENANT_CLAIM": "organization_id",
            "MERLIN_OIDC_ROLE_CLAIM": "merlin_role",
            "MERLIN_OIDC_REVOCATION_DB": str(Path(self.id()) if False else Path(os.environ.get("TMPDIR", "/tmp")) / "merlin-oidc-revocations.sqlite3"),
        }
        token = self.token(
            organization_id="tenant-from-idp",
            merlin_role="instructor",
        )
        fake_jwks = FakeJWKSClient(self.public_key)
        with patch.dict(os.environ, env, clear=True), patch(
            "jwt.PyJWKClient", return_value=fake_jwks
        ):
            resolver = learning_identity_resolver_from_environment()
            self.assertIsNotNone(resolver)
            actor = resolver({"Authorization": "Bearer " + token})
        self.assertEqual(actor, Actor("tenant-from-idp", "faculty-17", "instructor"))
        self.assertEqual(fake_jwks.lookups, 1)


if __name__ == "__main__":
    unittest.main()
