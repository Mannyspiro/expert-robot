#!/usr/bin/env python3
"""Safely extract a verified Merlin offline AI ZIP to an EMPTY new directory.

The verifier runs before extraction. Open all regular files with O_EXCL and
O_NOFOLLOW and create symlinks only after regular files are finished. Reject
overwrites and remove partial output on failure. This cannot certify runtime
ABI, licenses, provenance signatures or model quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import posixpath
import shutil
import stat
import sys
import zipfile

# -I isolated CLI execution intentionally omits the script directory from
# sys.path. Load only the verifier beside this exact pinned extractor source.
# The caller must run the reviewed source from a trusted checkout.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_offline_profile import ROOT, BASE, PROFILE, verify as verify_archive, unique, safe_path


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def _parents_are_real(root: Path, target: Path):
    require(target.is_relative_to(root), "member escaped extraction root")
    current = root
    for segment in target.relative_to(root).parts[:-1]:
        current = current / segment
        try:
            state = current.lstat()
        except FileNotFoundError:
            current.mkdir(mode=0o700)
            state = current.lstat()
        require(stat.S_ISDIR(state.st_mode) and not stat.S_ISLNK(state.st_mode),
                "archive member parent is a symlink or special file")


def extract(source: Path, destination: Path):
    source = Path(source).expanduser()
    require(source.is_file() and not source.is_symlink(),
            "verified regular ZIP file required")
    # Full archive validation occurs before a single output member is written.
    audit = verify_archive(source)
    original_dest = Path(destination).expanduser()
    parent = original_dest.parent.resolve(strict=True)
    require(parent.is_dir() and not original_dest.exists()
            and not original_dest.is_symlink()
            and original_dest.name not in ("", ".", ".."),
            "destination must not already exist")
    target = parent / original_dest.name
    require(not target.exists() and not target.is_symlink(), "destination already exists")
    target.mkdir(mode=0o700)
    written = 0
    links = 0
    result = None
    try:
        with zipfile.ZipFile(source, "r") as archive:
            base = json.loads(archive.read(BASE), object_pairs_hook=unique)
            extra = json.loads(archive.read(PROFILE), object_pairs_hook=unique)
            identity = {r["path"]: r for r in base["files"]}
            for record in extra["files"]:
                require(record["path"] not in identity,
                        "duplicate extra file")
                identity[record["path"]] = record
            identity["PACKAGE_MANIFEST.json"] = None
            identity["OFFLINE_PROFILE_MANIFEST.json"] = None
            files = []
            symlinks = []
            for member in archive.infolist():
                require(member.filename.startswith(ROOT), "member outside root")
                rel = safe_path(member.filename[len(ROOT):])
                absolute = target / ROOT[:-1] / rel
                _parents_are_real(target, absolute)
                require(not absolute.exists() and not absolute.is_symlink(),
                        "duplicate extraction destination")
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    symlinks.append((member, absolute, rel))
                else:
                    require(stat.S_ISREG(mode), "unexpected special member")
                    files.append((member, absolute, rel))
            # First write all normal files; no member parent may be a symlink.
            for member, absolute, rel in files:
                _parents_are_real(target, absolute)
                expected = identity[rel]
                require(expected is not None or rel in ("PACKAGE_MANIFEST.json",
                                                       "OFFLINE_PROFILE_MANIFEST.json"),
                        "member has no source or manifest identity")
                fd = os.open(absolute, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
                digest = hashlib.sha256()
                size = 0
                try:
                    with os.fdopen(fd, "wb") as dest, archive.open(member) as content:
                        while True:
                            block = content.read(1024 * 1024)
                            if not block:
                                break
                            size += len(block)
                            require(size <= member.file_size,
                                    "unexpected decompressed member size")
                            digest.update(block)
                            dest.write(block)
                        dest.flush()
                        os.fsync(dest.fileno())
                except BaseException:
                    # fdopen closes on context exit, including exceptions.
                    raise
                require(size == member.file_size, "short extracted file")
                if expected is not None:
                    require(digest.hexdigest() == expected["sha256"]
                            and size == expected["bytes"],
                            "extracted bytes differ from package manifest")
                # Rebind mode to this file: the archive-inventory loop's
                # earlier mode belongs to its final member, not every file.
                member_mode = member.external_attr >> 16
                require(stat.S_ISREG(member_mode),
                        "extracted member changed from verified regular file")
                os.chmod(absolute, 0o755 if member_mode & 0o111 else 0o644)
                written += 1
            # Restore symbolic links only after regular files, preventing
            # any archived file from being extracted through a link.
            for member, absolute, rel in symlinks:
                _parents_are_real(target, absolute)
                require(not absolute.exists() and not absolute.is_symlink(),
                        "symlink destination already occupied")
                text = archive.read(member).decode("utf-8")
                reference = identity[rel]
                require(reference and reference.get("kind") == "symlink",
                        "undeclared symlink rejected")
                normalized = posixpath.normpath(posixpath.join(
                    posixpath.dirname(rel), text))
                require(normalized.startswith("runtime/python/"),
                        "runtime symlink escapes declared Python directory")
                os.symlink(text, absolute)
                links += 1
            # All final symlinks must resolve inside the new Python runtime.
            python_root = (target / ROOT[:-1] / "runtime" / "python").resolve(strict=True)
            for _, absolute, _ in symlinks:
                resolved = absolute.resolve(strict=True)
                require(resolved.is_relative_to(python_root),
                        "newly extracted symlink resolves outside Python runtime")
        result = {"schema": "merlin-safe-offline-extract/1",
                  "status": "extracted_unqualified",
                  "verified_members": audit["files_checked"],
                  "written_regular_files": written,
                  "restored_safe_symlinks": links,
                  "target_platform": audit["target_platform"],
                  "runtime_executed": False,
                  "model_executed": False,
                  "license_review_completed": False,
                  "production_qualified": False}
        return result
    except BaseException:
        shutil.rmtree(target)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = extract(args.zip, args.destination)
        print(json.dumps(result, sort_keys=True, indent=2))
    except (OSError, ValueError, TypeError, RuntimeError,
            UnicodeError, zipfile.BadZipFile) as exc:
        parser.exit(2, "Offline extraction rejected: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
