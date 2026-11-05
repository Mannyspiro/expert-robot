"""Exact-byte recovery adapters. All restores target quarantine paths, never canonical paths."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any
from uuid import uuid4

from merlin.change_manifest import build_change_manifest


def _safe_relative(path: str) -> str:
    normalized = path.replace("\\", "/")
    value = PurePosixPath(normalized)
    if not normalized or value.is_absolute() or any(part in {"", ".", ".."} for part in value.parts):
        raise ValueError("recovery path must be relative and traversal-free")
    if ":" in value.parts[0]:
        raise ValueError("drive-qualified recovery path is forbidden")
    return str(value)


def _verify(data: bytes, expected_sha256: str) -> bytes:
    if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64
            or any(char not in "0123456789abcdef" for char in expected_sha256)):
        raise ValueError("expected SHA-256 must be 64 lowercase hexadecimal characters")
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"recovered bytes do not match expected SHA-256: {actual}")
    return data


class RegistryRecoveryAdapter:
    def __init__(self, registry):
        self.registry = registry

    def recover(self, *, digest: str, project_id: str, original_path: str,
                actor: str = "recovery") -> dict[str, Any]:
        try:
            source_bytes = self.registry.get_artifact_bytes(digest)
        except KeyError:
            # Recover an orphaned content-addressed blob even if its SQLite index row was lost.
            blob_path = self.registry.blobs / digest[:2] / digest[2:]
            if not blob_path.is_file():
                raise
            source_bytes = blob_path.read_bytes()
        data = _verify(source_bytes, digest)
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

    @staticmethod
    def _pinned_commit(commit: str) -> str:
        if (not isinstance(commit, str) or len(commit) != 40
                or any(char not in "0123456789abcdef" for char in commit)):
            raise ValueError("a full lowercase 40-character Git commit SHA is required")
        return commit

    def tree_manifest(self, commit: str, *, max_entries: int = 25000,
                      max_total_bytes: int = 1_000_000_000,
                      max_blob_bytes: int = 100_000_000) -> dict[str, Any]:
        """Inventory every tracked tree entry at a pinned commit with exact blob hashes."""
        commit = self._pinned_commit(commit)
        listing = subprocess.run(
            ["git", "-C", str(self.repository), "ls-tree", "-rz", "--full-tree", commit],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout
        entries = []
        total_bytes = 0
        for record in listing.split(b"\0"):
            if not record:
                continue
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split(" ")
            path = raw_path.decode("utf-8", errors="surrogateescape")
            safe_path = _safe_relative(path)
            if object_type == "blob":
                size = int(subprocess.run(
                    ["git", "-C", str(self.repository), "cat-file", "-s", object_id],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True,
                ).stdout.strip())
                if size > max_blob_bytes:
                    raise ValueError("Git manifest blob exceeds configured per-file limit")
                total_bytes += size
                if total_bytes > max_total_bytes:
                    raise ValueError("Git manifest exceeds configured total-byte limit")
                data = subprocess.run(
                    ["git", "-C", str(self.repository), "cat-file", "blob", object_id],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                ).stdout
                if len(data) != size:
                    raise RuntimeError("Git blob size mismatch during manifest creation")
                digest = hashlib.sha256(data).hexdigest()
            else:
                size = 0
                digest = hashlib.sha256((object_type + ":" + object_id).encode()).hexdigest()
            entries.append({
                "path": safe_path, "sha256": digest, "size_bytes": size,
                "mode": mode, "git_object_type": object_type,
                "git_object_id": object_id,
            })
            if len(entries) > max_entries:
                raise ValueError("Git manifest exceeds configured entry-count limit")
        return {"schema": "merlin-git-tree-manifest/1", "commit": commit, "artifacts": entries}

    def audit_history(self, base_commit: str, head_commit: str, *,
                      max_commits: int = 500) -> dict[str, Any]:
        """Audit every first-parent commit in a pinned range, not only its net diff.

        Each commit receives a full tracked-tree digest inventory plus Git's
        rename/copy-aware per-commit change records. Untracked and ignored
        filesystem entries are deliberately outside this Git-tree audit.
        """
        base = self._pinned_commit(base_commit)
        head = self._pinned_commit(head_commit)
        commits = subprocess.run(
            ["git", "-C", str(self.repository), "rev-list", "--reverse",
             "--first-parent", f"{base}..{head}"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        ).stdout.splitlines()
        if len(commits) > max_commits:
            raise ValueError("Git history audit exceeds configured commit limit")
        # Ensure the requested base is an ancestor of the requested head.
        subprocess.run(
            ["git", "-C", str(self.repository), "merge-base", "--is-ancestor", base, head],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        entries = []
        previous = base
        for commit in commits:
            changes = subprocess.run(
                ["git", "-C", str(self.repository), "diff-tree", "--no-commit-id",
                 "--name-status", "-r", "-M", "-C", "-z", previous, commit],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ).stdout.split(b"\\0")
            records = []
            index = 0
            while index < len(changes) and changes[index]:
                status = changes[index].decode("ascii")
                index += 1
                if status.startswith(("R", "C")):
                    if index + 1 >= len(changes):
                        raise RuntimeError("truncated Git rename/copy record")
                    old_path = changes[index].decode("utf-8", errors="surrogateescape")
                    new_path = changes[index + 1].decode("utf-8", errors="surrogateescape")
                    index += 2
                    records.append({"status": status, "old_path": old_path, "new_path": new_path})
                else:
                    if index >= len(changes):
                        raise RuntimeError("truncated Git path record")
                    path = changes[index].decode("utf-8", errors="surrogateescape")
                    index += 1
                    records.append({"status": status, "path": path})
            before_tree = self.tree_manifest(previous)
            after_tree = self.tree_manifest(commit)
            entries.append({
                "commit": commit,
                "parent": previous,
                "change_records": records,
                "before_tree_sha256": hashlib.sha256(
                    json.dumps(before_tree, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
                "after_tree_sha256": hashlib.sha256(
                    json.dumps(after_tree, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
                "before_entry_count": len(before_tree["artifacts"]),
                "after_entry_count": len(after_tree["artifacts"]),
            })
            previous = commit
        if previous != head:
            raise ValueError("head commit is not on the requested first-parent range")
        return {
            "schema": "merlin-git-history-audit/1",
            "base_commit": base,
            "head_commit": head,
            "commit_count": len(entries),
            "commits": entries,
            "untracked_and_ignored_included": False,
        }

    def compare_commits(self, before_commit: str, after_commit: str, *,
                        operation_id: str, actor: str, reason: str) -> dict[str, Any]:
        """Produce a complete tracked-file manifest; unapproved deletions remain blocked."""
        before = self.tree_manifest(before_commit)
        after = self.tree_manifest(after_commit)
        return build_change_manifest(
            before, after, operation_id=operation_id, actor=actor, reason=reason,
        )

    def recover(self, *, commit: str, path: str, expected_sha256: str,
                project_id: str, registry, actor: str = "recovery") -> dict[str, Any]:
        commit = self._pinned_commit(commit)
        safe_path = _safe_relative(path)
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
