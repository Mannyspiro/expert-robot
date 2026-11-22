#!/usr/bin/env python3
"""Integrity-only verifier for a Linux Merlin self-contained offline profile.

This verifies exact archive inventory, bytes, source-license receipts, paths,
platform headers and safe runtime symlinks. It does NOT verify authenticity,
redistribution rights, AI reasoning, runtime ABI or actual startup.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import PurePosixPath
import posixpath
import re
import stat
import struct
import zipfile

ROOT = "Merlin_Studio/"
PROFILE = ROOT + "OFFLINE_PROFILE_MANIFEST.json"
BASE = ROOT + "PACKAGE_MANIFEST.json"
SCHEMA = "merlin-linux-offline-profile/1"
MAX_RECORDS = 16000
MAX_TOTAL = 16 * 1024**3
MAX_RUNTIME_FILE = 512 * 1024**2
MAX_MODEL_FILE = 8 * 1024**3
PLATFORMS = {"linux-x86_64": 62, "linux-aarch64": 183}
SHA = re.compile(r"[0-9a-f]{64}\Z")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON field")
        result[key] = value
    return result


def safe_path(path):
    require(isinstance(path, str) and 1 <= len(path) <= 512
            and "\\" not in path and "\x00" not in path,
            "invalid ZIP path")
    parsed = PurePosixPath(path)
    require(not parsed.is_absolute() and parsed.as_posix() == path
            and all(p not in (".", "..", "") for p in path.split("/")),
            "unsafe ZIP path")
    return path


def digest_member(archive, member, *, max_bytes):
    expected_size = member.file_size
    require(0 <= expected_size <= max_bytes, "unbounded archive member size")
    digest = hashlib.sha256()
    count = 0
    with archive.open(member) as source:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            count += len(block)
            require(count <= max_bytes, "unbounded ZIP extraction")
            digest.update(block)
    require(count == expected_size, "ZIP member size drift")
    return digest.hexdigest(), count


def check_entry(archive, info, record, *, max_bytes, allow_symlink=False):
    path = safe_path(record["path"])
    require(info.filename == ROOT + path, "wrong member identity")
    kind = record.get("kind", "file")
    require(kind in ("file", "symlink") and (kind != "symlink" or allow_symlink),
            "unexpected archive member kind")
    require(type(record.get("bytes")) is int and 0 <= record["bytes"] <= max_bytes
            and isinstance(record.get("sha256"), str) and SHA.fullmatch(record["sha256"]),
            "unbounded or unpinned manifest file")
    mode = info.external_attr >> 16
    require(info.create_system == 3 and not info.is_dir()
            and not info.flag_bits & 1
            and (stat.S_ISLNK(mode) if kind == "symlink" else stat.S_ISREG(mode)),
            "non-regular, encrypted or wrong ZIP member kind")
    expected_mode = "0777" if kind == "symlink" else record.get("mode")
    require(expected_mode in ("0644", "0755", "0777")
            and (mode & 0o777) == int(expected_mode, 8),
            "archive executable/permission bits differ")
    digest, length = digest_member(archive, info, max_bytes=max_bytes)
    require(length == record["bytes"] and digest == record["sha256"],
            "archive member digest differs")
    if kind == "symlink":
        require(path.startswith("runtime/python/"), "symlink outside bundled Python runtime")
        target = archive.read(info).decode("utf-8")
        require(target and not target.startswith("/") and "\\" not in target and "\x00" not in target
                and len(target) <= 512,
                "unsafe symlink destination")
        normalized = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
        require(normalized.startswith("runtime/python/"),
                "Python runtime symlink escapes its own root")
    return path


def verify(archive_path):
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        require(len(names) == len(set(names)) and len(names) <= MAX_RECORDS,
                "duplicate or excessive ZIP member count")
        require(PROFILE in names and BASE in names, "base/package manifests missing")
        for info in infos:
            safe_path(info.filename)
            require(info.filename.startswith(ROOT), "ZIP member outside Merlin_Studio")
        profile_info = archive.getinfo(PROFILE)
        base_info = archive.getinfo(BASE)
        require(profile_info.file_size <= 1024 * 1024
                and base_info.file_size <= 1024 * 1024,
                "unbounded manifest")
        profile = json.loads(archive.read(PROFILE), object_pairs_hook=unique)
        base = json.loads(archive.read(BASE), object_pairs_hook=unique)
        require(isinstance(profile, dict) and profile.get("schema") == SCHEMA
                and profile.get("archive_root") == ROOT[:-1]
                and profile.get("platform") in PLATFORMS
                and profile.get("model_id") == "local"
                and profile.get("production_qualified") is False
                and profile.get("authenticity_verified") is False
                and profile.get("license_review_completed") is False,
                "offline profile claims unsupported scope")
        require(isinstance(base, dict) and base.get("schema") == "merlin-studio-portable/1"
                and base.get("archive_root") == ROOT[:-1]
                and base.get("contains_python_runtime") is False
                and base.get("contains_model_weights") is False,
                "inner Studio ZIP source manifest differs")
        base_records = base.get("files")
        extra_records = profile.get("files")
        require(isinstance(base_records, list) and 1 <= len(base_records) <= 500
                and isinstance(extra_records, list) and 6 <= len(extra_records) <= MAX_RECORDS - 501,
                "invalid package inventories")
        checks = {}
        total = 0
        for item in base_records:
            require(isinstance(item, dict), "malformed Studio record")
            name = safe_path(item.get("path"))
            require(name != "PACKAGE_MANIFEST.json" and name not in checks,
                    "duplicate Studio file")
            info = archive.getinfo(ROOT + name)
            record = {**item, "kind": "file"}
            check_entry(archive, info, record, max_bytes=64 * 1024 * 1024)
            total += info.file_size
            checks[name] = "studio"
        for record in extra_records:
            require(isinstance(record, dict), "malformed profile record")
            name = safe_path(record.get("path"))
            require(name not in checks and name not in ("PACKAGE_MANIFEST.json",
                    "OFFLINE_PROFILE_MANIFEST.json"), "duplicate profile file")
            bound = MAX_MODEL_FILE if name == "models/merlin-local.gguf" else MAX_RUNTIME_FILE
            if name.startswith("licenses/"):
                bound = 128 * 1024
            check_entry(archive, archive.getinfo(ROOT + name), record,
                        max_bytes=bound, allow_symlink=True)
            total += record["bytes"]
            require(total <= MAX_TOTAL, "profile total uncompressed data exceeded")
            checks[name] = record["kind"]
        expected = {ROOT + name for name in checks} | {BASE, PROFILE}
        require(set(names) == expected, "unknown or missing ZIP members")
        required = {"bin/llama-server", "models/merlin-local.gguf",
                    "runtime/python/bin/python3", "PROFILE_VERIFY.py",
                    "licenses/model.txt", "licenses/inference.txt",
                    "licenses/python.txt"}
        require(required.issubset(checks), "missing offline runtime or license asset")
        require(checks["bin/llama-server"] == "file"
                and checks["models/merlin-local.gguf"] == "file", "binary asset is not regular")
        headers = (
            ("bin/llama-server", PLATFORMS[profile["platform"]]),
            ("runtime/python/bin/python3", PLATFORMS[profile["platform"]])
        )
        for path, machine in headers:
            info = archive.getinfo(ROOT + path)
            if checks[path] == "symlink":
                # python3 is typically a safe relative symlink to python3.11.
                link = archive.read(info).decode("utf-8")
                target = posixpath.normpath(posixpath.join(posixpath.dirname(path), link))
                require(target.startswith("runtime/python/") and checks.get(target) == "file",
                        "unresolved Python executable symlink")
                info = archive.getinfo(ROOT + target)
            with archive.open(info) as source:
                head = source.read(20)
            require(len(head) == 20 and head[:6] == b"\x7fELF\x02\x01"
                    and struct.unpack("<H", head[18:20])[0] == machine,
                    "binary architecture or format differs")
        with archive.open(ROOT + "models/merlin-local.gguf") as source:
            require(source.read(4) == b"GGUF", "model asset is not GGUF")
        origin = profile.get("origins")
        require(isinstance(origin, dict) and set(origin) == {"python", "model", "inference"}
                and all(isinstance(value, str) and value.startswith("https://")
                        and len(value) <= 1024 for value in origin.values()),
                "missing explicitly declared asset publishers")
        return {"verified": True, "schema": SCHEMA,
                "target_platform": profile["platform"], "files_checked": len(checks),
                "bytes_checked": total, "model_sha256": next(r["sha256"] for r in extra_records
                                                          if r["path"] == "models/merlin-local.gguf"),
                "contains_python_runtime": True, "contains_model_weights": True,
                "contains_inference_engine": True,
                "license_receipts_present": True,
                "authenticity_verified": False, "license_review_completed": False,
                "production_qualified": False,
                "native_executable_started": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", help="Complete Linux offline profile ZIP")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.zip), sort_keys=True, indent=2))
    except (OSError, ValueError, KeyError, TypeError,
            UnicodeError, zipfile.BadZipFile) as exc:
        parser.exit(2, "Offline profile verification failed: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
