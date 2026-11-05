"""Exact-byte recovery adapters. All restores target quarantine paths, never canonical paths."""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any
from uuid import uuid4


def _safe_relative(path: str) -> str:
    normalized = path.replace("\\", "/")
    value = PurePosixPath(normalized)
    if not normalized or value.is_absolute() or any(part in {"", ".", ".."} for part in value.parts):
        raise ValueError("recovery path must be relative and traversal-free")
    if ":" in value.parts[0]:
        raise ValueError("drive-qualified recovery path is forbidden")
    return str(value)


def _verify(data: bytes, expected_sha256: str) -> bytes:
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"recovered bytes do not match expected SHA-256: {actual}")
    return data


class RegistryRecoveryAdapter:
    def __init__(self, registry):
        self.registry = registry

    def recover(self, *, digest: str, project_id: str, original_path: str,
                actor: str = "recovery") -> dict[str, Any]:
        data = _verify(self.registry.get_artifact_bytes(digest), digest)
        recovery_path = f"_recovery/{uuid4().hex}/{_safe_relative(original_path)}"
        restored = self.registry.put_artifact(
            project_id, recovery_path, data, actor=actor, operation_id="registry-recovery"
        )
        _verify(self.registry.get_artifact_bytes(restored), digest)
        return {"confidence": "exact", "source": "registry", "original_path": original_path,
                "recovery_path": recovery_path, "sha256": digest, "size_bytes": len(data)}


class GitRecoveryAdapter:
    """Reads a path from a retained Git commit without checking it out or mutating the worktree."""
    def __init__(self, repository: str | Path):
        self.repository = Path(repository).resolve()
        if not (self.repository / ".git").exists():
            raise ValueError("repository must be an existing Git worktree")

    def recover(self, *, commit: str, path: str, expected_sha256: str,
                project_id: str, registry, actor: str = "recovery") -> dict[str, Any]:
        safe_path = _safe_relative(path)
        if not commit or commit.startswith("-"):
            raise ValueError("a pinned Git commit is required")
        result = subprocess.run(
            ["git", "-C", str(self.repository), "show", f"{commit}:{safe_path}"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        data = _verify(result.stdout, expected_sha256)
        recovery_path = f"_recovery/{uuid4().hex}/{safe_path}"
        digest = registry.put_artifact(
            project_id, recovery_path, data, actor=actor, operation_id=f"git-recovery:{commit}"
        )
        return {"confidence": "exact", "source": "git", "commit": commit,
                "original_path": safe_path, "recovery_path": recovery_path,
                "sha256": _verify(registry.get_artifact_bytes(digest), expected_sha256) and digest,
                "size_bytes": len(data)}


class ZipRecoveryAdapter:
    """Reads a validated member from an archive without extracting paths to disk."""
    def recover(self, *, archive_path: str | Path, member_path: str,
                expected_sha256: str, project_id: str, registry,
                actor: str = "recovery") -> dict[str, Any]:
        import zipfile

        safe_member = _safe_relative(member_path)
        with zipfile.ZipFile(archive_path, "r") as archive:
            matches = [info for info in archive.infolist()
                       if not info.is_dir() and _safe_relative(info.filename) == safe_member]
            if len(matches) != 1:
                raise KeyError(f"archive member is missing or ambiguous: {safe_member}")
            data = _verify(archive.read(matches[0]), expected_sha256)
        recovery_path = f"_recovery/{uuid4().hex}/{safe_member}"
        digest = registry.put_artifact(
            project_id, recovery_path, data, actor=actor, operation_id="zip-recovery"
        )
        _verify(registry.get_artifact_bytes(digest), expected_sha256)
        return {"confidence": "exact", "source": "zip", "original_path": safe_member,
                "recovery_path": recovery_path, "sha256": digest, "size_bytes": len(data)}
