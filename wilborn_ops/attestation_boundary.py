"""Reuse Merlin's pinned CACE Ed25519 verifier; no signing keys or promotion."""
from datetime import datetime, timezone
import hashlib
import json
from python.merlin.cace_attestation import verify_cace_signed_attestation

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,
                      allow_nan=False).encode("utf-8")

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def fresh_attestation(envelope, *, trust, claim_id, bundle_sha256, bindings,
                      requester_id, purpose, now=None, max_age_seconds=3600):
    if type(envelope) is not dict or len(canonical(envelope))>32768:
        raise ValueError("bounded signed attestation required")
    if type(max_age_seconds) is not int or not 1<=max_age_seconds<=86400:
        raise ValueError("invalid freshness policy")
    verified=verify_cace_signed_attestation(
        envelope,trusted_verifier_keys=trust,expected_claim_id=claim_id,
        expected_bundle_sha256=bundle_sha256,expected_bindings=bindings,
        requester_id=requester_id)
    statement=envelope["statement"]
    if verified["purpose"]!=purpose or canonical(statement["bindings"])!=canonical(bindings):
        raise PermissionError("attestation purpose or exact binding mismatch")
    issued=datetime.strptime(statement["created_at_utc"],"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    current=now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("timezone-aware host clock required")
    age=(current-issued).total_seconds()
    if not 0<=age<=max_age_seconds:
        raise PermissionError("attestation outside freshness window")
    return verified

def separated_trust(left,right):
    """Host trust configuration, not data from an LLM or request."""
    if not left or not right or len(left)>16 or len(right)>16:
        raise PermissionError("separate pinned signer sets required")
    if set(left)&set(right):
        raise PermissionError("signer keys must be distinct")
    left_ids={v["verifier_id"] for v in left.values()}
    right_ids={v["verifier_id"] for v in right.values()}
    if left_ids&right_ids:
        raise PermissionError("signer identities must be distinct")
