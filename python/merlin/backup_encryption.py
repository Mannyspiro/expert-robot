"""Chunked authenticated encryption for MerlinRegistry backup packages.

The key provider is injected. Production use requires an independently provisioned
KMS/Vault implementation; this module contains no local key store or fallback key.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import struct
import tempfile
from typing import Any, Protocol
import zipfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .registry_backup import MerlinRegistryBackup


MAGIC = b"MERLIN-REGISTRY-ENCRYPTED-BACKUP/1\n"
ENVELOPE_SCHEMA = "merlin-encrypted-registry-backup/1"
ALGORITHM = "AES-256-GCM-CHUNKED"
DEFAULT_CHUNK_SIZE = 1024 * 1024
MIN_CHUNK_SIZE = 64 * 1024
MAX_CHUNK_SIZE = 8 * 1024 * 1024
MAX_HEADER_SIZE = 1024 * 1024


class BackupKeyProvider(Protocol):
    """KMS adapter contract; plaintext data keys exist only in process memory."""

    def generate_data_key(self) -> tuple[str, bytes, bytes]:
        """Return (KMS key ID, 32-byte plaintext DEK, wrapped DEK ciphertext)."""

    def unwrap_data_key(self, key_id: str, wrapped_key: bytes) -> bytes:
        """Return the 32-byte plaintext DEK for this exact KMS key/version."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("encrypted backup header contains duplicate JSON keys")
        result[key] = value
    return result


def _read_exact(stream, length: int) -> bytes:
    chunks = []
    remaining = length
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise ValueError("encrypted backup envelope is truncated")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _open_regular_nofollow(path: Path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        raise ValueError("encrypted backup input must be a regular file")
    return os.fdopen(descriptor, "rb")


def _publish_no_overwrite(temporary_path: Path, destination: Path) -> None:
    if not destination.parent.is_dir():
        raise FileNotFoundError("encrypted backup destination directory must exist")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("encrypted backup destination already exists")
    os.link(temporary_path, destination)
    with destination.open("rb+") as published:
        os.fsync(published.fileno())
    parent_fd = os.open(destination.parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


class MerlinBackupEncryption:
    """Encrypt verified backup ZIPs with a KMS-wrapped data key and chunked AES-GCM."""

    @staticmethod
    def encrypt(
        backup_path: str | Path,
        destination: str | Path,
        key_provider: BackupKeyProvider,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> dict[str, Any]:
        source = Path(backup_path)
        target = Path(destination)
        if (isinstance(chunk_size, bool) or not isinstance(chunk_size, int)
                or not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE):
            raise ValueError("chunk_size must be between 64 KiB and 8 MiB")
        if not target.parent.is_dir():
            raise FileNotFoundError("encrypted backup destination directory must exist")
        if target.exists() or target.is_symlink():
            raise FileExistsError("encrypted backup destination already exists")
        backup_receipt = MerlinRegistryBackup.verify_archive(source)

        key_id, plaintext_key, wrapped_key = key_provider.generate_data_key()
        if (not isinstance(key_id, str) or not key_id.strip() or len(key_id) > 1024
                or not isinstance(plaintext_key, bytes) or len(plaintext_key) != 32
                or not isinstance(wrapped_key, bytes) or not wrapped_key
                or len(wrapped_key) > 64 * 1024):
            raise ValueError("KMS provider returned an invalid data-key envelope")

        nonce_prefix = secrets.token_bytes(8)
        chunk_count = (backup_receipt["size_bytes"] + chunk_size - 1) // chunk_size
        header = {
            "schema": ENVELOPE_SCHEMA,
            "algorithm": ALGORITHM,
            "key_id": key_id,
            "wrapped_data_key_b64": base64.b64encode(wrapped_key).decode("ascii"),
            "nonce_prefix_b64": base64.b64encode(nonce_prefix).decode("ascii"),
            "chunk_size": chunk_size,
            "chunk_count": chunk_count,
            "plaintext_size": backup_receipt["size_bytes"],
            "plaintext_sha256": backup_receipt["archive_sha256"],
        }
        header_bytes = _canonical_json(header)
        if len(header_bytes) > MAX_HEADER_SIZE:
            raise ValueError("encrypted backup header exceeds the safety limit")
        aad_prefix = MAGIC + struct.pack(">I", len(header_bytes)) + header_bytes
        cipher = AESGCM(plaintext_key)
        plaintext_digest = hashlib.sha256()
        plaintext_size = 0

        with tempfile.NamedTemporaryFile(
            prefix=".merlin-encrypted-backup-", suffix=".tmp",
            dir=target.parent, delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            try:
                temporary.write(aad_prefix)
                with _open_regular_nofollow(source) as input_stream:
                    for index in range(chunk_count):
                        chunk = input_stream.read(chunk_size)
                        if not chunk:
                            raise RuntimeError("backup source truncated during encryption")
                        plaintext_digest.update(chunk)
                        plaintext_size += len(chunk)
                        nonce = nonce_prefix + struct.pack(">I", index)
                        aad = aad_prefix + struct.pack(">I", index)
                        encrypted = cipher.encrypt(nonce, chunk, aad)
                        temporary.write(struct.pack(">I", len(encrypted)))
                        temporary.write(encrypted)
                    if input_stream.read(1):
                        raise RuntimeError("backup source grew during encryption")
                if (plaintext_size != backup_receipt["size_bytes"]
                        or plaintext_digest.hexdigest() != backup_receipt["archive_sha256"]):
                    raise RuntimeError("backup source changed during encryption")
                temporary.flush()
                os.fsync(temporary.fileno())
            except Exception:
                temporary_path.unlink(missing_ok=True)
                raise
        try:
            envelope_sha256 = hashlib.sha256()
            envelope_size = 0
            with temporary_path.open("rb") as stream:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    envelope_sha256.update(chunk)
                    envelope_size += len(chunk)
            _publish_no_overwrite(temporary_path, target)
            return {
                "path": str(target),
                "envelope_sha256": envelope_sha256.hexdigest(),
                "envelope_size_bytes": envelope_size,
                "plaintext_sha256": backup_receipt["archive_sha256"],
                "plaintext_size_bytes": backup_receipt["size_bytes"],
                "key_id": key_id,
                "chunk_count": chunk_count,
            }
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def decrypt(
        encrypted_path: str | Path,
        destination: str | Path,
        key_provider: BackupKeyProvider,
    ) -> dict[str, Any]:
        source = Path(encrypted_path)
        target = Path(destination)
        if not target.parent.is_dir():
            raise FileNotFoundError("decrypted backup destination directory must exist")
        if target.exists() or target.is_symlink():
            raise FileExistsError("decrypted backup destination already exists")

        envelope_digest = hashlib.sha256()
        envelope_size = 0
        with _open_regular_nofollow(source) as stream:
            # Hash the exact encrypted bytes in a separate no-follow pass.
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                envelope_digest.update(chunk)
                envelope_size += len(chunk)

        with tempfile.TemporaryDirectory(prefix=".merlin-decrypted-backup-", dir=target.parent) as temp:
            temporary_path = Path(temp) / "backup.zip"
            with _open_regular_nofollow(source) as stream:
                if _read_exact(stream, len(MAGIC)) != MAGIC:
                    raise ValueError("unsupported encrypted backup envelope")
                header_length = struct.unpack(">I", _read_exact(stream, 4))[0]
                if not 1 <= header_length <= MAX_HEADER_SIZE:
                    raise ValueError("encrypted backup header length is invalid")
                header_bytes = _read_exact(stream, header_length)
                try:
                    header = json.loads(
                        header_bytes.decode("utf-8"),
                        object_pairs_hook=_reject_duplicate_keys,
                    )
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError("encrypted backup header is malformed") from exc
                if _canonical_json(header) != header_bytes:
                    raise ValueError("encrypted backup header is not canonical JSON")
                expected_fields = {
                    "schema", "algorithm", "key_id", "wrapped_data_key_b64",
                    "nonce_prefix_b64", "chunk_size", "chunk_count",
                    "plaintext_size", "plaintext_sha256",
                }
                if not isinstance(header, dict) or set(header) != expected_fields:
                    raise ValueError("encrypted backup header has missing or unexpected fields")
                if header["schema"] != ENVELOPE_SCHEMA or header["algorithm"] != ALGORITHM:
                    raise ValueError("unsupported encrypted backup schema or algorithm")
                key_id = header["key_id"]
                if not isinstance(key_id, str) or not key_id.strip() or len(key_id) > 1024:
                    raise ValueError("encrypted backup KMS key ID is invalid")
                if (isinstance(header["chunk_size"], bool)
                        or not isinstance(header["chunk_size"], int)
                        or not MIN_CHUNK_SIZE <= header["chunk_size"] <= MAX_CHUNK_SIZE):
                    raise ValueError("encrypted backup chunk size is invalid")
                if (isinstance(header["plaintext_size"], bool)
                        or not isinstance(header["plaintext_size"], int)
                        or header["plaintext_size"] < 1):
                    raise ValueError("encrypted backup plaintext size is invalid")
                expected_chunks = (
                    header["plaintext_size"] + header["chunk_size"] - 1
                ) // header["chunk_size"]
                if (isinstance(header["chunk_count"], bool)
                        or not isinstance(header["chunk_count"], int)
                        or header["chunk_count"] != expected_chunks
                        or header["chunk_count"] > 0xFFFFFFFF):
                    raise ValueError("encrypted backup chunk count is invalid")
                plaintext_sha256 = header["plaintext_sha256"]
                if (not isinstance(plaintext_sha256, str) or len(plaintext_sha256) != 64
                        or any(ch not in "0123456789abcdef" for ch in plaintext_sha256)):
                    raise ValueError("encrypted backup plaintext digest is invalid")
                try:
                    wrapped_key = base64.b64decode(
                        header["wrapped_data_key_b64"], validate=True,
                    )
                    nonce_prefix = base64.b64decode(
                        header["nonce_prefix_b64"], validate=True,
                    )
                except (TypeError, ValueError) as exc:
                    raise ValueError("encrypted backup key or nonce encoding is invalid") from exc
                if not wrapped_key or len(wrapped_key) > 64 * 1024 or len(nonce_prefix) != 8:
                    raise ValueError("encrypted backup wrapped key or nonce has invalid length")
                plaintext_key = key_provider.unwrap_data_key(key_id, wrapped_key)
                if not isinstance(plaintext_key, bytes) or len(plaintext_key) != 32:
                    raise ValueError("KMS provider returned an invalid plaintext data key")
                cipher = AESGCM(plaintext_key)
                aad_prefix = MAGIC + struct.pack(">I", header_length) + header_bytes
                digest = hashlib.sha256()
                total = 0
                with temporary_path.open("xb") as output:
                    for index in range(header["chunk_count"]):
                        remaining = header["plaintext_size"] - total
                        expected_plain = min(header["chunk_size"], remaining)
                        expected_cipher = expected_plain + 16
                        frame_length = struct.unpack(">I", _read_exact(stream, 4))[0]
                        if frame_length != expected_cipher:
                            raise ValueError("encrypted backup chunk frame length is invalid")
                        ciphertext = _read_exact(stream, frame_length)
                        nonce = nonce_prefix + struct.pack(">I", index)
                        aad = aad_prefix + struct.pack(">I", index)
                        try:
                            plaintext = cipher.decrypt(nonce, ciphertext, aad)
                        except Exception as exc:
                            raise ValueError("encrypted backup chunk authentication failed") from exc
                        if len(plaintext) != expected_plain:
                            raise ValueError("encrypted backup plaintext chunk length is invalid")
                        output.write(plaintext)
                        digest.update(plaintext)
                        total += len(plaintext)
                    if stream.read(1):
                        raise ValueError("encrypted backup envelope contains trailing bytes")
                    output.flush()
                    os.fsync(output.fileno())
                if total != header["plaintext_size"] or digest.hexdigest() != plaintext_sha256:
                    raise ValueError("decrypted backup plaintext digest or size mismatch")

            backup_receipt = MerlinRegistryBackup.verify_archive(temporary_path)
            if (backup_receipt["archive_sha256"] != plaintext_sha256
                    or backup_receipt["size_bytes"] != header["plaintext_size"]):
                raise ValueError("decrypted backup package does not match authenticated header")
            _publish_no_overwrite(temporary_path, target)
        return {
            "path": str(target),
            "envelope_sha256": envelope_digest.hexdigest(),
            "envelope_size_bytes": envelope_size,
            "plaintext_sha256": plaintext_sha256,
            "plaintext_size_bytes": header["plaintext_size"],
            "key_id": header["key_id"],
            "verified_backup": True,
        }
