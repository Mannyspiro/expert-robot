#!/usr/bin/env python3
"""Check this narrow deployment profile without making network or service changes.

The .yml template intentionally uses JSON syntax (a YAML subset), so this gate
needs only the standard library. cloudflared's own ingress validation is an
additional required gate. This checks config agreement, not a live Access policy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import stat
import urllib.parse
import uuid


GATEWAY_KEYS = {"schema", "contract_version", "public_origin", "team_name",
                "audiences", "identity_verifier"}
HOST = re.compile(r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
                  r"[a-z][a-z0-9-]{0,61}[a-z0-9]\Z")
TEAM = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
AUDIENCE = re.compile(r"[A-Za-z0-9_-]{8,256}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate configuration key")
        result[key] = value
    return result


def load(path):
    path = Path(path)
    metadata = path.lstat()
    require(stat.S_ISREG(metadata.st_mode), "Configuration must be a regular file, not a symlink")
    require(metadata.st_uid == 0, "Deployment configuration must be owned by root")
    require(not metadata.st_mode & 0o022, "Deployment configuration must not be group/world writable")
    require(metadata.st_size <= 32768, "Configuration exceeds 32 KiB")
    text = path.read_text(encoding="utf-8")
    require("REPLACE_WITH_" not in text, "Unresolved deployment placeholder")
    value = json.loads(text, object_pairs_hook=unique_object)
    require(isinstance(value, dict), "Configuration must be an object")
    return value


def validate(gateway, tunnel):
    require("REPLACE_WITH_" not in json.dumps([gateway, tunnel]), "Unresolved deployment placeholder")
    require(set(gateway) == GATEWAY_KEYS, "Unexpected or missing gateway fields")
    require(gateway["schema"] == "merlin-studio-trusted-gateway/1", "Wrong gateway schema")
    require(type(gateway["contract_version"]) is int and gateway["contract_version"] == 1,
            "Wrong gateway contract version")
    require(gateway["identity_verifier"] == "cloudflared-access-required", "Unsupported identity verifier")
    origin = gateway["public_origin"]
    require(isinstance(origin, str), "Origin must be text")
    parsed = urllib.parse.urlsplit(origin)
    host = parsed.hostname or ""
    require(HOST.fullmatch(host) is not None and host == host.lower(), "Origin requires a lowercase DNS hostname")
    require(origin == "https://" + host, "Origin must be one HTTPS DNS origin with no port, path, query or fragment")
    require(not host.endswith((".invalid", ".example", ".test", ".localhost", ".local"))
            and host not in {"example.com", "example.net", "example.org"}, "Example/local hostname is not a deployment identity")
    team = gateway["team_name"]
    audiences = gateway["audiences"]
    require(isinstance(team, str) and TEAM.fullmatch(team) is not None, "Invalid Access team slug")
    require(isinstance(audiences, list) and 0 < len(audiences) <= 8, "One to eight explicit application audiences are required")
    require(all(isinstance(a, str) and AUDIENCE.fullmatch(a) is not None for a in audiences),
            "Use the exact Access application AUDs from the approved configuration")
    require(len(set(audiences)) == len(audiences), "Duplicate application audiences")
    require(set(tunnel) == {"tunnel", "credentials-file", "metrics", "ingress"}, "Unexpected or missing tunnel fields")
    tunnel_id = tunnel["tunnel"]
    require(isinstance(tunnel_id, str) and str(uuid.UUID(tunnel_id)) == tunnel_id
            and uuid.UUID(tunnel_id).int != 0, "Use the existing tunnel's canonical UUID")
    require(tunnel["credentials-file"] == "/etc/merlin-studio-tunnel/credentials.json", "Unexpected credential path")
    require(tunnel["metrics"] == "127.0.0.1:20241", "Metrics must remain on the declared loopback port")
    expected = [
        {"hostname": host, "service": "http://127.0.0.1:8771", "originRequest": {
            "httpHostHeader": host, "access": {"required": True, "teamName": team, "audTag": audiences}}},
        {"service": "http_status:404"},
    ]
    require(tunnel["ingress"] == expected,
            "Tunnel must exactly match the protected hostname, loopback target, per-rule Access verifier and rejecting catch-all")
    # bool is a subclass of int; equality alone would accept required=1.
    require(tunnel["ingress"][0]["originRequest"]["access"]["required"] is True,
            "Access required must be the JSON Boolean true")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", type=Path, required=True)
    parser.add_argument("--tunnel", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(load(args.gateway), load(args.tunnel))
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        # Do not echo parsed values, credentials, or complete files.
        parser.exit(2, "Deployment configuration rejected: " + type(exc).__name__ + "\n")
    print("Configuration agreement passed; live Access policy, host isolation and end-to-end checks are still required.")


if __name__ == "__main__":
    main()
