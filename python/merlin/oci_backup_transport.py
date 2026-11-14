"""Create-only OCI Object Storage transport for encrypted Merlin backups.

The adapter never creates/deletes buckets or objects and never manages retention.
Bucket retention, versioning, privacy and IAM are provisioned separately.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import tempfile
from typing import Any, Mapping

from .backup_encryption import MAGIC, ENVELOPE_SCHEMA


OBJECT_CONTENT_TYPE = "application/vnd.merlin.encrypted-registry-backup"
OBJECT_METADATA_SCHEMA = "merlin-object-backup-metadata/1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ObjectStorageConflict(RuntimeError):
    pass


def _headers(response: Any) -> dict[str, str]:
    raw = getattr(response, "headers", None) or {}
    return {str(key).lower(): str(value) for key, value in raw.items()}


def _hash_regular_file(path: Path) -> tuple[str, int, bytes]:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    digest = hashlib.sha256()
    size = 0
    prefix = b""
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("encrypted backup must be a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            prefix = stream.read(len(MAGIC))
            digest.update(prefix)
            size += len(prefix)
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest(), size, prefix


def _publish_no_overwrite(temporary_path: Path, destination: Path) -> None:
    if not destination.parent.is_dir():
        raise FileNotFoundError("download destination directory must exist")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("download destination already exists")
    os.link(temporary_path, destination)
    with destination.open("rb+") as published:
        os.fsync(published.fileno())
    parent_fd = os.open(destination.parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


class OciObjectStorageBackupTransport:
    """Upload/download encrypted backups with content-addressed create-only names."""

    def __init__(
        self,
        namespace: str,
        bucket: str,
        *,
        prefix: str = "merlin/backups",
        read_client: Any,
        upload_manager: Any,
    ):
        if not isinstance(namespace, str) or not namespace.strip() or len(namespace) > 256:
            raise ValueError("OCI Object Storage namespace is invalid")
        if not isinstance(bucket, str) or not bucket.strip() or len(bucket) > 256:
            raise ValueError("OCI Object Storage bucket name is invalid")
        if not isinstance(prefix, str) or prefix.startswith("/") or "\\" in prefix:
            raise ValueError("backup object prefix is invalid")
        prefix_parts = prefix.split("/") if prefix else []
        if any(part in {"", ".", ".."} for part in prefix_parts):
            raise ValueError("backup object prefix contains an unsafe path")
        self.namespace = namespace
        self.bucket = bucket
        self.prefix = prefix
        self.read_client = read_client
        self.upload_manager = upload_manager

    @classmethod
    def from_instance_principal(
        cls, namespace: str, bucket: str, *, prefix: str = "merlin/backups",
    ):
        import oci
        read_signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        write_signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        read_client = oci.object_storage.ObjectStorageClient(config={}, signer=read_signer)
        # UploadManager mutates timeout settings on its client; keep it isolated.
        write_client = oci.object_storage.ObjectStorageClient(config={}, signer=write_signer)
        upload_manager = oci.object_storage.UploadManager(
            write_client, allow_parallel_uploads=False,
        )
        return cls(
            namespace, bucket, prefix=prefix,
            read_client=read_client, upload_manager=upload_manager,
        )

    @classmethod
    def from_environment(cls):
        namespace = os.getenv("MERLIN_BACKUP_OCI_NAMESPACE", "").strip()
        bucket = os.getenv("MERLIN_BACKUP_OCI_BUCKET", "").strip()
        prefix = os.getenv("MERLIN_BACKUP_OCI_PREFIX", "merlin/backups").strip()
        if not namespace or not bucket:
            raise RuntimeError("Merlin backup OCI Object Storage namespace/bucket are unconfigured")
        return cls.from_instance_principal(namespace, bucket, prefix=prefix)

    def object_name_for_digest(self, digest: str) -> str:
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ValueError("encrypted backup SHA-256 must be lowercase hexadecimal")
        suffix = f"sha256/{digest[:2]}/{digest}.mrb.enc"
        return f"{self.prefix}/{suffix}" if self.prefix else suffix

    def _head_verified(
        self, object_name: str, digest: str, size: int | None = None,
        version_id: str | None = None,
    ):
        kwargs = {"version_id": version_id} if version_id else {}
        response = self.read_client.head_object(
            self.namespace, self.bucket, object_name, **kwargs,
        )
        headers = _headers(response)
        expected_metadata = {
            "opc-meta-merlin-sha256": digest,
            "opc-meta-merlin-envelope-schema": ENVELOPE_SCHEMA,
            "opc-meta-merlin-metadata-schema": OBJECT_METADATA_SCHEMA,
        }
        for name, expected in expected_metadata.items():
            if headers.get(name) != expected:
                raise ObjectStorageConflict(f"Object Storage metadata mismatch: {name}")
        content_length = headers.get("content-length")
        if (content_length is None or not content_length.isdigit()
                or headers.get("opc-meta-merlin-size-bytes") != content_length):
            raise ObjectStorageConflict("Object Storage content length metadata mismatch")
        actual_size = int(content_length)
        if size is not None and actual_size != size:
            raise ObjectStorageConflict("Object Storage content length mismatch")
        return {
            "etag": headers.get("etag"),
            "version_id": headers.get("opc-version-id"),
            "content_length": actual_size,
        }

    @staticmethod
    def _status_from_exception(exc: Exception):
        status = getattr(exc, "status", None)
        if status is None:
            status = getattr(getattr(exc, "service_error", None), "status", None)
        return status

    def upload_encrypted_backup(
        self, encrypted_path: str | Path, *,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        path = Path(encrypted_path)
        digest, size, prefix = _hash_regular_file(path)
        if prefix != MAGIC:
            raise ValueError("Object Storage transport accepts only Merlin encrypted backup envelopes")
        if expected_sha256 is not None and expected_sha256 != digest:
            raise ValueError("encrypted backup digest does not match caller's expected SHA-256")
        object_name = self.object_name_for_digest(digest)
        metadata = {
            "merlin-sha256": digest,
            "merlin-size-bytes": str(size),
            "merlin-envelope-schema": ENVELOPE_SCHEMA,
            "merlin-metadata-schema": OBJECT_METADATA_SCHEMA,
        }
        replayed = False
        try:
            self.upload_manager.upload_file(
                self.namespace,
                self.bucket,
                object_name,
                str(path),
                if_none_match="*",
                content_type=OBJECT_CONTENT_TYPE,
                metadata=metadata,
                opc_checksum_algorithm="SHA256",
            )
        except Exception as exc:
            if self._status_from_exception(exc) != 412:
                raise
            # A timed-out create may already have committed; accept only an exact match.
            replayed = True
        head = self._head_verified(object_name, digest, size)
        return {
            "namespace": self.namespace,
            "bucket": self.bucket,
            "object_name": object_name,
            "sha256": digest,
            "size_bytes": size,
            "etag": head["etag"],
            "version_id": head["version_id"],
            "replayed": replayed,
        }

    def download_encrypted_backup(
        self,
        object_name: str,
        destination: str | Path,
        *,
        expected_sha256: str,
        expected_size: int | None = None,
        version_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(expected_sha256, str) or not SHA256_RE.fullmatch(expected_sha256):
            raise ValueError("expected backup SHA-256 must be lowercase hexadecimal")
        expected_name = self.object_name_for_digest(expected_sha256)
        if object_name != expected_name:
            raise ValueError("Object Storage name does not match the expected content digest")
        target = Path(destination)
        if not target.parent.is_dir():
            raise FileNotFoundError("download destination directory must exist")
        if target.exists() or target.is_symlink():
            raise FileExistsError("download destination already exists")

        head = self._head_verified(
            object_name, expected_sha256, expected_size, version_id,
        )
        etag = head["etag"]
        get_kwargs = {}
        if etag:
            get_kwargs["if_match"] = etag
        if version_id:
            get_kwargs["version_id"] = version_id
        response = self.read_client.get_object(
            self.namespace, self.bucket, object_name, **get_kwargs,
        )
        raw = getattr(getattr(response, "data", None), "raw", None)
        if raw is None or not hasattr(raw, "stream"):
            raise RuntimeError("OCI Object Storage response did not provide a streaming body")

        with tempfile.NamedTemporaryFile(
            prefix=".merlin-object-download-", suffix=".tmp",
            dir=target.parent, delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            digest = hashlib.sha256()
            size = 0
            try:
                for chunk in raw.stream(1024 * 1024, decode_content=False):
                    temporary.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                temporary.flush()
                os.fsync(temporary.fileno())
            except Exception:
                temporary_path.unlink(missing_ok=True)
                raise
        try:
            if digest.hexdigest() != expected_sha256:
                raise ValueError("downloaded encrypted backup SHA-256 mismatch")
            if size != head["content_length"]:
                raise ValueError("downloaded encrypted backup size mismatch")
            with temporary_path.open("rb") as stream:
                if stream.read(len(MAGIC)) != MAGIC:
                    raise ValueError("downloaded object is not a Merlin encrypted backup envelope")
            _publish_no_overwrite(temporary_path, target)
            return {
                "path": str(target),
                "namespace": self.namespace,
                "bucket": self.bucket,
                "object_name": object_name,
                "sha256": digest.hexdigest(),
                "size_bytes": size,
                "etag": head["etag"],
                "version_id": version_id or head["version_id"],
            }
        finally:
            temporary_path.unlink(missing_ok=True)
