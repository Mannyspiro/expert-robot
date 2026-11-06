import unittest

from python.merlin.identity import OIDCIdentityResolver
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


if __name__ == "__main__":
    unittest.main()
