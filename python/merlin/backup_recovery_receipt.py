"""Canonical, non-authoritative receipt for a complete Merlin backup recovery drill.

The receipt binds the exact backup/envelope/object, KMS key identity, source
revision, restore host, elapsed time, and independently checked restore results.
It is deliberately unsigned: CACE must attest the exact receipt bytes separately.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


SCHEMA = "merlin-backup-recovery-receipt/1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_CHECKS = (
    "archive_verified",
    "envelope_authenticated",
    "database_integrity",
    "foreign_keys",
    "blob_inventory",
    "artifact_refs",
    "dag_history",
    "outbox_pointers",
    "separate_host",
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _require_sha256(value: Any, field: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be lowercase SHA-256")


def _require_text(value: Any, field: str, *, prefix: str | None = None) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field} must be non-empty canonical text")
    if prefix is not None and not value.startswith(prefix):
        raise ValueError(f"{field} has an invalid identity prefix")


def _require_uint(value: Any, field: str, *, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")


def _validate_payload(payload: Mapping[str, Any]) -> None:
    expected = {
        "schema", "source", "backup", "encrypted_envelope",
        "object_storage", "kms", "restore", "checks", "counts",
    }
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise ValueError("backup recovery receipt has an invalid field set")
    if payload["schema"] != SCHEMA:
        raise ValueError("unsupported backup recovery receipt schema")

    source = payload["source"]
    if not isinstance(source, Mapping) or set(source) != {"repository", "commit"}:
        raise ValueError("source identity is malformed")
    _require_text(source["repository"], "source.repository")
    if not isinstance(source["commit"], str) or not COMMIT_RE.fullmatch(source["commit"]):
        raise ValueError("source.commit must be a full Git commit SHA")

    backup = payload["backup"]
    if not isinstance(backup, Mapping) or set(backup) != {
        "package_sha256", "manifest_sha256", "restored_manifest_sha256",
    }:
        raise ValueError("backup identity is malformed")
    for field in ("package_sha256", "manifest_sha256", "restored_manifest_sha256"):
        _require_sha256(backup[field], f"backup.{field}")
    if backup["manifest_sha256"] != backup["restored_manifest_sha256"]:
        raise ValueError("restored registry manifest does not match the source backup manifest")

    envelope = payload["encrypted_envelope"]
    if not isinstance(envelope, Mapping) or set(envelope) != {"sha256", "size_bytes"}:
        raise ValueError("encrypted envelope identity is malformed")
    _require_sha256(envelope["sha256"], "encrypted_envelope.sha256")
    _require_uint(envelope["size_bytes"], "encrypted_envelope.size_bytes", minimum=1)

    storage = payload["object_storage"]
    if not isinstance(storage, Mapping) or set(storage) != {
        "namespace", "bucket", "object_name", "version_id", "etag",
    }:
        raise ValueError("Object Storage identity is malformed")
    for field in ("namespace", "bucket", "object_name", "etag"):
        _require_text(storage[field], f"object_storage.{field}")
    expected_suffix = f"sha256/{envelope['sha256'][:2]}/{envelope['sha256']}.mrb.enc"
    if not storage["object_name"].endswith(expected_suffix):
        raise ValueError("Object Storage object name is not bound to the envelope digest")
    if storage["version_id"] is not None:
        _require_text(storage["version_id"], "object_storage.version_id")

    kms = payload["kms"]
    if not isinstance(kms, Mapping) or set(kms) != {"key_ocid", "key_version_id"}:
        raise ValueError("KMS identity is malformed")
    _require_text(kms["key_ocid"], "kms.key_ocid", prefix="ocid1.key.")
    _require_text(kms["key_version_id"], "kms.key_version_id")

    restore = payload["restore"]
    if not isinstance(restore, Mapping) or set(restore) != {
        "host_identity_sha256", "runner_profile", "started_at_unix_ms",
        "completed_at_unix_ms", "duration_ms",
    }:
        raise ValueError("restore execution identity is malformed")
    _require_sha256(restore["host_identity_sha256"], "restore.host_identity_sha256")
    _require_text(restore["runner_profile"], "restore.runner_profile")
    for field in ("started_at_unix_ms", "completed_at_unix_ms", "duration_ms"):
        _require_uint(restore[field], f"restore.{field}")
    if restore["completed_at_unix_ms"] < restore["started_at_unix_ms"]:
        raise ValueError("restore completion precedes start")
    if restore["duration_ms"] != restore["completed_at_unix_ms"] - restore["started_at_unix_ms"]:
        raise ValueError("restore duration does not match timestamps")

    checks = payload["checks"]
    if not isinstance(checks, Mapping) or set(checks) != set(REQUIRED_CHECKS):
        raise ValueError("restore checks have an invalid field set")
    if any(value is not True for value in checks.values()):
        raise ValueError("recovery receipt cannot qualify with a failed or missing check")

    counts = payload["counts"]
    if not isinstance(counts, Mapping) or set(counts) != {
        "blob_count", "artifact_ref_count", "snapshot_count", "outbox_event_count",
    }:
        raise ValueError("restored inventory counts are malformed")
    for field, value in counts.items():
        _require_uint(value, f"counts.{field}")


def build_backup_recovery_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and digest a complete restore result; does not sign or qualify it."""
    _validate_payload(payload)
    body = dict(payload)
    return {
        **body,
        "receipt_sha256": hashlib.sha256(canonical_json(body)).hexdigest(),
    }


def verify_backup_recovery_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Verify canonical receipt bytes and internal cross-field bindings."""
    if not isinstance(receipt, Mapping) or "receipt_sha256" not in receipt:
        raise ValueError("backup recovery receipt digest is required")
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    _validate_payload(body)
    expected = hashlib.sha256(canonical_json(body)).hexdigest()
    if receipt["receipt_sha256"] != expected:
        raise ValueError("backup recovery receipt digest mismatch")
    return {
        "verified": True,
        "schema": SCHEMA,
        "receipt_sha256": expected,
        "authority": "integrity-only",
        "cace_attestation_required": True,
    }
