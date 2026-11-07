"""Build a bounded, secret-excluding source snapshot for Merlin Forge."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

_ALLOWED_ROOTS = (
    "python", "tests", "ui", "docs/merlin", "formal", "scripts",
    "docs/research/real-world-equation-atlas", "research/merlin",
    ".github/workflows",
)
_ROOT_FILES = (
    "README.md", "pyproject.toml", "Makefile", ".gitignore",
    "docs/research/merlin-mathematical-idea-catalog.v1.json",
)
_TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".yml", ".yaml", ".toml", ".txt", ".sh",
    ".js", ".mjs", ".cjs", ".html", ".css", ".lean", ".csv", ".svg",
}
_EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "dist",
    "build", ".cace", ".lake", ".cache", ".next", "target", "out", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "site-packages", "coverage",
}
_SENSITIVE_PARTS = {
    "secret", "secrets", "credential", "credentials", "token", "tokens",
    "password", "private", "private_key", "api_key", "apikey",
    "access_token", "client_secret",
}
_SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".env"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _excluded_reason(relative: str, path: Path) -> str | None:
    parts = [part.lower() for part in Path(relative).parts]
    name = path.name.lower()
    if any(part in _EXCLUDED_DIRS for part in parts):
        return "generated_or_dependency_directory"
    name_tokens = set(re.split(r"[^a-z0-9]+", Path(name).stem))
    if name == ".env" or name.startswith(".env.") or any(
        part in _SENSITIVE_PARTS or Path(part).stem in _SENSITIVE_PARTS
        or bool(name_tokens & _SENSITIVE_PARTS)
        for part in parts
    ):
        return "sensitive_name"
    if path.suffix.lower() in _SENSITIVE_SUFFIXES:
        return "sensitive_file_type"
    if path.suffix.lower() not in _TEXT_SUFFIXES:
        return "non_text_or_unapproved_file_type"
    return None


def build_repository_seed(
    repository_root: str | Path,
    *,
    max_files: int = 2000,
    max_file_bytes: int = 5_000_000,
    max_total_bytes: int = 50_000_000,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Return a deterministic text-only repository snapshot and its manifest.

    Sensitive files, generated directories, dependencies, binaries and symlinks
    are never copied into Forge. Size/count limits fail closed rather than
    silently creating a partial repository snapshot.
    """
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise ValueError("repository root must be an existing directory")
    for value, label, maximum in (
        (max_files, "max_files", 10000),
        (max_file_bytes, "max_file_bytes", 20_000_000),
        (max_total_bytes, "max_total_bytes", 500_000_000),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise ValueError(label + " is outside its allowed range")

    candidates: set[Path] = set()
    for name in _ROOT_FILES:
        path = root / name
        if path.exists():
            candidates.add(path)
    for pattern in ("requirements*.txt",):
        candidates.update(root.glob(pattern))
    for relative_root in _ALLOWED_ROOTS:
        directory = root / relative_root
        if directory.is_dir() and not directory.is_symlink():
            candidates.update(directory.rglob("*"))

    files: dict[str, bytes] = {}
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    excluded_total = 0
    total = 0

    def record_excluded(relative: str, reason: str) -> None:
        nonlocal excluded_total
        excluded_total += 1
        if len(excluded) < 500:
            excluded.append({"path": relative, "reason": reason})
    for path in sorted(candidates, key=lambda item: item.as_posix()):
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if path.is_symlink():
            record_excluded(relative, "symlink")
            continue
        reason = _excluded_reason(relative, path)
        if reason:
            record_excluded(relative, reason)
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > max_file_bytes:
            record_excluded(relative, "file_size_limit")
            continue
        raw = path.read_bytes()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            record_excluded(relative, "invalid_utf8")
            continue
        if len(files) >= max_files:
            raise ValueError("repository seed exceeds max_files; refusing partial snapshot")
        total += len(raw)
        if total > max_total_bytes:
            raise ValueError("repository seed exceeds max_total_bytes; refusing partial snapshot")
        digest = hashlib.sha256(raw).hexdigest()
        files[relative] = raw
        included.append({"path": relative, "sha256": digest, "size_bytes": len(raw)})

    if not files:
        raise ValueError("repository seed contains no eligible source files")
    manifest: dict[str, Any] = {
        "schema": "merlin-forge-seed-manifest/1",
        "snapshot_kind": "runtime-filesystem-source-snapshot",
        "source_commit": None,
        "file_count": len(included),
        "total_bytes": total,
        "included": included,
        "excluded_count": excluded_total,
        "excluded": excluded,
        "sensitive_files_included": False,
        "execution_performed": False,
        "source_commit_verified": False,
    }
    manifest["tree_sha256"] = hashlib.sha256(_canonical(included).encode("utf-8")).hexdigest()
    files["merlin/SEED_MANIFEST.json"] = _canonical(manifest) + b"\n"
    return files, manifest


__all__ = ["build_repository_seed"]
