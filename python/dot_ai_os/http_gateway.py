"""Authenticated, loopback-only MCP read plane. Deployment candidate, not a live service.

An external OAuth authorization server issues tokens. This module only consumes
RFC 7662 introspection from one operator-configured HTTPS endpoint and acts as
an MCP resource server. It never issues tokens or reuses other apps' credentials.
Publish only through an operator-provisioned private tunnel/authenticated HTTPS
gateway; the listener remains on 127.0.0.1. No remote endpoint is created here.
"""
from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from typing import Any
from urllib.parse import urlsplit

import httpx
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl

from merlin.project_registry import MerlinRegistry
from .bridge import DotContextBridge, canonical
from .mcp_server import ReceiptDialogue, create_server

READ_SCOPE = "merlin:context:read"
Introspection = Callable[[str], Awaitable[Mapping[str, Any]]]


class GatewayConfigurationError(ValueError):
    """Required host-owned identity configuration is absent or invalid."""


class ReadOnlyRegistryError(PermissionError):
    """The read plane cannot mutate the canonical registry or blob store."""


class ReadOnlyMerlinRegistry(MerlinRegistry):
    """Canonical readers with no initialization/migrations and mode=ro SQLite.

    Host filesystem controls must also keep the process account read-only. This
    subclass blocks normal mutation methods; it is not an OS sandbox against
    arbitrary Python executed by a compromised host.
    """
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve(strict=True)
        self.blobs = self.root / "blobs" / "sha256"
        self.db_path = self.root / "merlin.sqlite3"
        if self.db_path.is_symlink() or not self.db_path.is_file() or not self.blobs.is_dir():
            raise GatewayConfigurationError("existing canonical registry and blob directory required")
        self._check_journal()

    def _check_journal(self):
        # mode=ro alone can create -wal/-shm files. Refuse WAL before SQLite
        # opens it. Do not use immutable=1 on a live-changing database: that
        # would make a stronger and false promise about source immutability.
        with self.db_path.open("rb") as stream:
            header = stream.read(100)
        if len(header) != 100 or header[:16] != b"SQLite format 3\x00":
            raise GatewayConfigurationError("existing initialized SQLite registry required")
        if header[18:20] != b"\x01\x01":
            raise GatewayConfigurationError("WAL registry requires a host-published read snapshot")

    def _connect(self):
        self._check_journal()
        db = sqlite3.connect(self.db_path.as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA query_only=ON")
        except Exception:
            db.close()
            raise
        return db

    @staticmethod
    def _deny(*args, **kwargs):
        raise ReadOnlyRegistryError("the HTTP registry is read-only")

    _initialize = _deny
    register_project = _deny
    put_artifact = _deny
    add_claim = _deny
    relate = _deny
    record_capability_qualification = _deny


def _https_url(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 2000:
        raise GatewayConfigurationError(f"{name} must be a fixed HTTPS URL")
    parsed = urlsplit(value)
    try:
        parsed.port
    except ValueError as exc:
        raise GatewayConfigurationError(f"invalid {name} port") from exc
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or any(ord(c) <= 32 or ord(c) >= 127 for c in value)):
        raise GatewayConfigurationError(f"{name} must be credential-free HTTPS without query or fragment")
    return value


@dataclass(frozen=True)
class GatewayConfig:
    issuer_url: str
    introspection_url: str
    resource_url: str
    allowed_subjects: tuple[str, ...]
    port: int = 8766
    introspection_timeout_seconds: float = 5.0
    introspection_max_bytes: int = 65536

    def __post_init__(self):
        for name in ("issuer_url", "introspection_url", "resource_url"):
            _https_url(getattr(self, name), name)
        if urlsplit(self.resource_url).path != "/mcp":
            raise GatewayConfigurationError("resource_url must identify the exact /mcp endpoint")
        subjects = self.allowed_subjects
        if (not isinstance(subjects, tuple) or not subjects or len(subjects) > 100
                or any(not isinstance(s, str) or not s.strip() or len(s) > 500 for s in subjects)
                or len(set(subjects)) != len(subjects)):
            raise GatewayConfigurationError("an explicit nonempty tuple of unique allowed subjects is required")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise GatewayConfigurationError("port must be an integer in [1, 65535]")
        if (type(self.introspection_timeout_seconds) not in (int, float)
                or not math.isfinite(self.introspection_timeout_seconds)
                or not 0 < self.introspection_timeout_seconds <= 30):
            raise GatewayConfigurationError("introspection timeout must be finite and at most 30 seconds")
        if type(self.introspection_max_bytes) is not int or not 1 <= self.introspection_max_bytes <= 1024 * 1024:
            raise GatewayConfigurationError("introspection response ceiling must be 1 byte through 1 MiB")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GatewayConfig":
        required = {"issuer_url", "introspection_url", "resource_url", "allowed_subjects"}
        optional = {"port", "introspection_timeout_seconds", "introspection_max_bytes"}
        if not isinstance(value, Mapping) or not required <= set(value) or not set(value) <= required | optional:
            raise GatewayConfigurationError("exact required gateway identity settings are missing or unknown")
        data = dict(value)
        if not isinstance(data["allowed_subjects"], (list, tuple)):
            raise GatewayConfigurationError("allowed_subjects must be an explicit list")
        data["allowed_subjects"] = tuple(data["allowed_subjects"])
        return cls(**data)


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate introspection JSON member")
        result[name] = value
    return result


def _invalid_constant(value):
    raise ValueError("nonfinite JSON numeric literal")


class HTTPIntrospector:
    """Bounded POST to one fixed HTTPS endpoint, without redirects or proxy env.

    Optional credentials are dedicated introspection-client credentials supplied
    by the operator. No token, secret, response body or credential enters logs.
    transport is an explicitly host-injected httpx test transport, never a tool input.
    """
    def __init__(self, config: GatewayConfig, *, client_id: str | None = None,
                 client_secret: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        if not isinstance(config, GatewayConfig):
            raise GatewayConfigurationError("gateway configuration required")
        if (client_id is None) != (client_secret is None):
            raise GatewayConfigurationError("introspection credentials must be configured together")
        if client_id is not None and (not isinstance(client_id, str) or not client_id.strip()
                or not isinstance(client_secret, str) or not client_secret):
            raise GatewayConfigurationError("empty introspection credentials are invalid")
        self.config = config
        self._auth = httpx.BasicAuth(client_id, client_secret) if client_id is not None else None
        self._transport = transport

    async def __call__(self, token: str) -> Mapping[str, Any]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.config.introspection_timeout_seconds),
                follow_redirects=False, trust_env=False, transport=self._transport,
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=0)) as client:
            async with client.stream("POST", self.config.introspection_url,
                    data={"token": token, "token_type_hint": "access_token"}, auth=self._auth,
                    headers={"Accept": "application/json", "Accept-Encoding": "identity"}) as response:
                if response.status_code != 200:
                    raise ValueError("introspection did not return success")
                if response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                    raise ValueError("introspection requires JSON content type")
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise ValueError("compressed introspection responses are not accepted")
                length = response.headers.get("content-length")
                if length is not None and (not length.isdecimal() or int(length) > self.config.introspection_max_bytes):
                    raise ValueError("introspection response length exceeds bound or is malformed")
                data = bytearray()
                async for block in response.aiter_raw():
                    if len(data) + len(block) > self.config.introspection_max_bytes:
                        raise ValueError("introspection response exceeds byte ceiling")
                    data.extend(block)
        value = json.loads(data, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        if not isinstance(value, dict):
            raise ValueError("introspection root must be an object")
        return value


class IntrospectionTokenVerifier(TokenVerifier):
    """Fail-closed SDK verifier with fixed subject, issuer and resource policy.

    Introspection transport authenticates the issuer's assertion. The assertion
    is not a CACE receipt or proof of mathematical correctness. No auth cache is
    used: revocation/expiry is checked through introspection for each request.
    """
    def __init__(self, config: GatewayConfig, introspect: Introspection,
                 *, clock: Callable[[], float] = time.time):
        if not isinstance(config, GatewayConfig) or not callable(introspect) or not callable(clock):
            raise GatewayConfigurationError("configured introspection verifier required")
        self.config, self._introspect, self._clock = config, introspect, clock

    async def verify_token(self, token: str) -> AccessToken | None:
        if (not isinstance(token, str) or not 1 <= len(token) <= 8192
                or re.fullmatch(r"[A-Za-z0-9._~+/=-]+", token) is None):
            return None
        try:
            result = await asyncio.wait_for(self._introspect(token),
                                           timeout=self.config.introspection_timeout_seconds)
            if not isinstance(result, Mapping) or len(result) > 128:
                return None
            if len(canonical(dict(result))) > self.config.introspection_max_bytes or result.get("active") is not True:
                return None
            now = self._clock()
            expiry = result.get("exp")
            if (type(now) not in (int, float) or not math.isfinite(now)
                    or type(expiry) not in (int, float) or not math.isfinite(expiry) or expiry <= now):
                return None
            for field in ("nbf", "iat"):
                value = result.get(field)
                if value is not None and (type(value) not in (int, float)
                        or not math.isfinite(value) or value > now):
                    return None
            if "iss" in result and result["iss"] != self.config.issuer_url:
                return None
            if result.get("sub") not in self.config.allowed_subjects:
                return None
            # SDK 1.29 lacks validate_token_resource; enforce it here. A list
            # audience may contain other entries, but must contain this exact URL.
            audience = result.get("aud")
            if isinstance(audience, str):
                audience_ok = audience == self.config.resource_url
            else:
                audience_ok = (isinstance(audience, list) and bool(audience)
                               and all(isinstance(x, str) and x for x in audience)
                               and self.config.resource_url in audience)
            if not audience_ok:
                return None
            if "resource" in result and result["resource"] != self.config.resource_url:
                return None
            client_id = result.get("client_id")
            if not isinstance(client_id, str) or not client_id.strip() or len(client_id) > 500:
                return None
            scope = result.get("scope", "")
            if not isinstance(scope, str) or len(scope) > 4096:
                return None
            scopes = scope.split(" ") if scope else []
            if any(not re.fullmatch(r"[\x21\x23-\x5b\x5d-\x7e]+", item) for item in scopes):
                return None
            # Missing required read scope is deliberately returned to the SDK's
            # RequireAuthMiddleware, which responds with a 403 scope challenge.
            return AccessToken(token=token, client_id=client_id, scopes=scopes,
                               expires_at=math.ceil(expiry), resource=self.config.resource_url,
                               subject=result["sub"], claims={"iss": self.config.issuer_url})
        except Exception:
            # Do not disclose exception text: provider errors can contain tokens.
            return None


@dataclass(frozen=True)
class SubjectReadScope:
    """Operator-selected read bridge and constructor for its pinned receipt catalogue."""
    bridge: DotContextBridge
    dialogue: Callable[[DotContextBridge], ReceiptDialogue]


def create_http_server(bridge: DotContextBridge, *, config: GatewayConfig,
                       token_verifier: IntrospectionTokenVerifier,
                       subject_scopes: Mapping[str, SubjectReadScope] | None = None) -> FastMCP:
    if (not isinstance(config, GatewayConfig) or not isinstance(token_verifier, IntrospectionTokenVerifier)
            or token_verifier.config != config):
        raise GatewayConfigurationError("matching fixed gateway and token verifier configuration required")
    if not isinstance(bridge.registry, ReadOnlyMerlinRegistry):
        raise GatewayConfigurationError("HTTP requires the migration-free read-only registry")
    origin = urlsplit(config.resource_url)
    request_bridge = new_dialogue = None
    if subject_scopes is not None:
        scopes = dict(subject_scopes)
        if set(scopes) != set(config.allowed_subjects) or any(
            not isinstance(scope, SubjectReadScope) or not callable(scope.dialogue)
            or not isinstance(scope.bridge.registry, ReadOnlyMerlinRegistry) for scope in scopes.values()
        ):
            raise GatewayConfigurationError("one complete read-only scope per allowed subject required")

        def current_scope():
            token = get_access_token()
            if token is None or token.subject not in scopes:
                raise PermissionError("authenticated read scope required")
            return scopes[token.subject]

        def request_bridge():
            return current_scope().bridge

        def new_dialogue():
            scope = current_scope()
            return scope.dialogue(scope.bridge)

    return create_server(bridge, request_bridge=request_bridge, new_receipt_dialogue=new_dialogue, server_options={
        "host": "127.0.0.1", "port": config.port,
        "json_response": True, "stateless_http": True,
        "max_request_body_size": 65536,
        "token_verifier": token_verifier,
        "auth": AuthSettings(issuer_url=AnyHttpUrl(config.issuer_url),
                             resource_server_url=AnyHttpUrl(config.resource_url),
                             required_scopes=[READ_SCOPE]),
        "transport_security": TransportSecuritySettings(enable_dns_rebinding_protection=True,
            allowed_hosts=[origin.netloc, f"127.0.0.1:{config.port}"],
            allowed_origins=[f"https://{origin.netloc}"]),
    })


def build_http_gateway(*, root: str | Path, namespaces: tuple[str, ...],
                       config: GatewayConfig | None,
                       subject_scopes: Mapping[str, SubjectReadScope] | None = None,
                       introspect: Introspection | None = None,
                       client_id: str | None = None, client_secret: str | None = None) -> FastMCP:
    """Construct without listening. Config absent refuses before touching registry."""
    if not isinstance(config, GatewayConfig):
        raise GatewayConfigurationError("real operator-provisioned OAuth configuration is required")
    callback = introspect if introspect is not None else HTTPIntrospector(
        config, client_id=client_id, client_secret=client_secret)
    verifier = IntrospectionTokenVerifier(config, callback)
    bridge = DotContextBridge(ReadOnlyMerlinRegistry(root), namespaces=namespaces)
    bridge.status()  # Ensure project/schema/source scope already exists; never initialize it.
    return create_http_server(bridge, config=config, token_verifier=verifier, subject_scopes=subject_scopes)


def main():
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--namespaces", required=True, nargs="+")
    parser.add_argument("--config", required=True, type=Path,
                        help="host-owned JSON identity settings; no credentials in this file")
    args = parser.parse_args()
    try:
        config = GatewayConfig.from_mapping(json.loads(args.config.read_text("utf-8")))
        server = build_http_gateway(root=args.root, namespaces=tuple(args.namespaces), config=config,
            client_id=os.environ.get("MERLIN_INTROSPECTION_CLIENT_ID"),
            client_secret=os.environ.get("MERLIN_INTROSPECTION_CLIENT_SECRET"))
    except (OSError, ValueError) as exc:
        parser.error(type(exc).__name__ + ": gateway startup refused; check host-owned configuration")
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
