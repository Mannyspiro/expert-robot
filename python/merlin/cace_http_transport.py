"""Bounded HTTPS transport for independent CACE verification.

The transport authenticates to an externally operated CACE verifier. It never
creates a verification result locally: the adapter validates the exact receipt
returned by the remote service.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a bearer credential to a redirect target.
        return None


class CaceHTTPTransport:
    def __init__(
        self,
        endpoint: str,
        bearer_token: str,
        *,
        timeout_seconds: float = 15,
        max_request_bytes: int = 36_000_000,
        max_response_bytes: int = 1_000_000,
        opener: Any | None = None,
        allow_loopback_http: bool = False,
    ):
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError("CACE endpoint is required")
        parsed = urlsplit(endpoint)
        loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if (parsed.scheme != "https" and not (allow_loopback_http and loopback and parsed.scheme == "http")):
            raise ValueError("CACE verifier endpoint must use HTTPS")
        if not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError("CACE verifier endpoint must have a host and no embedded credentials")
        if parsed.fragment:
            raise ValueError("CACE verifier endpoint must not contain a fragment")
        if not isinstance(bearer_token, str) or len(bearer_token) < 32 or not bearer_token.isascii():
            raise ValueError("CACE bearer token must be at least 32 ASCII characters")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 1 <= timeout_seconds <= 60:
            raise ValueError("CACE timeout must be between 1 and 60 seconds")
        for value, label, maximum in (
            (max_request_bytes, "max_request_bytes", 40_000_000),
            (max_response_bytes, "max_response_bytes", 4_000_000),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
                raise ValueError(label + " is outside its allowed range")
        self.endpoint = endpoint
        self._token = bearer_token
        self.timeout_seconds = float(timeout_seconds)
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes
        self.opener = opener or build_opener(_NoRedirect())

    def __call__(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise ValueError("CACE request must be an object")
        try:
            body = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("CACE request is not canonical JSON") from exc
        if not body or len(body) > self.max_request_bytes:
            raise ValueError("CACE request exceeds the configured size limit")
        idempotency_key = hashlib.sha256(body).hexdigest()
        request = Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": "Bearer " + self._token,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            method="POST",
        )
        try:
            response = self.opener.open(request, timeout=self.timeout_seconds)
            status = getattr(response, "status", 200)
            raw = response.read(self.max_response_bytes + 1)
        except HTTPError as exc:
            # Do not include response bodies, URLs or credentials in raised errors.
            raise RuntimeError("CACE verifier returned HTTP " + str(exc.code)) from None
        except URLError as exc:
            raise RuntimeError("CACE verifier transport failed: " + type(exc.reason).__name__) from None
        except TimeoutError:
            raise RuntimeError("CACE verifier request timed out") from None
        if status < 200 or status >= 300:
            raise RuntimeError("CACE verifier returned HTTP " + str(status))
        if not isinstance(raw, bytes) or len(raw) > self.max_response_bytes:
            raise RuntimeError("CACE verifier response exceeded the configured size limit")
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("CACE verifier returned invalid JSON") from None
        if not isinstance(result, dict):
            raise RuntimeError("CACE verifier response must be a JSON object")
        return result


def cace_transport_from_environment(*, opener: Any | None = None) -> CaceHTTPTransport | None:
    """Return None only when both endpoint and token are absent; partial config fails."""
    endpoint = os.environ.get("CACE_VERIFY_URL", "").strip()
    token = os.environ.get("CACE_VERIFY_TOKEN", "")
    if not endpoint and not token:
        return None
    if not endpoint or not token:
        raise ValueError("CACE_VERIFY_URL and CACE_VERIFY_TOKEN must be configured together")
    try:
        timeout = float(os.environ.get("CACE_VERIFY_TIMEOUT_SECONDS", "15"))
        max_request = int(os.environ.get("CACE_VERIFY_MAX_REQUEST_BYTES", "36000000"))
        max_response = int(os.environ.get("CACE_VERIFY_MAX_RESPONSE_BYTES", "1000000"))
    except ValueError as exc:
        raise ValueError("CACE verifier transport limits must be numeric integers/seconds") from exc
    return CaceHTTPTransport(
        endpoint, token, timeout_seconds=timeout,
        max_request_bytes=max_request, max_response_bytes=max_response,
        opener=opener,
    )


__all__ = ["CaceHTTPTransport", "cace_transport_from_environment"]
