#!/usr/bin/env python3
"""Verify shipped Merlin Studio file hashes in a ZIP or extracted directory.

This checks integrity against the manifest, not authenticity, model quality,
capability qualification, or optional files added after extraction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

MAX_FILE_BYTES = 64 * 1024 * 1024


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("Invalid manifest path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ValueError("Unsafe manifest path: " + value)
    return path


def check_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get("schema") != "merlin-studio-portable/1":
        raise ValueError("Unsupported package manifest")
    root = manifest.get("archive_root")
    if len(relative_path(root).parts) != 1:
        raise ValueError("Invalid archive root")
    files = manifest.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= 4096:
        raise ValueError("Invalid manifest inventory")
    seen = set()
    for entry in files:
        name = relative_path(entry["path"]).as_posix()
        if name in seen or name == "PACKAGE_MANIFEST.json":
            raise ValueError("Duplicate or circular manifest path")
        seen.add(name)
        if type(entry["bytes"]) is not int or not 0 <= entry["bytes"] <= MAX_FILE_BYTES:
            raise ValueError("Invalid file size")
        if not isinstance(entry["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
            raise ValueError("Invalid file digest")
        if entry.get("mode") not in ("0644", "0755"):
            raise ValueError("Invalid file mode")
    return files


def verify(path: Path) -> dict:
    path = Path(path).resolve()
    if path.is_dir():
        manifest_path = path / "PACKAGE_MANIFEST.json"
        if manifest_path.is_symlink() or manifest_path.stat().st_size > 1024 * 1024:
            raise ValueError("Invalid package manifest file")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = check_manifest(manifest)
        for entry in files:
            target = path.joinpath(*relative_path(entry["path"]).parts)
            target.resolve().relative_to(path)
            if target.is_symlink() or not target.is_file() or target.stat().st_size != entry["bytes"]:
                raise ValueError("Missing or size-changed file: " + entry["path"])
            if hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("Changed file: " + entry["path"])
        scope = "extracted shipped files; optional and user-created files are outside this verification"
    else:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = [e.filename for e in entries]
            if len(names) != len(set(names)) or len(names) > 4097:
                raise ValueError("Duplicate or excessive ZIP entries")
            for item in entries:
                relative_path(item.filename)
                if item.is_dir() or stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1:
                    raise ValueError("Unexpected directory, symlink, or encrypted ZIP member")
                if item.file_size > MAX_FILE_BYTES:
                    raise ValueError("Oversized ZIP member")
            manifests = [n for n in names if n.endswith("/PACKAGE_MANIFEST.json")]
            if len(manifests) != 1 or archive.getinfo(manifests[0]).file_size > 1024 * 1024:
                raise ValueError("One bounded package manifest is required")
            manifest = json.loads(archive.read(manifests[0]))
            files = check_manifest(manifest)
            prefix = manifest["archive_root"] + "/"
            expected = {prefix + entry["path"] for entry in files} | {prefix + "PACKAGE_MANIFEST.json"}
            if set(names) != expected:
                raise ValueError("ZIP inventory differs from manifest")
            for entry in files:
                name = prefix + entry["path"]
                item = archive.getinfo(name)
                if item.file_size != entry["bytes"] or hashlib.sha256(archive.read(name)).hexdigest() != entry["sha256"]:
                    raise ValueError("Changed file: " + entry["path"])
                if (item.external_attr >> 16) & 0o777 != int(entry["mode"], 8):
                    raise ValueError("Changed file mode: " + entry["path"])
        scope = "complete ZIP inventory and shipped file hashes"
    return {"verified": True, "file_count": len(files), "schema": manifest["schema"],
            "native_protocol": manifest["native_protocol"], "scope": scope,
            "authenticity_verified": False, "model_quality_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=Path(__file__).resolve().parent,
                        help="ZIP or extracted Merlin_Studio folder (default: this script's folder)")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.path), sort_keys=True, indent=2))
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        parser.exit(1, "Package verification failed: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
