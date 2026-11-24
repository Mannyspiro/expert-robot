"""Receipt-verified public retrieval boundary.

This module does not open sockets. A separately secured fetch provider must
enforce network egress, redirect policy, DNS/IP checks, TLS, robots and rate limits.
"""
from dataclasses import dataclass
from hashlib import sha256
from .research_ingest import ingest_public_text, validate_url, MAX_BYTES

@dataclass(frozen=True)
class FetchReceipt:
    requested_url: str
    final_url: str
    status: int
    content_type: str
    body: bytes
    redirect_count: int
    egress_policy_verified: bool
    tls_verified: bool
    access_policy_verified: bool

def accept_receipt(receipt):
    if not isinstance(receipt, FetchReceipt):
        raise TypeError("typed fetch receipt required")
    validate_url(receipt.requested_url)
    validate_url(receipt.final_url)
    if receipt.requested_url != receipt.final_url or receipt.redirect_count != 0:
        raise PermissionError("redirects not accepted by prototype boundary")
    if type(receipt.status) is not int or receipt.status != 200:
        raise ValueError("successful HTTP response required")
    if receipt.content_type not in ("text/html", "text/plain", "text/csv"):
        raise PermissionError("unsupported content type")
    if not all(x is True for x in (
        receipt.egress_policy_verified, receipt.tls_verified,
        receipt.access_policy_verified)):
        raise PermissionError("verified fetch policy required")
    if not isinstance(receipt.body, bytes) or len(receipt.body) > MAX_BYTES:
        raise ValueError("invalid response body")
    evidence=ingest_public_text(receipt.final_url,receipt.body)
    return {
        "evidence": evidence,
        "receipt_sha256": sha256(receipt.body).hexdigest(),
        "retrieval_assurance": "provider_asserted_not_independently_attested",
        "data_class": "public_research",
    }
