"""Safe, manifest-first ZIP intake for Merlin.

Archive members are read as bytes and written into the content-addressed store;
the importer never extracts member paths onto the host filesystem. Import is
bounded and reports duplicates by SHA-256. It does not infer project ownership.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import PurePosixPath
from pathlib import Path
import zipfile
from typing import Any

from .foundation_store import MerlinFoundationStore


class ArchiveIntakeError(ValueError):
    pass


def _safe_member_path(name: str) -> str:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ArchiveIntakeError(f"unsafe archive member path: {name!r}")
    if path.parts and ":" in path.parts[0]:
        raise ArchiveIntakeError(f"drive-qualified archive member path: {name!r}")
    return str(path)


def inspect_zip(path: str | Path, *, max_members: int = 20000,
                max_uncompressed_bytes: int = 2_000_000_000,
                max_member_bytes: int = 500_000_000,
                max_compression_ratio: float = 250.0) -> dict[str, Any]:
    archive_path = Path(path)
    raw = archive_path.read_bytes()
    archive_digest = hashlib.sha256(raw).hexdigest()
    members: list[dict[str, Any]] = []
    total = 0
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if len(infos) > max_members:
            raise ArchiveIntakeError("archive exceeds member-count limit")
        for info in infos:
            if info.is_dir():
                continue
            member_path = _safe_member_path(info.filename)
            if info.flag_bits & 0x1:
                raise ArchiveIntakeError(f"encrypted member is not supported: {member_path}")
            if info.file_size > max_member_bytes:
                raise ArchiveIntakeError(f"member exceeds size limit: {member_path}")
            total += info.file_size
            if total > max_uncompressed_bytes:
                raise ArchiveIntakeError("archive exceeds total uncompressed-size limit")
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > max_compression_ratio and info.file_size > 1_000_000:
                raise ArchiveIntakeError(f"member compression ratio exceeds limit: {member_path}")
            data = archive.read(info)
            if len(data) != info.file_size:
                raise ArchiveIntakeError(f"member size mismatch: {member_path}")
            members.append({
                "path": member_path,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "crc32": f"{info.CRC:08x}",
                "media_type": "application/octet-stream",
                "_content": data,
            })
    public_members = [{k:v for k,v in item.items() if k != "_content"} for item in members]
    return {
        "archive_name": archive_path.name,
        "archive_sha256": archive_digest,
        "archive_size_bytes": len(raw),
        "member_count": len(members),
        "uncompressed_size_bytes": total,
        "members": members,
        "manifest_sha256": hashlib.sha256(json.dumps(
            public_members, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(),
    }


def ingest_archives(store: MerlinFoundationStore, project_id: str,
                    archive_paths: list[str | Path], *,
                    max_members: int = 20000,
                    max_uncompressed_bytes: int = 2_000_000_000) -> dict[str, Any]:
    """Ingest supplied ZIPs into a named project; never guesses project mapping."""
    if store.registry.inventory(project_id) is None:  # pragma: no cover - inventory raises if absent
        raise KeyError(project_id)
    reports = []
    digest_locations: dict[str, list[str]] = defaultdict(list)
    for archive_path in archive_paths:
        inspected = inspect_zip(archive_path, max_members=max_members,
                                max_uncompressed_bytes=max_uncompressed_bytes)
        archive_digest = inspected["archive_sha256"]
        archive_bytes = Path(archive_path).read_bytes()
        store.put_artifact(project_id, f"intake/archives/{archive_digest}.zip",
                           archive_bytes, "application/zip", metadata={
                               "original_filename": inspected["archive_name"],
                               "archive_sha256": archive_digest,
                           })
        stored_members = []
        for member in inspected["members"]:
            logical_path = f"intake/members/{archive_digest}/{member['path']}"
            digest = store.put_artifact(
                project_id, logical_path, member["_content"], member["media_type"],
                artifact_type="source",
                metadata={"source_archive_sha256": archive_digest,
                          "original_member_path": member["path"],
                          "crc32": member["crc32"]},
            )
            digest_locations[digest].append(logical_path)
            stored_members.append({k:v for k,v in member.items() if k != "_content"})
        reports.append({
            "archive_name": inspected["archive_name"],
            "archive_sha256": archive_digest,
            "archive_size_bytes": inspected["archive_size_bytes"],
            "member_count": inspected["member_count"],
            "uncompressed_size_bytes": inspected["uncompressed_size_bytes"],
            "manifest_sha256": inspected["manifest_sha256"],
            "members": stored_members,
        })
    duplicates = {digest: paths for digest, paths in digest_locations.items() if len(paths) > 1}
    result = {
        "schema_version": "1.0",
        "project_id": project_id,
        "archive_count": len(reports),
        "total_member_count": sum(r["member_count"] for r in reports),
        "archives": reports,
        "duplicate_content": duplicates,
        "registry_reconciliation": store.reconcile_project(project_id),
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    result["intake_receipt_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return result
