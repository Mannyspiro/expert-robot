"""Verified, portable backup packages for the canonical MerlinRegistry.

This creates and verifies a local recovery package. It does not encrypt, upload,
or qualify an off-host backup; those require separately managed key custody and
transport credentials.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tempfile
import time
from typing import Any
import zipfile

from .qualification_evidence_dag import SnapshotHistory


BACKUP_SCHEMA = "merlin-registry-backup/1"
DATABASE_ENTRY = "merlin.sqlite3"
MANIFEST_ENTRY = "manifest.json"
BLOB_PREFIX = "blobs/sha256"


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def _validate_archive_name(name: str) -> str:
    if (not isinstance(name, str) or not name or name.startswith("/")
            or "\\" in name or "\x00" in name):
        raise ValueError("backup archive contains an unsafe path")
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("backup archive contains a traversal path")
    return name


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("backup manifest contains duplicate JSON keys")
        result[key] = value
    return result


class MerlinRegistryBackup:
    """Build, verify and restore full registry + referenced blob packages."""

    def __init__(self, registry_root: str | Path):
        self.root = Path(registry_root).resolve()
        self.db_path = self.root / "merlin.sqlite3"
        if not self.db_path.is_file() or self.db_path.is_symlink():
            raise FileNotFoundError("an existing canonical MerlinRegistry is required")

    def backup_to(self, destination: str | Path) -> dict[str, Any]:
        """Create a non-overwriting ZIP containing a consistent DB and all referenced blobs."""
        target = Path(destination)
        if not target.parent.is_dir():
            raise FileNotFoundError("backup destination directory must already exist")
        if target.exists() or target.is_symlink():
            raise FileExistsError("backup destination already exists")
        with tempfile.TemporaryDirectory(prefix=".merlin-backup-", dir=target.parent) as temp:
            stage = Path(temp)
            database_copy = stage / DATABASE_ENTRY
            with sqlite3.connect(str(self.db_path), timeout=30) as source:
                with sqlite3.connect(str(database_copy)) as copied:
                    source.backup(copied)
            SnapshotHistory.verify_backup(database_copy)

            with sqlite3.connect(str(database_copy)) as db:
                db.row_factory = sqlite3.Row
                integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise RuntimeError("registry backup failed SQLite integrity_check")
                rows = db.execute(
                    "SELECT digest,size_bytes,relative_path FROM artifacts ORDER BY digest"
                ).fetchall()

            blobs = []
            for row in rows:
                digest = row["digest"]
                size_bytes = row["size_bytes"]
                relative_path = row["relative_path"]
                expected_path = f"{BLOB_PREFIX}/{digest[:2]}/{digest[2:]}"
                if (not isinstance(digest, str) or len(digest) != 64
                        or any(ch not in "0123456789abcdef" for ch in digest)
                        or relative_path != expected_path
                        or isinstance(size_bytes, bool) or not isinstance(size_bytes, int)
                        or size_bytes < 0):
                    raise RuntimeError("registry artifact metadata is malformed")
                source_blob = self.root / relative_path
                try:
                    metadata = source_blob.lstat()
                except OSError as exc:
                    raise RuntimeError(f"referenced artifact blob is unavailable: {digest}") from exc
                if not stat.S_ISREG(metadata.st_mode):
                    raise RuntimeError(f"referenced artifact blob is not a regular file: {digest}")
                actual_digest, actual_size = _sha256_file(source_blob)
                if actual_digest != digest or actual_size != size_bytes:
                    raise RuntimeError(f"referenced artifact blob failed integrity check: {digest}")
                blobs.append({
                    "sha256": digest,
                    "size_bytes": size_bytes,
                    "path": expected_path,
                })

            database_sha256, database_size = _sha256_file(database_copy)
            manifest = {
                "schema": BACKUP_SCHEMA,
                "created_at_unix": int(time.time()),
                "database": {
                    "path": DATABASE_ENTRY,
                    "sha256": database_sha256,
                    "size_bytes": database_size,
                },
                "blob_count": len(blobs),
                "blobs": blobs,
            }
            manifest_bytes = _canonical_json(manifest)
            temporary_archive = stage / "package.zip"
            with zipfile.ZipFile(
                temporary_archive, "w", compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as archive:
                archive.writestr(MANIFEST_ENTRY, manifest_bytes)
                archive.write(database_copy, DATABASE_ENTRY)
                for blob in blobs:
                    source_blob = self.root / blob["path"]
                    archive.write(source_blob, blob["path"])

            archive_sha256, archive_size = _sha256_file(temporary_archive)
            # A hard link provides atomic no-overwrite publication on the same filesystem.
            os.link(temporary_archive, target)
            with target.open("rb") as published:
                os.fsync(published.fileno())
            parent_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            return {
                "path": str(target),
                "archive_sha256": archive_sha256,
                "size_bytes": archive_size,
                "database_sha256": database_sha256,
                "blob_count": len(blobs),
            }

    @staticmethod
    def verify_archive(archive_path: str | Path) -> dict[str, Any]:
        """Verify archive paths, canonical manifest, DB schema, snapshots and every blob."""
        path = Path(archive_path)
        if not path.is_file() or path.is_symlink():
            raise ValueError("backup package must be a regular, non-symlink file")
        archive_sha256, archive_size = _sha256_file(path)
        if not zipfile.is_zipfile(path):
            raise ValueError("backup package is not a ZIP archive")

        with tempfile.TemporaryDirectory(prefix="merlin-backup-verify-") as temp:
            database_copy = Path(temp) / DATABASE_ENTRY
            with zipfile.ZipFile(path, "r") as archive:
                infos = archive.infolist()
                names = [_validate_archive_name(item.filename) for item in infos]
                if len(names) != len(set(names)):
                    raise ValueError("backup archive contains duplicate paths")
                for info in infos:
                    mode = info.external_attr >> 16
                    if stat.S_ISLNK(mode):
                        raise ValueError("backup archive must not contain symlinks")
                if MANIFEST_ENTRY not in names or DATABASE_ENTRY not in names:
                    raise ValueError("backup package is missing its manifest or database")
                manifest_bytes = archive.read(MANIFEST_ENTRY)
                try:
                    manifest = json.loads(
                        manifest_bytes.decode("utf-8"),
                        object_pairs_hook=_reject_duplicate_keys,
                    )
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError("backup manifest is malformed JSON") from exc
                if _canonical_json(manifest) != manifest_bytes:
                    raise ValueError("backup manifest is not canonical JSON")
                if not isinstance(manifest, dict) or set(manifest) != {
                    "schema", "created_at_unix", "database", "blob_count", "blobs",
                }:
                    raise ValueError("backup manifest has missing or unexpected fields")
                if manifest["schema"] != BACKUP_SCHEMA:
                    raise ValueError("unsupported backup manifest schema")
                if (isinstance(manifest["created_at_unix"], bool)
                        or not isinstance(manifest["created_at_unix"], int)
                        or manifest["created_at_unix"] < 1):
                    raise ValueError("backup manifest timestamp is invalid")
                database = manifest["database"]
                if not isinstance(database, dict) or set(database) != {
                    "path", "sha256", "size_bytes",
                } or database["path"] != DATABASE_ENTRY:
                    raise ValueError("backup database manifest is invalid")
                if (not isinstance(database["sha256"], str)
                        or len(database["sha256"]) != 64
                        or any(ch not in "0123456789abcdef" for ch in database["sha256"])
                        or isinstance(database["size_bytes"], bool)
                        or not isinstance(database["size_bytes"], int)
                        or database["size_bytes"] < 1):
                    raise ValueError("backup database digest or size is invalid")
                blobs = manifest["blobs"]
                if (not isinstance(blobs, list)
                        or isinstance(manifest["blob_count"], bool)
                        or manifest["blob_count"] != len(blobs)):
                    raise ValueError("backup blob manifest count is invalid")
                expected_names = {MANIFEST_ENTRY, DATABASE_ENTRY}
                previous_digest = ""
                for blob in blobs:
                    if not isinstance(blob, dict) or set(blob) != {
                        "sha256", "size_bytes", "path",
                    }:
                        raise ValueError("backup blob manifest entry is invalid")
                    digest = blob["sha256"]
                    if (not isinstance(digest, str) or len(digest) != 64
                            or any(ch not in "0123456789abcdef" for ch in digest)
                            or digest <= previous_digest):
                        raise ValueError("backup blob digests must be unique and sorted")
                    previous_digest = digest
                    expected_blob_path = f"{BLOB_PREFIX}/{digest[:2]}/{digest[2:]}"
                    if blob["path"] != expected_blob_path:
                        raise ValueError("backup blob path does not match its content digest")
                    if (isinstance(blob["size_bytes"], bool)
                            or not isinstance(blob["size_bytes"], int)
                            or blob["size_bytes"] < 0):
                        raise ValueError("backup blob size is invalid")
                    expected_names.add(expected_blob_path)
                if set(names) != expected_names:
                    raise ValueError("backup archive entries do not match the manifest")

                with archive.open(DATABASE_ENTRY, "r") as source, database_copy.open("xb") as target:
                    shutil.copyfileobj(source, target)
                database_sha256, database_size = _sha256_file(database_copy)
                if (database_sha256 != database["sha256"]
                        or database_size != database["size_bytes"]):
                    raise ValueError("backup database digest or size mismatch")

                for blob in blobs:
                    digest = hashlib.sha256()
                    size = 0
                    with archive.open(blob["path"], "r") as stream:
                        while True:
                            chunk = stream.read(1024 * 1024)
                            if not chunk:
                                break
                            digest.update(chunk)
                            size += len(chunk)
                    if digest.hexdigest() != blob["sha256"] or size != blob["size_bytes"]:
                        raise ValueError(f"backup artifact blob failed integrity check: {blob['sha256']}")

            SnapshotHistory.verify_backup(database_copy)
            with sqlite3.connect(str(database_copy)) as db:
                db.row_factory = sqlite3.Row
                if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("backup database failed SQLite integrity_check")
                if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise ValueError("backup database contains foreign-key violations")
                rows = db.execute(
                    "SELECT digest,size_bytes,relative_path FROM artifacts ORDER BY digest"
                ).fetchall()
                db_blobs = [{
                    "sha256": row["digest"],
                    "size_bytes": row["size_bytes"],
                    "path": row["relative_path"],
                } for row in rows]
                if db_blobs != manifest["blobs"]:
                    raise ValueError("backup manifest does not match registry artifact references")
                if "artifact_version_provenance" in {
                    row[0] for row in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }:
                    for provenance in db.execute(
                        "SELECT provenance_json,provenance_sha256 FROM artifact_version_provenance"
                    ):
                        raw = provenance["provenance_json"]
                        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != provenance["provenance_sha256"]:
                            raise ValueError("backup artifact provenance digest mismatch")
                        json.loads(raw)
                snapshot_count = db.execute(
                    "SELECT COUNT(*) FROM qualification_evidence_snapshots"
                ).fetchone()[0]
        return {
            "verified": True,
            "archive_sha256": archive_sha256,
            "size_bytes": archive_size,
            "database_sha256": database_sha256,
            "blob_count": len(manifest["blobs"]),
            "snapshot_count": snapshot_count,
        }

    @staticmethod
    def restore_to(archive_path: str | Path, destination_root: str | Path) -> dict[str, Any]:
        """Verify then restore a package into a new, non-overwriting registry root."""
        archive_path = Path(archive_path)
        target = Path(destination_root)
        if not target.parent.is_dir():
            raise FileNotFoundError("restore parent directory must already exist")
        if target.exists() or target.is_symlink():
            raise FileExistsError("restore destination already exists")
        verified = MerlinRegistryBackup.verify_archive(archive_path)
        with tempfile.TemporaryDirectory(prefix=".merlin-restore-", dir=target.parent) as temp:
            stage = Path(temp) / "registry"
            stage.mkdir()
            with zipfile.ZipFile(archive_path, "r") as archive:
                for info in archive.infolist():
                    name = _validate_archive_name(info.filename)
                    if name == MANIFEST_ENTRY:
                        continue
                    output = stage.joinpath(*PurePosixPath(name).parts)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info, "r") as source, output.open("xb") as dest:
                        shutil.copyfileobj(source, dest)
            SnapshotHistory.verify_backup(stage / DATABASE_ENTRY)
            # Verify restored blob paths against the registry metadata before publication.
            with sqlite3.connect(str(stage / DATABASE_ENTRY)) as db:
                rows = db.execute(
                    "SELECT digest,size_bytes,relative_path FROM artifacts ORDER BY digest"
                ).fetchall()
            for digest, size_bytes, relative_path in rows:
                blob = stage / relative_path
                actual_digest, actual_size = _sha256_file(blob)
                if actual_digest != digest or actual_size != size_bytes:
                    raise ValueError("restored registry blob failed integrity verification")
            if target.exists() or target.is_symlink():
                raise FileExistsError("restore destination appeared during operation")
            os.rename(stage, target)
        return {**verified, "restored_root": str(target)}
