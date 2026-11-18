"""Bounded Titan wrapper over the installed cryptography HPKE implementation.

Fixed opt-in profile: cryptography 50.0.2 / OpenSSL 4.0.3, ML-KEM-768,
HKDF-SHA256 and AES-256-GCM through Suite.encrypt/decrypt. No KEM, KDF,
AEAD, hybrid combiner or nonce construction is implemented here. Dependency
absence/version mismatch blocks rather than falling back to classical crypto.

The board/history/message is entirely encrypted. An authenticated internal
length plus fixed-bucket random padding hides exact payload length within the
selected bucket. Public metadata still exposes schema, suite, generic context,
bucket and traffic timing. Base-mode HPKE supplies no sender identity, replay
prevention, forward secrecy against recipient-key compromise, key custody,
secure Python memory erasure, padding against traffic analysis, or production
qualification. Public context must contain generic application labels only.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from typing import Any

SCHEMA = 'titan-pq-envelope/1'
SUITE = 'HPKE-ML-KEM-768-HKDF-SHA256-AES-256-GCM'
CRYPTOGRAPHY_VERSION = '50.0.2'
OPENSSL_BACKEND_VERSION = 'OpenSSL 4.0.3 29 Sep 2026'
PADDING_BUCKETS = (4096, 16384, 65536, 262144, 1048576)
DEFAULT_PAD_TO = 65536
MAX_PAYLOAD_BYTES = PADDING_BUCKETS[-1] - 8
MAX_ENVELOPE_BYTES = 1500000
_ENC_BYTES = 1088
_TAG_BYTES = 16


class TitanDependencyUnavailable(RuntimeError):
    """The explicitly tested maintained implementation is unavailable."""


class TitanDecryptionError(ValueError):
    """Generic envelope/key/context/authentication failure; no plaintext returned."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
        allow_nan=False,
    ).encode('utf-8')


def _backend():
    try:
        import cryptography
        from cryptography.hazmat.backends.openssl.backend import backend
        from cryptography.hazmat.primitives.asymmetric.mlkem import (
            MLKEM768PrivateKey,
            MLKEM768PublicKey,
        )
        from cryptography.hazmat.primitives.hpke import AEAD, KDF, KEM, Suite

        if (
            cryptography.__version__ != CRYPTOGRAPHY_VERSION
            or backend.openssl_version_text() != OPENSSL_BACKEND_VERSION
        ):
            raise ValueError('unreviewed dependency version')
        suite = Suite(KEM.MLKEM768, KDF.HKDF_SHA256, AEAD.AES_256_GCM)
        if KEM.MLKEM768.enc_length() != _ENC_BYTES:
            raise ValueError('unexpected KEM encoding')
        return (suite, MLKEM768PrivateKey, MLKEM768PublicKey)
    except Exception:
        raise TitanDependencyUnavailable('pinned Titan HPKE backend unavailable') from None


def backend_status() -> dict[str, Any]:
    """Perform a real ephemeral backend roundtrip; report non-secret provenance."""
    try:
        suite, private_type, _ = _backend()
        key = private_type.generate()
        encrypted = suite.encrypt(b'backend-check', key.public_key(), info=b'Titan-backend-check-v1')
        if suite.decrypt(encrypted, key, info=b'Titan-backend-check-v1') != b'backend-check':
            raise ValueError('backend mismatch')
    except Exception:
        return {'available': False, 'profile': SUITE, 'qualification': False, 'promotion_authority': False}
    return {
        'available': True,
        'profile': SUITE,
        'cryptography_version': CRYPTOGRAPHY_VERSION,
        'openssl_backend_version': OPENSSL_BACKEND_VERSION,
        'real_roundtrip': True,
        'source': f'https://cryptography.io/en/{CRYPTOGRAPHY_VERSION}/hazmat/primitives/hpke/',
        'qualification': False,
        'promotion_authority': False,
    }


def _context(value):
    # Board parameters, history and fingerprints belong inside the ciphertext.
    if type(value) is not dict or set(value) != {'purpose', 'schema'}:
        raise ValueError('only generic public purpose/schema labels are permitted')
    for text in value.values():
        if not isinstance(text, str) or re.fullmatch('[a-z][a-z0-9._/-]{0,95}', text) is None:
            raise ValueError('bounded canonical public labels required')
    return dict(value)


def _header(context, pad_to):
    if type(pad_to) is not int or pad_to not in PADDING_BUCKETS:
        raise ValueError('fixed permitted padding bucket required')
    return {'schema': SCHEMA, 'version': 1, 'suite': SUITE, 'pad_to': pad_to, 'context': _context(context)}


def _info(header, public_key):
    # The public-key hash binds the recipient but is not transmitted.
    # HPKE's documented info input carries single-shot application metadata.
    return (
        b'Titan-PQ-envelope-v1\x00'
        + _canonical(header)
        + b'\x00recipient-key\x00'
        + hashlib.sha256(public_key).digest()
    )


def generate_recipient_keypair() -> tuple[bytes, bytes]:
    """Return (public bytes, secret64-byte seed); caller owns secure key custody."""
    _, private_type, _ = _backend()
    try:
        key = private_type.generate()
        return (key.public_key().public_bytes_raw(), key.private_bytes_raw())
    except Exception:
        raise TitanDependencyUnavailable('pinned Titan HPKE backend unavailable') from None


def encrypt(
    payload: bytes,
    public_key: bytes,
    public_context: dict,
    *,
    pad_to: int = DEFAULT_PAD_TO,
) -> bytes:
    """Seal opaque bytes in one operator-selected fixed-size padding bucket.

    Oversized input is rejected, never automatically moved to a larger bucket.
    Key generation, randomness and HPKE encryption come from the maintained
    library; os.urandom supplies only non-semantic padding bytes.
    """
    header = _header(public_context, pad_to)
    if type(payload) is not bytes or len(payload) > pad_to - 8:
        raise ValueError('payload exceeds selected padding bucket')
    if type(public_key) is not bytes or len(public_key) != 1184:
        raise ValueError('ML-KEM-768 public key bytes required')
    suite, _, public_type = _backend()
    recipient = public_type.from_public_bytes(public_key)
    padded = len(payload).to_bytes(8, 'big') + payload + os.urandom(pad_to - 8 - len(payload))
    ciphertext = suite.encrypt(padded, recipient, info=_info(header, public_key))
    if len(ciphertext) != pad_to + _ENC_BYTES + _TAG_BYTES:
        raise RuntimeError('unexpected maintained HPKE output length')
    result = _canonical({'header': header, 'ciphertext_b64': base64.b64encode(ciphertext).decode('ascii')})
    if len(result) > MAX_ENVELOPE_BYTES:
        raise RuntimeError('envelope ceiling exceeded')
    return result


def decrypt(envelope: bytes, private_seed: bytes, expected_context: dict) -> bytes:
    """Open only the fixed profile; all malformed/key/context/tag errors are generic.

    Dependency errors are configuration failures and are reported separately.
    No plaintext, including its internal length, is released before HPKE accepts.
    """
    suite, private_type, _ = _backend()
    try:
        if type(envelope) is not bytes or not 1 <= len(envelope) <= MAX_ENVELOPE_BYTES:
            raise ValueError('invalid envelope')
        if type(private_seed) is not bytes or len(private_seed) != 64:
            raise ValueError('invalid key')

        def pairs(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise ValueError('duplicate field')
                value[key] = item
            return value
        value = json.loads(envelope, object_pairs_hook=pairs)
        if (
            type(value) is not dict
            or set(value) != {'header', 'ciphertext_b64'}
            or _canonical(value) != envelope
        ):
            raise ValueError('invalid envelope encoding')
        header = value['header']
        if type(header) is not dict or set(header) != {'schema', 'version', 'suite', 'pad_to', 'context'}:
            raise ValueError('invalid header')
        if type(header['version']) is not int or header['version'] != 1:
            raise ValueError('unsupported version')
        expected_header = _header(expected_context, header['pad_to'])
        if _canonical(header) != _canonical(expected_header):
            raise ValueError('unexpected profile or context')
        encoded = value['ciphertext_b64']
        size = header['pad_to'] + _ENC_BYTES + _TAG_BYTES
        if type(encoded) is not str or len(encoded) != 4 * ((size + 2) // 3):
            raise ValueError('invalid ciphertext size')
        ciphertext = base64.b64decode(encoded, validate=True)
        if len(ciphertext) != size or base64.b64encode(ciphertext).decode('ascii') != encoded:
            raise ValueError('invalid ciphertext encoding')
        recipient = private_type.from_seed_bytes(private_seed)
        public = recipient.public_key().public_bytes_raw()
        padded = suite.decrypt(ciphertext, recipient, info=_info(header, public))
        if len(padded) != header['pad_to']:
            raise ValueError('invalid padded plaintext')
        length = int.from_bytes(padded[:8], 'big')
        if length > len(padded) - 8:
            raise ValueError('invalid authenticated internal length')
        return padded[8:8 + length]
    except Exception:
        raise TitanDecryptionError('decryption failed') from None
__all__ = [
    'generate_recipient_keypair',
    'encrypt',
    'decrypt',
    'backend_status',
    'TitanDependencyUnavailable',
    'TitanDecryptionError',
    'PADDING_BUCKETS',
    'DEFAULT_PAD_TO',
    'MAX_PAYLOAD_BYTES',
    'MAX_ENVELOPE_BYTES',
]
