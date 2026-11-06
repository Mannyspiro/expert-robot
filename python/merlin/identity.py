"""Fail-closed OIDC claims-to-Learning-Actor boundary.

This module does NOT parse or cryptographically verify JWTs. A production
`token_verifier` must be backed by a maintained OIDC/OAuth library and must
validate the signature, permitted algorithm, trusted issuer metadata/JWKS,
issuer, audience, token profile and key rotation before returning claims.
For browser authorization-code flows, state and nonce validation belongs in
that OIDC client transaction before an access token reaches this resolver.

Only verified claims are mapped to an Actor. Request headers other than the
Bearer credential, and all request-body identity fields, are ignored.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from math import isfinite
import re
import time
from urllib.parse import urlsplit
from typing import Any

from .learning_platform import Actor, ROLES

TokenVerifier = Callable[[str, str, str], Mapping[str, Any]]
RevocationChecker = Callable[[str, str], bool]
_BEARER = re.compile(r"^Bearer ([A-Za-z0-9._~+/-]+=*)$", re.IGNORECASE)


class OIDCIdentityResolver:
    """Map claims from a trusted verifier to a tenant-scoped Learning Actor.

    `token_verifier(token, issuer, audience)` must return claims only after
    successful cryptographic and OIDC token verification. It must raise on
    invalid credentials. This resolver adds strict claim-to-Actor policy and
    never treats unverified decoded JWT content as trusted.
    """

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        token_verifier: TokenVerifier | None,
        allowed_roles: frozenset[str] | set[str] = frozenset(ROLES),
        revocation_checker: RevocationChecker | None = None,
        clock: Callable[[], float] = time.time,
        clock_skew_seconds: int = 60,
        tenant_claim: str = "tenant_id",
        role_claim: str = "role",
    ) -> None:
        self.issuer = issuer.strip() if isinstance(issuer, str) else ""
        self.audience = audience.strip() if isinstance(audience, str) else ""
        self.token_verifier = token_verifier
        self.allowed_roles = frozenset(allowed_roles) & frozenset(ROLES)
        self.revocation_checker = revocation_checker
        self.clock = clock
        self.tenant_claim = tenant_claim
        self.role_claim = role_claim
        self.clock_skew_seconds = max(0, min(int(clock_skew_seconds), 300))

    @property
    def configured(self) -> bool:
        return bool(self.issuer and self.audience and self.token_verifier
                    and self.allowed_roles)

    @staticmethod
    def _text(claims: Mapping[str, Any], key: str, limit: int = 200) -> str | None:
        value = claims.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            return None
        return value.strip()

    @staticmethod
    def _timestamp(claims: Mapping[str, Any], key: str) -> float | None:
        value = claims.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        return number if isfinite(number) else None

    def __call__(self, headers: Any) -> Actor | None:
        if not self.configured:
            return None
        try:
            authorization = headers.get("Authorization", "")
            if not isinstance(authorization, str) or len(authorization) > 8300:
                return None
            match = _BEARER.fullmatch(authorization.strip())
            if match is None:
                return None
            token = match.group(1)

            # The verifier owns signature, algorithm, issuer metadata/JWKS and
            # OIDC token-profile verification. Any verifier error fails closed.
            claims = self.token_verifier(token, self.issuer, self.audience)
            if not isinstance(claims, Mapping):
                return None

            issuer = self._text(claims, "iss", 2048)
            if issuer != self.issuer:
                return None
            audience = claims.get("aud")
            if isinstance(audience, str):
                audiences = {audience}
            elif isinstance(audience, (list, tuple)) and all(
                isinstance(item, str) for item in audience
            ):
                audiences = set(audience)
            else:
                return None
            if self.audience not in audiences:
                return None

            now = float(self.clock())
            expires = self._timestamp(claims, "exp")
            if expires is None or expires <= now - self.clock_skew_seconds:
                return None
            not_before = self._timestamp(claims, "nbf")
            if not_before is not None and not_before > now + self.clock_skew_seconds:
                return None

            subject = self._text(claims, "sub")
            tenant_id = self._text(claims, self.tenant_claim)
            role = self._text(claims, self.role_claim, 64)
            if not subject or not tenant_id or not role:
                return None
            if role not in self.allowed_roles:
                return None

            token_id = self._text(claims, "jti", 256)
            if self.revocation_checker is not None:
                if not token_id or self.revocation_checker(issuer, token_id):
                    return None

            return Actor(tenant_id=tenant_id, actor_id=subject, role=role)
        except Exception:
            # Do not leak verifier exceptions or token material into HTTP output.
            return None


class PyJWTJWKSVerifier:
    """Production JWT signature/claim verifier backed by PyJWT and a JWKS endpoint.

    Issuer, audience, JWKS URL and the fixed asymmetric algorithm allowlist are
    trusted deployment configuration. The token's unverified header is used
    only by PyJWKClient to select a candidate key; jwt.decode then verifies
    the signature and registered claims using the configured allowlist.
    """

    _ASYMMETRIC_ALGORITHMS = frozenset({
        "RS256", "RS384", "RS512", "PS256", "PS384", "PS512",
        "ES256", "ES384", "ES512", "EdDSA",
    })

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        allowed_algorithms: tuple[str, ...] | list[str],
        leeway_seconds: int = 60,
        timeout_seconds: float = 5,
        jwks_cache_seconds: int = 300,
        jwks_client: Any | None = None,
    ) -> None:
        self.issuer = issuer.strip()
        self.audience = audience.strip()
        self.jwks_url = jwks_url.strip()
        algorithms = frozenset(allowed_algorithms)
        if not self.issuer or not self.audience:
            raise ValueError("OIDC issuer and audience are required")
        if not algorithms or not algorithms.issubset(self._ASYMMETRIC_ALGORITHMS):
            raise ValueError("OIDC algorithms must be a non-empty asymmetric allowlist")
        parsed = urlsplit(self.jwks_url)
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in local_hosts
        ):
            raise ValueError("JWKS URL must use HTTPS except for loopback development")
        if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("JWKS URL is invalid")
        if isinstance(leeway_seconds, bool) or not 0 <= leeway_seconds <= 300:
            raise ValueError("OIDC clock leeway must be between 0 and 300 seconds")
        if timeout_seconds <= 0 or timeout_seconds > 30:
            raise ValueError("JWKS timeout must be greater than 0 and at most 30 seconds")
        if isinstance(jwks_cache_seconds, bool) or not 1 <= jwks_cache_seconds <= 3600:
            raise ValueError("JWKS cache lifetime must be between 1 and 3600 seconds")
        try:
            import jwt
        except ImportError as exc:
            raise RuntimeError("PyJWT[crypto] is required for OIDC JWKS verification") from exc
        self._jwt = jwt
        self.algorithms = tuple(sorted(algorithms))
        self.leeway_seconds = int(leeway_seconds)
        self._jwks = jwks_client or jwt.PyJWKClient(
            self.jwks_url,
            cache_jwk_set=True,
            lifespan=jwks_cache_seconds,
            timeout=timeout_seconds,
            cooldown_duration=0,
        )

    def __call__(self, token: str, expected_issuer: str, expected_audience: str) -> Mapping[str, Any]:
        if expected_issuer != self.issuer or expected_audience != self.audience:
            raise ValueError("OIDC verifier configuration does not match resolver policy")
        signing_key = self._jwks.get_signing_key_from_jwt(token)
        return self._jwt.decode(
            token,
            signing_key.key,
            algorithms=list(self.algorithms),
            issuer=self.issuer,
            audience=self.audience,
            leeway=self.leeway_seconds,
            options={
                "require": ["exp", "iss", "aud", "sub"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
                "verify_nbf": True,
            },
        )


def learning_identity_resolver_from_environment() -> OIDCIdentityResolver | None:
    """Create the production JWKS resolver only when all trusted settings exist."""
    import os

    issuer = os.environ.get("MERLIN_OIDC_ISSUER", "").strip()
    audience = os.environ.get("MERLIN_OIDC_AUDIENCE", "").strip()
    jwks_url = os.environ.get("MERLIN_OIDC_JWKS_URL", "").strip()
    if not issuer or not audience or not jwks_url:
        return None
    algorithms = tuple(
        item.strip() for item in os.environ.get(
            "MERLIN_OIDC_ALLOWED_ALGORITHMS", "RS256"
        ).split(",") if item.strip()
    )
    try:
        verifier = PyJWTJWKSVerifier(
            issuer=issuer,
            audience=audience,
            jwks_url=jwks_url,
            allowed_algorithms=algorithms,
            leeway_seconds=int(os.environ.get("MERLIN_OIDC_LEEWAY_SECONDS", "60")),
            timeout_seconds=float(os.environ.get("MERLIN_OIDC_JWKS_TIMEOUT_SECONDS", "5")),
            jwks_cache_seconds=int(os.environ.get("MERLIN_OIDC_JWKS_CACHE_SECONDS", "300")),
        )
        return OIDCIdentityResolver(
            issuer=issuer,
            audience=audience,
            token_verifier=verifier,
            tenant_claim=os.environ.get("MERLIN_OIDC_TENANT_CLAIM", "tenant_id"),
            role_claim=os.environ.get("MERLIN_OIDC_ROLE_CLAIM", "role"),
        )
    except Exception as exc:
        print("Merlin Learning OIDC verifier unavailable: " + type(exc).__name__)
        return None

