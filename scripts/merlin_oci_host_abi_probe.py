#!/usr/bin/env python3
"""Read-only host ABI inventory for Merlin's pinned CPython 3.11 aarch64 archive.

Run with *already installed* Python (3.9+); do not install or execute the
downloaded interpreter. Only inspect allowlisted loader/library files and
their static ELF symbol definitions. Output is evidence, not authorization.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import struct
import subprocess
import sys

SCHEMA = "merlin-oci-native-host-abi-inventory/1"
SOURCE_ARCHIVE_SHA256 = "623a370be4489d8c35c7a274be02f3007a030618cda29025780beb416c6c8861"
ENTRYPOINT_SHA256 = "6cfad927461ace659b09716fad2efa828c6a4b084b7be8181c3982a9f36f464c"
REQUIREMENTS = {
    "ld-linux-aarch64.so.1": ("GLIBC_2.17",),
    "libc.so.6": ("GLIBC_2.17",),
    "libdl.so.2": ("GLIBC_2.17",),
    "libm.so.6": ("GLIBC_2.17",),
    "libpthread.so.0": ("GLIBC_2.17",),
    "librt.so.1": ("GLIBC_2.17",),
    "libutil.so.1": ("GLIBC_2.17",),
    "libgcc_s.so.1": ("GCC_3.0",),
}
OPTIONAL = {"libcrypt.so.1": ("GLIBC_2.17",)}
LOADER_PATH = "/lib/ld-linux-aarch64.so.1"
ROOTS = ("/lib/", "/lib64/", "/usr/lib/", "/usr/lib64/")
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_LDCONFIG_BYTES = 256 * 1024
MAX_READELF_BYTES = 2 * 1024 * 1024


def parse_ldconfig(stdout):
    """Accept only an exact allowlisted SONAME and absolute system library path."""
    if not isinstance(stdout, str) or len(stdout) > MAX_LDCONFIG_BYTES:
        raise ValueError("unbounded ldconfig listing")
    found = {key: [] for key in (*REQUIREMENTS, *OPTIONAL)}
    for line in stdout.splitlines():
        match = re.fullmatch(r"\s*(\S+)\s+\([^)]+\)\s+=>\s+(\S+)\s*", line)
        if match is None:
            continue
        name, candidate = match.groups()
        if (name in found and candidate.startswith(ROOTS)
                and "\x00" not in candidate and ".." not in candidate.split("/")):
            if candidate not in found[name] and len(found[name]) < 16:
                found[name].append(candidate)
    return found


def parse_version_definitions(stdout):
    """Read *provided* ELF definitions only, not a binary's version needs."""
    if not isinstance(stdout, str) or len(stdout) > MAX_READELF_BYTES:
        raise ValueError("unbounded static ELF output")
    match = re.search(r"Version definition section .*?(?=Version needs section|\Z)",
                      stdout, flags=re.DOTALL)
    if match is None:
        return set()
    return set(re.findall(r"\bName:\s*((?:GLIBC|GCC)_[0-9]+(?:\.[0-9]+){1,3})\b",
                          match.group(0)))


def _fixed_command(candidates, args, max_bytes, timeout):
    binary = next((name for name in candidates if os.path.isfile(name)
                   and os.access(name, os.X_OK)), None)
    if not binary:
        return None, "utility_missing"
    try:
        completed = subprocess.run([binary, *args], cwd="/",
                                   env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                                        "LANG": "C", "LC_ALL": "C"},
                                   stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None, "read_only_utility_failed"
    if completed.returncode != 0 or len(completed.stdout) > max_bytes:
        return None, "read_only_utility_failed_or_oversized"
    try:
        return completed.stdout.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, "read_only_utility_output_invalid"


def _elf_header(path):
    with open(path, "rb") as stream:
        header = stream.read(24)
    if len(header) < 20 or header[:4] != b"\x7fELF":
        return False
    return header[4] == 2 and header[5] == 1 and struct.unpack_from("<H", header, 18)[0] == 183


def _safe_system_path(path):
    if (not isinstance(path, str) or len(path) > 4096 or not path.startswith(ROOTS)
            or "\x00" in path or ".." in path.split("/")):
        return None, "unapproved_library_path"
    resolved = os.path.realpath(path)
    if not resolved.startswith(ROOTS):
        return None, "library_symlink_outside_system_roots"
    try:
        before = os.stat(resolved, follow_symlinks=False)
    except OSError:
        return None, "not_present_or_unreadable"
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != 0
            or before.st_mode & 0o022 or not 0 < before.st_size <= MAX_FILE_BYTES):
        return None, "unsafe_owner_type_mode_or_size"
    return (resolved, before), None


def inspect_library(path, required, readelf=True):
    """Recheck inode around bounded read; reject changed/bad host files."""
    approved, error = _safe_system_path(path)
    if error:
        return {"path": path, "observed": False, "reason": error}
    resolved, before = approved
    if not _elf_header(resolved):
        return {"path": path, "observed": False, "reason": "not_arm64_elf64_little_endian"}
    digest, total = hashlib.sha256(), 0
    try:
        with open(resolved, "rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FILE_BYTES:
                    return {"path": path, "observed": False, "reason": "library_exceeded_ceiling"}
                digest.update(chunk)
        after = os.stat(resolved, follow_symlinks=False)
    except OSError:
        return {"path": path, "observed": False, "reason": "file_read_failed"}
    if ((before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size)
            != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size)
            or total != before.st_size):
        return {"path": path, "observed": False, "reason": "library_identity_changed"}
    versions, utility_error = None, "version_definitions_not_probed"
    if readelf:
        output, utility_error = _fixed_command(("/usr/bin/readelf", "/bin/readelf"),
                                                ("-V", resolved), MAX_READELF_BYTES, 12)
        if output is not None:
            try:
                versions = sorted(parse_version_definitions(output))
                utility_error = None
            except ValueError:
                utility_error = "unbounded_version_definitions"
    matched = versions is not None and set(required).issubset(versions)
    return {"path": path, "resolved_path": resolved, "observed": True,
            "bytes": total, "sha256": digest.hexdigest(), "uid": before.st_uid,
            "mode": oct(stat.S_IMODE(before.st_mode)),
            "elf_machine": "AArch64", "defined_symbol_versions": versions,
            "required_versions": list(required), "required_versions_observed": matched,
            "version_probe_error": utility_error}


def inventory():
    listing, error = _fixed_command(("/sbin/ldconfig", "/usr/sbin/ldconfig"),
                                     ("-p",), MAX_LDCONFIG_BYTES, 8)
    cache = parse_ldconfig(listing) if listing is not None else {
        key: [] for key in (*REQUIREMENTS, *OPTIONAL)}
    findings = {}
    for name, required in {**REQUIREMENTS, **OPTIONAL}.items():
        candidates = [LOADER_PATH] if name == "ld-linux-aarch64.so.1" else cache[name]
        observations = [inspect_library(path, required) for path in candidates]
        satisfied = [o for o in observations
                     if o.get("observed") and o.get("required_versions_observed")]
        findings[name] = {"required_for_core_start": name in REQUIREMENTS,
                          "declared_symbol_versions": list(required),
                          "candidate_paths": candidates,
                          "observations": observations, "static_version_match": bool(satisfied)}
    satisfied = all(findings[name]["static_version_match"] for name in REQUIREMENTS)
    return {
        "schema": SCHEMA, "archive_sha256": SOURCE_ARCHIVE_SHA256,
        "entrypoint_sha256": ENTRYPOINT_SHA256,
        "host": {"machine": platform.machine(), "python": sys.version.split()[0],
                 "effective_uid": os.geteuid(), "glibc_reported": platform.libc_ver()},
        "ldconfig_error": error,
        "libraries": findings,
        "core_static_libraries_observed": satisfied,
        "native_interpreter_executed": False,
        "interpreter_installed": False, "model_inference_performed": False,
        "production_qualified": False, "runtime_startup_verified": False,
        "provisioning_authority": False,
        "decision": "host_static_metadata_complete_not_execution_proof"
                    if satisfied else "host_static_dependency_evidence_incomplete",
        "scope": "read-only fixed host file inventory; does not determine dynamic loader actual resolution",
    }


def main():
    result = inventory()
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    return 0  # Missing libraries are evidence, not permission to retry or repair.


if __name__ == "__main__":
    raise SystemExit(main())
