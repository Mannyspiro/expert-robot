"""Bounded research retrieval with provenance; no JS, login, or interactive browser.

Network and file access remain subject to the hosting runtime's policy. A
transport may be injected for offline deterministic tests.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class RetrievalDenied(ValueError):
    pass


@dataclass(frozen=True)
class Retrieval:
    url: str
    final_url: str
    status: int
    content_type: str
    sha256: str
    size_bytes: int
    artifact: str


def _validate_url(url: str, *, resolve: bool = True) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise RetrievalDenied("only absolute http(s) URLs are allowed")
    if parsed.username or parsed.password:
        raise RetrievalDenied("embedded credentials are forbidden")
    if parsed.port not in (None, 80, 443):
        raise RetrievalDenied("nonstandard ports require a separate host policy")
    try:
        literal_ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and not literal_ip.is_global:
        raise RetrievalDenied("non-public network destination")
    if resolve:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        for entry in addresses:
            ip = ipaddress.ip_address(entry[4][0])
            if not ip.is_global:
                raise RetrievalDenied("non-public network destination")


def _default_transport(url: str, max_bytes: int, timeout: float) -> tuple[str, int, str, bytes]:
    class CheckedRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            _validate_url(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(CheckedRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": "MerlinResearch/0.1"})
    with opener.open(request, timeout=timeout) as response:
        final_url = response.geturl()
        _validate_url(final_url)
        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise RetrievalDenied("response exceeds byte budget")
        return final_url, response.status, response.headers.get("Content-Type", "application/octet-stream"), content


def retrieve(
    url: str,
    evidence_dir: Path,
    *,
    max_bytes: int = 2_000_000,
    timeout: float = 12.0,
    transport: Callable[[str, int, float], tuple[str, int, str, bytes]] | None = None,
) -> Retrieval:
    if not 0 < max_bytes <= 10_000_000 or not 0 < timeout <= 60:
        raise ValueError("invalid retrieval budget")
    _validate_url(url, resolve=transport is None)
    final_url, status, content_type, content = (transport or _default_transport)(url, max_bytes, timeout)
    _validate_url(final_url, resolve=transport is None)
    if not 200 <= status < 300 or len(content) > max_bytes:
        raise RetrievalDenied("non-success response or byte budget exceeded")
    digest = hashlib.sha256(content).hexdigest()
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    artifact = evidence_dir / (digest + ".bin")
    artifact.write_bytes(content)
    receipt = Retrieval(url, final_url, status, content_type, digest, len(content), str(artifact))
    (evidence_dir / (digest + ".json")).write_text(json.dumps(receipt.__dict__, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
