"""Synthetic-only implementation of Merlin's standards-based Titan envelope model.

Not the experimental Go-Enigma cipher. No KEM, key persistence, or production
qualification. The trusted host supplies a 32-byte master key; no key in artifacts.
"""
import base64
import hashlib
import os
import re
from python.merlin.artifact_ref import ArtifactRef
from python.merlin.titan_protocol_model import (
    ENVELOPE_SCHEMA,PRODUCTION_SUITE,REQUIRED_ENVELOPE_FIELDS,
    canonical_json_bytes,validate_envelope_structure)
from .research_ingest import MAX_BYTES

def _context(ref):
    ref=ArtifactRef.from_mapping(ref)
    if ref.project_id!="wilborn-demo" or not ref.logical_path.startswith("research/wilborn/synthetic_fixture/"):
        raise PermissionError("Titan integration is synthetic-demo only")
    return {"purpose":"research-artifact","protocol_version":"1",
            "tenant_or_domain":"wilborn-demo","data_class":"synthetic",
            "artifact_ref":ref.to_dict()}

def _metadata(ref,key_id):
    if not isinstance(key_id,str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}",key_id):
        raise ValueError("bounded key identity required")
    return {"schema":ENVELOPE_SCHEMA,"version":1,"suite":dict(PRODUCTION_SUITE),
            "context":_context(ref),"recipient_key_id":key_id}

def _cipher(master_key,nonce,metadata):
    if type(master_key) is not bytes or len(master_key)!=32:
        raise ValueError("host-managed 256-bit master key required")
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV
    key=HKDF(algorithm=hashes.SHA256(),length=32,salt=nonce,
             info=b"merlin-titan-demo-envelope-v1\0"+canonical_json_bytes(metadata)).derive(master_key)
    return AESGCMSIV(key)

def _b64(value):
    return base64.b64encode(value).decode("ascii")

def _decode(value,limit):
    if not isinstance(value,str) or len(value)>4*((limit+2)//3):
        raise ValueError("invalid bounded envelope field")
    decoded=base64.b64decode(value,validate=True)
    if len(decoded)>limit or _b64(decoded)!=value:
        raise ValueError("invalid canonical envelope field")
    return decoded

def seal_demo(content,*,artifact_ref,key_id,master_key):
    metadata=_metadata(artifact_ref,key_id)
    if type(content) is not bytes or not 1<=len(content)<=MAX_BYTES:
        raise ValueError("bounded synthetic artifact required")
    if hashlib.sha256(content).hexdigest()!=metadata["context"]["artifact_ref"]["sha256"]:
        raise ValueError("artifact digest mismatch")
    nonce=os.urandom(12)
    encrypted=_cipher(master_key,nonce,metadata).encrypt(nonce,content,canonical_json_bytes(metadata))
    return {**metadata,"nonce_b64":_b64(nonce),"ciphertext_b64":_b64(encrypted[:-16]),
            "tag_b64":_b64(encrypted[-16:])}

def open_demo(envelope,*,artifact_ref,key_id,master_key):
    expected=_metadata(artifact_ref,key_id)
    if type(envelope) is not dict or set(envelope)!=set(REQUIRED_ENVELOPE_FIELDS):
        raise ValueError("exact Titan envelope required")
    if validate_envelope_structure(envelope):
        raise ValueError("Titan envelope structure rejected")
    actual={k:envelope[k] for k in expected}
    if canonical_json_bytes(actual)!=canonical_json_bytes(expected):
        raise PermissionError("Titan context, suite or key identity mismatch")
    nonce=_decode(envelope["nonce_b64"],12)
    body=_decode(envelope["ciphertext_b64"],MAX_BYTES)
    tag=_decode(envelope["tag_b64"],16)
    if len(nonce)!=12 or len(tag)!=16 or not body:
        raise ValueError("invalid Titan nonce, tag or ciphertext length")
    from cryptography.exceptions import InvalidTag
    try:
        plain=_cipher(master_key,nonce,expected).decrypt(nonce,body+tag,canonical_json_bytes(expected))
    except InvalidTag:
        raise PermissionError("Titan authentication failed") from None
    if hashlib.sha256(plain).hexdigest()!=expected["context"]["artifact_ref"]["sha256"]:
        raise PermissionError("Titan plaintext artifact identity mismatch")
    return plain
