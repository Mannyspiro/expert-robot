"""Read-only, fail-closed Merlin release evidence verifier.

Checks actual local evidence bytes, rather than trusting a manifest's digest.
This is not a deployment approval or a test of the underlying application.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import re
from pathlib import Path

REQUIRED = (
    "browser_native_socket", "browser_retained_state_recovery",
    "python_compatible_runtime", "studio_111_product_tests",
    "real_model_response", "offline_restart_readback",
    "ui_rendered_smoke", "package_install_rollback",
    "provider_preservation",
)
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
GIT_COMMIT_SHA1 = re.compile(r"[0-9a-f]{40}\Z")  # This source repository uses Git SHA-1 IDs.
MAX_EVIDENCE_BYTES = 16 * 1024 * 1024


def _evidence_digest(root: Path, locator: str) -> tuple[str, tuple[int, int]] | None:
    """Hash a bounded regular file strictly within the supplied evidence root."""
    if not locator or "\\" in locator or "\x00" in locator:
        return None
    rel = Path(locator)
    if rel.is_absolute() or rel.as_posix() != locator or any(part in (".", "..") for part in rel.parts):
        return None
    # Open each path component without following symlinks; avoid check/open races.
    try:
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            return None
        parts = rel.parts
        if not parts or any(part in ("", ".", "..") for part in parts):
            return None
        fd = os.open(root.resolve(strict=True), os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in parts[:-1]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=fd)
            try:
                info = os.fstat(file_fd)
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_EVIDENCE_BYTES:
                    return None
                digest = hashlib.sha256()
                size = 0
                while True:
                    chunk = os.read(file_fd, 65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_EVIDENCE_BYTES:
                        return None
                    digest.update(chunk)
                return digest.hexdigest(), (info.st_dev, info.st_ino)
            finally:
                os.close(file_fd)
        finally:
            os.close(fd)
    except (OSError, ValueError, RuntimeError):
        return None


def assess(manifest: object, evidence_root: Path, *, expected_source_commit: str | None = None) -> dict:
    # An externally observed checkout revision must be bound for review readiness.
    # Consistent self-reported source_commit fields alone are not source authentication.
    if expected_source_commit is not None and (
        not isinstance(expected_source_commit, str)
        or GIT_COMMIT_SHA1.fullmatch(expected_source_commit) is None
    ):
        raise ValueError("expected_source_commit must be a lowercase 40-hex Git SHA-1")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("gates"), dict):
        raise ValueError("manifest must contain a gates object")
    gates = manifest["gates"]
    report = {}
    commits = set()
    used_locators = set()
    used_file_ids = set()
    for name in REQUIRED:
        entry = gates.get(name)
        if not isinstance(entry, dict):
            report[name] = "missing"
            continue
        digest = entry.get("evidence_sha256")
        locator = entry.get("evidence_locator")
        source = entry.get("source_commit")
        valid_identity = (
            entry.get("status") == "passed"
            and isinstance(digest, str) and SHA256.fullmatch(digest) is not None
            and isinstance(source, str) and GIT_COMMIT_SHA1.fullmatch(source) is not None
            and isinstance(locator, str) and bool(locator.strip())
        )
        if not valid_identity:
            report[name] = "unqualified"
            continue
        actual = _evidence_digest(evidence_root, locator)
        if actual is None:
            report[name] = "evidence_unavailable"
        elif actual[0] != digest:
            report[name] = "digest_mismatch"
        elif locator in used_locators:
            report[name] = "reused_evidence_locator"
        elif actual[1] in used_file_ids:
            report[name] = "reused_evidence_file"
        elif expected_source_commit is not None and source != expected_source_commit:
            report[name] = "source_commit_mismatch"
        else:
            report[name] = "digest_verified"
            used_locators.add(locator)
            used_file_ids.add(actual[1])
            commits.add(source)
    if len(commits) > 1:
        for name in REQUIRED:
            if report[name] == "digest_verified":
                report[name] = "source_commit_mismatch"
    return {
        "ready_for_independent_review": (
            expected_source_commit is not None
            and all(v == "digest_verified" for v in report.values())
        ),
        "source_commit_bound_to_expected_revision": expected_source_commit is not None,
        "gate_status": report,
        "warning": "Evidence bytes verified; the truth of claims, test independence, and deployment authorization are NOT verified.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--expected-source-commit", help="40-hex SHA observed from the checked-out Git repository")
    args = parser.parse_args()
    try:
        report = assess(json.loads(args.manifest.read_text(encoding="utf-8")), args.evidence_root,
                        expected_source_commit=args.expected_source_commit)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"invalid release evidence: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready_for_independent_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
