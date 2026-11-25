"""Explicit single-owner origin contract for a verifying local Access gateway.

This module does not verify a Cloudflare JWT. The independently configured
cloudflared ingress must validate Access (required/teamName/audTag) before
forwarding to the loopback listener. No forwarded header grants authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


@dataclass(frozen=True)
class GatewayContract:
    public_origin: str
    hostname: str
    team_name: str
    audiences: tuple[str, ...]

    def status(self):
        return {
            "mode": "trusted_gateway",
            "public_origin": self.public_origin,
            "identity_verifier": "cloudflared-access-required",
            "application_verifies_access_jwt": False,
            "scope": "single_owner_shared_workspace",
        }


def load_gateway_contract(path):
    if path is None:
        return None
    raw = Path(path).read_bytes()
    if len(raw) > 16384:
        raise ValueError("Gateway contract is too large")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate gateway contract field")
            result[key] = value
        return result
    data = json.loads(raw, object_pairs_hook=unique)
    fields = {"schema", "contract_version", "public_origin", "team_name", "audiences", "identity_verifier"}
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError("Gateway contract fields are incomplete or unsupported")
    if (data["schema"] != "merlin-studio-trusted-gateway/1"
            or type(data["contract_version"]) is not int or data["contract_version"] != 1
            or data["identity_verifier"] != "cloudflared-access-required"):
        raise ValueError("Unsupported gateway verification contract")
    origin = data["public_origin"]
    if not isinstance(origin, str) or len(origin) > 260:
        raise ValueError("A single canonical HTTPS public origin is required")
    parsed = urlsplit(origin)
    hostname = parsed.hostname or ""
    if (parsed.scheme != "https" or origin != "https://" + hostname
            or len(hostname) > 253 or "." not in hostname
            or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                   for label in hostname.split("."))):
        raise ValueError("A canonical HTTPS hostname without port, path or credentials is required")
    team = data["team_name"]
    if not isinstance(team, str) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", team):
        raise ValueError("Invalid Access team name")
    audiences = data["audiences"]
    if (not isinstance(audiences, list) or not 1 <= len(audiences) <= 8
            or any(not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,256}", item)
                   for item in audiences)
            or len(set(audiences)) != len(audiences)):
        raise ValueError("One to eight distinct Access audience tags are required")
    return GatewayContract(origin, hostname, team, tuple(audiences))


def check_request_boundary(headers, port, gateway, session_token, *, mutation=False):
    """Validate the origin boundary; identity remains the gateway's responsibility."""
    import hmac
    for name in ("Host", "Origin", "Sec-Fetch-Site", "X-Merlin-Token", "Cf-Access-Jwt-Assertion", "Content-Type"):
        values = headers.get_all(name, [])
        if len(values) > 1 or (name == "Host" and len(values) != 1):
            raise PermissionError("Ambiguous request boundary header")
    local_hosts = {"127.0.0.1:" + str(port), "localhost:" + str(port)}
    if port == 80:
        local_hosts.update({"127.0.0.1", "localhost"})
    host = headers.get("Host", "").lower()
    if host in local_hosts:
        allowed_origins = {"http://" + item for item in local_hosts}
    elif gateway is not None and host == gateway.hostname:
        assertion = headers.get("Cf-Access-Jwt-Assertion", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", assertion) or len(assertion) > 16384:
            raise PermissionError("The configured Access gateway assertion is required")
        allowed_origins = {gateway.public_origin}
    else:
        raise PermissionError("Unrecognized local Host header or configured public hostname")
    origin = headers.get("Origin")
    if origin is not None and origin not in allowed_origins:
        raise PermissionError("Cross-origin requests are not accepted")
    if headers.get("Sec-Fetch-Site") == "cross-site":
        raise PermissionError("Cross-site requests are not accepted")
    if mutation:
        supplied = headers.get("X-Merlin-Token", "")
        if not hmac.compare_digest(supplied.encode(), session_token.encode()):
            raise PermissionError("Reload Studio to obtain the current local session")
        if headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise ValueError("Content-Type must be application/json")
        if headers.get("Transfer-Encoding") is not None:
            raise ValueError("Chunked request bodies are not accepted")
