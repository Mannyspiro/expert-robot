#!/usr/bin/env python3
"""Assemble an explicit, license-receipted Linux offline AI profile from local assets.

No network, model downloads, passwords or host installation. Supply a verified
Studio ZIP, extracted portable Python runtime, llama-server ELF, one GGUF, three
license receipts and exact byte digests. Output remains UNQUALIFIED until it
passes real target-host startup, model tool use, recovery, ABI and rights review.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import shutil
import stat
import struct
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_portable import verify as verify_studio
from verify_offline_profile import verify as verify_offline

ARCHIVE = "Merlin_Studio/"
DATE = (1980, 1, 1, 0, 0, 0)
PLATFORMS = {"linux-x86_64": 62, "linux-aarch64": 183}
MAX_RUNTIME_FILES = 12000
MAX_RUNTIME_TOTAL = 2 * 1024**3
SHA = re.compile(r"[0-9a-f]{64}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_hash(path, *, max_size, allow_empty=False):
    p = Path(path)
    require(p.is_file() and not p.is_symlink(), "regular input required: " + str(p))
    size = p.stat().st_size
    require(0 <= size <= max_size if allow_empty else 0 < size <= max_size,
            "asset size exceeds fixed limit: " + str(p))
    h = hashlib.sha256()
    with p.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest(), size


def assert_hash(path, expected, *, max_size):
    require(isinstance(expected, str) and SHA.fullmatch(expected),
            "explicit SHA256 required")
    actual, size = file_hash(path, max_size=max_size)
    require(actual == expected, "asset does not match expected SHA256")
    return size


def elf_machine(path):
    with Path(path).open("rb") as source:
        header = source.read(20)
    require(len(header) == 20 and header[:6] == b"\x7fELF\x02\x01",
            "little-endian ELF64 binary required")
    return struct.unpack("<H", header[18:20])[0]


def safe_runtime_link(path, root):
    target = os.readlink(path)
    require(isinstance(target, str) and target and not target.startswith("/")
            and "\\" not in target and "\x00" not in target
            and len(target) <= 512,
            "invalid absolute or oversized Python runtime symlink")
    try:
        resolved = (path.parent / target).resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("Python runtime link escapes verified runtime root") from exc
    return target.encode("utf-8")


def runtime_records(directory):
    root = Path(directory)
    require(root.is_dir() and not root.is_symlink(), "Python runtime root must be a directory")
    records = []
    total = 0
    for path in sorted(root.rglob("*"), key=lambda x: x.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        parts = Path(rel).parts
        # The standalone runtime may carry derived CPython bytecode caches.
        # They are unnecessary in the redistributable ZIP; omit, never ingest.
        if "__pycache__" in parts:
            continue
        require(not any(part in (".git", ".env", ".ssh", "credentials")
                        for part in parts), "secret path in runtime assets")
        if path.is_dir() and not path.is_symlink():
            continue
        relpath = "runtime/python/" + rel
        if path.is_symlink():
            raw = safe_runtime_link(path, root)
            item = (relpath, "symlink", path, raw)
            size = len(raw)
        else:
            require(path.is_file() and stat.S_ISREG(path.lstat().st_mode),
                    "special Python runtime file rejected")
            size = path.stat().st_size
            require(0 <= size <= 512 * 1024**2, "Python runtime member oversized")
            item = (relpath, "file", path, None)
        total += size
        require(total <= MAX_RUNTIME_TOTAL, "Python runtime exceeds 2 GiB")
        records.append(item)
        require(len(records) <= MAX_RUNTIME_FILES, "Python runtime has excessive file count")
    require(records, "Python runtime is empty")
    return records


def zipinfo(relative, kind, executable=False):
    info = zipfile.ZipInfo(ARCHIVE + relative, date_time=DATE)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.flag_bits |= 0x800
    mode = 0o777 if kind == "symlink" else (0o755 if executable else 0o644)
    info.external_attr = ( (stat.S_IFLNK if kind == "symlink" else stat.S_IFREG) | mode) << 16
    return info, format(mode, "04o")


def write_path(output, relative, path=None, *, kind="file", raw=None, executable=False, allow_empty=False):
    info, mode = zipinfo(relative, kind, executable)
    if raw is not None:
        require(len(raw) <= 128 * 1024, "inline profile data exceeds bound")
        output.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
        data_hash = hashlib.sha256(raw).hexdigest()
        length = len(raw)
    else:
        source = Path(path)
        data_hash, length = file_hash(source, max_size=8 * 1024**3, allow_empty=allow_empty)
        with source.open("rb") as reader, output.open(info, "w", force_zip64=True) as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
    return {"path": relative, "bytes": length,
            "sha256": data_hash, "mode": mode, "kind": kind}


def build(*, studio_zip, python_root, python_sha256, llama_server,
          llama_sha256, gguf_model, gguf_sha256, model_license,
          inference_license, python_license, output,
          target, model_origin, inference_origin, python_origin):
    require(target in PLATFORMS, "Linux x86_64/aarch64 only")
    for label, origin in (("model", model_origin), ("inference", inference_origin),
                          ("python", python_origin)):
        require(isinstance(origin, str) and origin.startswith("https://")
                and len(origin) <= 1024 and "\n" not in origin and "@" not in origin,
                "HTTPS publisher origin required: " + label)
    studio_zip = Path(studio_zip).resolve(strict=True)
    verify_studio(studio_zip)
    runtime = Path(python_root).resolve(strict=True)
    require(runtime.is_dir() and not Path(python_root).is_symlink(),
            "explicit extracted Python runtime required")
    python_entry = runtime / "bin" / "python3"
    require(python_entry.exists() and python_entry.is_file()
            and python_entry.resolve(strict=True).is_relative_to(runtime),
            "portable Python bin/python3 must resolve within runtime")
    assert_hash(python_entry.resolve(strict=True), python_sha256, max_size=512 * 1024**2)
    require(elf_machine(python_entry.resolve(strict=True)) == PLATFORMS[target],
            "Python ELF target architecture differs")
    assert_hash(llama_server, llama_sha256, max_size=512 * 1024**2)
    require(elf_machine(llama_server) == PLATFORMS[target],
            "inference server ELF target differs")
    assert_hash(gguf_model, gguf_sha256, max_size=8 * 1024**3)
    with Path(gguf_model).open("rb") as handle:
        require(handle.read(4) == b"GGUF", "inference model is not GGUF")
    runtime = runtime.resolve()
    runtime_files = runtime_records(runtime)
    license_paths = {
        "licenses/model.txt": model_license,
        "licenses/inference.txt": inference_license,
        "licenses/python.txt": python_license,
    }
    for path in license_paths.values():
        file_hash(path, max_size=128 * 1024)
    verifier_source = ROOT / "scripts" / "verify_offline_profile.py"
    file_hash(verifier_source, max_size=512 * 1024)
    destination = Path(output).expanduser().resolve()
    require(not destination.is_relative_to(runtime)
            and destination != studio_zip and destination != Path(llama_server).resolve()
            and destination != Path(gguf_model).resolve(),
            "output cannot overwrite or join an input source")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=".merlin-offline-", suffix=".zip", dir=destination.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(studio_zip) as original, zipfile.ZipFile(
                temp_name, "w", allowZip64=True) as package:
            for source_info in sorted(original.infolist(), key=lambda x: x.filename):
                raw = original.read(source_info)
                rel = source_info.filename.removeprefix(ARCHIVE)
                executable = (source_info.external_attr >> 16) & 0o111 != 0
                meta, _ = zipinfo(rel, "file", executable)
                package.writestr(meta, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
            records = []
            for rel, kind, path, raw in runtime_files:
                executable = (kind == "file" and bool(stat.S_IMODE(path.lstat().st_mode) & 0o111))
                records.append(write_path(package, rel, path=path,
                                          kind=kind, raw=raw, executable=executable,
                                          allow_empty=True))
            records.append(write_path(package, "bin/llama-server",
                                      path=llama_server, executable=True))
            records.append(write_path(package, "models/merlin-local.gguf",
                                      path=gguf_model))
            for rel, path in sorted(license_paths.items()):
                records.append(write_path(package, rel, path=path))
            records.append(write_path(package, "PROFILE_VERIFY.py",
                                      path=verifier_source))
            # A local input may be replaced after the first pin check.
            # Bind the bytes actually archived to the original expected pins,
            # not merely to self-consistent post-swap manifest digests.
            packed = {entry["path"]: entry["sha256"] for entry in records}
            python_payload = ("runtime/python/" +
                              python_entry.resolve(strict=True).relative_to(runtime).as_posix())
            require(packed.get("models/merlin-local.gguf") == gguf_sha256,
                    "pinned model changed between verification and ZIP assembly")
            require(packed.get("bin/llama-server") == llama_sha256,
                    "pinned inference executable changed before ZIP assembly")
            require(packed.get(python_payload) == python_sha256,
                    "pinned Python executable changed before ZIP assembly")
            manifest = {
                "schema": "merlin-linux-offline-profile/1", "archive_root": "Merlin_Studio",
                "platform": target, "model_id": "local",
                "model_protocol": "llama.cpp loopback /v1/chat/completions",
                "model_expected_sha256": gguf_sha256,
                "python_expected_sha256": python_sha256,
                "llama_expected_sha256": llama_sha256,
                "origins": {"model": model_origin, "inference": inference_origin,
                            "python": python_origin},
                # These upstream license labels are not an attestation for
                # the selected binary or the full standalone distribution.
                # The runtime may include differently licensed dependencies.
                "upstream_license_claims_unreviewed": {
                    "model_repository": "Apache-2.0",
                    "inference_source_repository": "MIT",
                    "standalone_python": "CPython and third-party notices; review required"},
                "files": sorted(records, key=lambda x: x["path"]),
                "authenticity_verified": False,
                "license_review_completed": False,
                "native_executable_started": False,
                "production_qualified": False,
                "scope": ("Reproducible source/asset assembly only. This profile requires "
                          "separate native ABI, license, startup, model, restart and "
                          "independent signing acceptance."),
            }
            entry, _ = zipinfo("OFFLINE_PROFILE_MANIFEST.json", "file")
            package.writestr(entry, (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode(),
                             compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
        checked = verify_offline(temp_name)
        require(checked["verified"], "combined ZIP failed independent integrity check")
        os.replace(temp_name, destination)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return {"status": "built_unqualified", "output": str(destination),
            "sha256": file_hash(destination, max_size=16 * 1024**3)[0],
            "bytes": destination.stat().st_size,
            "platform": target, "runtime_members": len(runtime_files),
            "verification": checked, "native_executable_started": False,
            "license_review_completed": False, "production_qualified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio-zip", type=Path, required=True)
    parser.add_argument("--python-root", type=Path, required=True)
    parser.add_argument("--python-sha256", required=True)
    parser.add_argument("--llama-server", type=Path, required=True)
    parser.add_argument("--llama-sha256", required=True)
    parser.add_argument("--gguf-model", type=Path, required=True)
    parser.add_argument("--gguf-sha256", required=True)
    parser.add_argument("--model-license", type=Path, required=True)
    parser.add_argument("--inference-license", type=Path, required=True)
    parser.add_argument("--python-license", type=Path, required=True)
    parser.add_argument("--target", choices=sorted(PLATFORMS), required=True)
    parser.add_argument("--model-origin", required=True)
    parser.add_argument("--inference-origin", required=True)
    parser.add_argument("--python-origin", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(build(**vars(args)), sort_keys=True, indent=2))
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        parser.exit(2, "Unqualified offline profile build blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
