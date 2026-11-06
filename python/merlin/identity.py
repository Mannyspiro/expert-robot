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
    ) -> None:
        self.issuer = issuer.strip() if isinstance(issuer, str) else ""
        self.audience = audience.strip() if isinstance(audience, str) else ""
        self.token_verifier = token_verifier
        self.allowed_roles = frozenset(allowed_roles) & frozenset(ROLES)
        self.revocation_checker = revocation_checker
        self.clock = clock
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
            tenant_id = self._text(claims, "tenant_id")
            role = self._text(claims, "role", 64)
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
