#!/usr/bin/env python3
"""Bounded, redacted secret-pattern audit of Git-tracked source and ZIP evidence.

No network or credentials. This catches a selected set of token patterns, not
all possible secrets. Never include matched bytes in reports, logs or errors.
A passing result is limited to the recorded byte coverage, not release approval.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import zipfile

MAX_FILE = 32 * 1024 * 1024
MAX_MEMBER = 12 * 1024 * 1024
MAX_ARCHIVE_UNPACKED = 160 * 1024 * 1024
MAX_TOTAL = 1_200 * 1024 * 1024
MAX_MEMBERS = 3000
MAX_FINDINGS = 500
SHA = re.compile(r"[0-9a-f]{40}\Z")

# Obscure fixed signature prefixes in source to avoid a false match on the
# scanner's own literals. This is not obfuscation of actual matches.
RULES = (
    ("private_key", re.compile(b"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("github_classic", re.compile(b"gh" + b"p_" + rb"[A-Za-z0-9]{30,}")),
    ("github_fine_grained", re.compile(b"github" + b"_pat_" + rb"[A-Za-z0-9_]{50,}")),
    ("github_oauth", re.compile(b"gh" + b"[ousr]_" + rb"[A-Za-z0-9]{30,}")),
    ("gitlab_personal", re.compile(b"gl" + b"pat-" + rb"[A-Za-z0-9_-]{20,}")),
    ("openai_api", re.compile(b"sk" + b"-(?:proj-)?[A-Za-z0-9_-]{30,}")),
    ("aws_access", re.compile(b"AK" + b"IA" + rb"[A-Z0-9]{16}")),
    ("google_api", re.compile(b"AI" + b"za" + rb"[0-9A-Za-z_-]{35}")),
    ("slack_bot", re.compile(b"xo" + b"xb-" + rb"[0-9]{10,}-[A-Za-z0-9-]{15,}")),
)

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def git_source_files(root: Path) -> list[str]:
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                            capture_output=True, check=True, timeout=30)
    return sorted(x.decode("utf-8") for x in result.stdout.split(b"\0") if x)

def snapshot(root: Path, expected_sha: str):
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise ValueError("Lowercase exact Git commit required")
    actual = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                            capture_output=True, check=True, text=True, timeout=20).stdout.strip()
    if actual != expected_sha:
        raise ValueError("Source revision differs")
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, check=True, timeout=20).stdout
    if dirty:
        raise ValueError("Tracked source modified during audit")
    return actual

def audit_paths(files, read_file, *, source_sha="fixture"):
    findings = []
    skipped = []
    errors = []
    examined = 0
    tracked_bytes = 0
    inspected_members = 0
    zip_bytes = 0
    total = 0

    def check(raw, locator):
        nonlocal examined, total
        if total + len(raw) > MAX_TOTAL:
            skipped.append({"path": locator, "reason": "total_byte_budget"})
            return False
        examined += 1
        total += len(raw)
        for label, pattern in RULES:
            for match in pattern.finditer(raw):
                if len(findings) >= MAX_FINDINGS:
                    errors.append("max_findings")
                    return False
                findings.append({"locator": locator, "rule": label,
                                 "offset": match.start(),
                                 "fingerprint_sha256": sha256(match.group())})
        return True

    for name in files:
        # Source paths are canonical from Git or an explicitly controlled fixture.
        if (not isinstance(name, str) or not name or name.startswith("/")
                or "\\" in name or "\0" in name
                or any(x in ("", ".", "..") for x in name.split("/"))):
            errors.append("invalid_source_path")
            continue
        try:
            raw = read_file(name)
        except (ValueError, OSError) as exc:
            skipped.append({"path": name, "reason": "unreadable_" + type(exc).__name__})
            continue
        if len(raw) > MAX_FILE:
            skipped.append({"path": name, "reason": "oversized_source"})
            continue
        tracked_bytes += len(raw)
        if not check(raw, name):
            continue
        if not raw.startswith(b"PK\x03\x04"):
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = archive.infolist()
                if len(members) > MAX_MEMBERS:
                    skipped.append({"path": name, "reason": "zip_member_count_exceeded"})
                    continue
                allotted = 0
                for member in members:
                    if member.is_dir():
                        continue
                    if (member.file_size > MAX_MEMBER
                            or allotted + member.file_size > MAX_ARCHIVE_UNPACKED
                            or member.flag_bits & 1):
                        skipped.append({"path": name + "::" + member.filename[:150],
                                        "reason": "zip_member_budget_or_encryption"})
                        continue
                    # A ZIP pathname is only a reporting label, never an output path.
                    inner = member.filename.replace("\n", "_").replace("\r", "_")[:160]
                    try:
                        payload = archive.read(member)
                    except (RuntimeError, OSError, zipfile.BadZipFile, ValueError):
                        skipped.append({"path": name + "::" + inner, "reason": "zip_member_read_failed"})
                        continue
                    allotted += len(payload)
                    zip_bytes += len(payload)
                    inspected_members += 1
                    check(payload, name + "::" + inner)
        except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile):
            skipped.append({"path": name, "reason": "invalid_zip_container"})
    status = "findings" if findings else "partial" if skipped or errors else "no_patterns_detected"
    return {
        "schema": "merlin-source-secret-pattern-audit/1",
        "source_commit": source_sha,
        "status": status,
        "rules": [name for name, _ in RULES],
        "git_paths_recorded": len(files),
        "raw_source_bytes_examined": tracked_bytes,
        "total_pattern_bytes_examined": total,
        "examined_byte_sequences": examined,
        "zip_members_examined": inspected_members,
        "zip_member_bytes_examined": zip_bytes,
        "findings": findings, "omissions": skipped, "errors": errors,
        "matched_bytes_emitted": False, "scope": "selected token signatures, bounded Git-tracked byte content and single-level ZIP members",
        "secret_absence_proven": False, "production_qualified": False,
    }

def audit_git(root: Path, sha: str):
    root = root.resolve(strict=True)
    snapshot(root, sha)
    files = git_source_files(root)
    def load(name):
        path = root
        for segment in name.split("/"):
            path = path / segment
            if path.is_symlink():
                raise ValueError("symlink")
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("nonregular")
        if info.st_size > MAX_FILE:
            return b"\x00" * (MAX_FILE + 1)  # no unbounded read
        return path.read_bytes()
    result = audit_paths(files, load, source_sha=sha)
    snapshot(root, sha)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_git(args.root, args.expected_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "paths": result["git_paths_recorded"],
                      "findings": len(result["findings"]), "skipped": len(result["omissions"]),
                      "zip_members": result["zip_members_examined"],
                      "matched_bytes_emitted": False, "production_qualified": False}, sort_keys=True))
    return 0 if result["status"] == "no_patterns_detected" else 2

if __name__ == "__main__":
    raise SystemExit(main())
