"""Bounded Linux compatibility checks; no model load or hardware activation.

The default API reads files only. A caller may explicitly request one bounded
``llama-server --version`` probe after its hash and CPU requirements pass.
Compatibility is not model readiness, physical-memory capacity, or GPU support.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import selectors
import signal
import stat
import struct
import subprocess
import sys
import time

SCHEMA = "merlin-linux-preflight/1"
REQUIREMENTS_SCHEMA = "merlin-linux-runtime-requirements/1"
PLATFORMS = {"linux-x86_64": 62, "linux-aarch64": 183}
CPU_BASELINES = {
    "linux-x86_64": ("x86_64-avx2", ["avx", "avx2", "bmi2", "f16c", "fma", "sse4_2"]),
    "linux-aarch64": ("armv8-a", ["asimd"]),
}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _read(path, limit):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 <= info.st_size <= limit:
            raise ValueError("non-regular or oversized input")
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("input grew beyond limit")
    return raw


def _host_platform():
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    return platform.system().lower() + "-" + machine


def _cpu_features():
    # procfs reports size zero, so bound the read itself. Require the features
    # on every reported processor rather than selecting the strongest core.
    with open("/proc/cpuinfo", "rb") as source:
        raw = source.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("CPU information limit")
    rows = []
    for line in raw.decode("ascii", "strict").splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip().lower() in {"flags", "features"}:
            rows.append(set(value.strip().lower().split()))
    if not rows:
        raise ValueError("CPU features unavailable")
    return set.intersection(*rows)


def _elf(path, root, *, symlink=False):
    if not symlink and path.is_symlink():
        raise ValueError("executable symlink rejected")
    resolved = path.resolve(strict=True)
    resolved.relative_to(root.resolve(strict=True))
    info = resolved.stat()
    if not stat.S_ISREG(info.st_mode) or not 20 <= info.st_size <= 512 * 1024**2:
        raise ValueError("invalid executable")
    if not os.access(resolved, os.X_OK):
        raise ValueError("executable permission missing")
    with resolved.open("rb") as source:
        head = source.read(20)
    if head[:6] != b"\x7fELF\x02\x01":
        raise ValueError("ELF64 little-endian required")
    return resolved, struct.unpack("<H", head[18:20])[0]


def _sha256(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            size += len(block)
            if size > 512 * 1024**2:
                raise ValueError("executable grew beyond bound")
            digest.update(block)
    return digest.hexdigest()


def _version_probe(executable, root, timeout=5):
    """No model argument; bounded output, wall time, and child process group."""
    output = bytearray()
    reason = None
    process = None
    try:
        process = subprocess.Popen(
            [str(executable), "--version"], cwd=str(root),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={"PATH": os.defpath, "HOME": str(root), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
            start_new_session=True)
        deadline = time.monotonic() + timeout
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            eof = False
            while not eof:
                if time.monotonic() >= deadline:
                    reason = "version_probe_timeout"
                    break
                for key, _ in selector.select(min(0.1, deadline - time.monotonic())):
                    chunk = os.read(key.fd, min(4096, 16385 - len(output)))
                    if not chunk:
                        eof = True
                        break
                    output.extend(chunk)
                    if len(output) > 16384:
                        reason = "version_probe_output_limit"
                        break
                if reason:
                    break
            if reason is None:
                process.wait(timeout=max(0.01, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        reason = "version_probe_timeout"
    except OSError:
        reason = "version_probe_launch_failed"
    finally:
        if process is not None:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2)
            if process.stdout is not None:
                process.stdout.close()
    code = process.returncode if process is not None else None
    return {"probe_performed": True, "compatible": reason is None and code == 0,
            "returncode": code, "reason": reason or ("version_probe_passed" if code == 0 else "version_probe_failed"),
            "output_bytes": len(output), "output_sha256": hashlib.sha256(output).hexdigest(),
            "model_loaded": False, "timeout_seconds": timeout}


def check_linux_host(root, *, data_dir=None, probe_binary=False, verify_executables=False):
    """Return compatibility facts; default never spawns or writes anything."""
    root = Path(root)
    report = {"schema": SCHEMA, "status": "not_applicable", "profile_present": False,
              "target_platform": None, "host_platform": _host_platform(),
              "runtime_compatible": None, "engine_compatible": None,
              "checks": [], "cpu": {"required": [], "missing": []},
              "abi": {"probe_performed": False, "compatible": None, "model_loaded": False},
              "integrity": {"executable_digests_checked": False, "executable_digests_match": None},
              "model_ready": None, "memory_capacity_qualified": False,
              "gpu_execution_qualified": False}

    def check(identifier, passed, detail):
        report["checks"].append({"id": identifier, "status": "pass" if passed else "blocked", "detail": detail})
        return passed

    manifest_path = root / "OFFLINE_PROFILE_MANIFEST.json"
    if not manifest_path.exists() and not manifest_path.is_symlink():
        return report
    report["profile_present"] = True
    report["status"] = "blocked"
    report["runtime_compatible"] = False
    report["engine_compatible"] = False
    try:
        manifest = json.loads(_read(manifest_path, 1024 * 1024), object_pairs_hook=_unique)
        if not isinstance(manifest, dict):
            raise ValueError("profile must be an object")
        target = manifest.get("platform")
        if manifest.get("schema") != "merlin-linux-offline-profile/1" or target not in PLATFORMS:
            raise ValueError("unsupported profile")
        report["target_platform"] = target
        marker = _read(root / "OFFLINE_PLATFORM", 32)
        if not check("platform_marker", marker == (target + "\n").encode(), "Package platform marker must match its manifest."):
            return report
        if not check("host_platform", report["host_platform"] == target, "Use the package matching this Linux CPU architecture."):
            return report
        python, machine = _elf(root / "runtime/python/bin/python3", root / "runtime/python", symlink=True)
        if not check("python_elf", machine == PLATFORMS[target], "Bundled Python must be an executable for the declared architecture."):
            return report
        report["runtime_compatible"] = True
        executable, machine = _elf(root / "bin/llama-server", root)
        if not check("engine_elf", machine == PLATFORMS[target], "Bundled inference engine must match the declared architecture."):
            return report
        requirements = manifest.get("runtime_requirements")
        baseline, features = CPU_BASELINES[target]
        valid = (isinstance(requirements, dict)
                 and len(json.dumps(requirements)) <= 8192
                 and requirements.get("schema") == REQUIREMENTS_SCHEMA
                 and requirements.get("platform") == target
                 and requirements.get("cpu_baseline") == baseline
                 and requirements.get("cpu_features") == features
                 and all(isinstance(manifest.get(field), str)
                         and re.fullmatch(r"[0-9a-f]{64}", manifest[field])
                         for field in ("llama_expected_sha256", "python_expected_sha256"))
                 and isinstance(requirements.get("system_libraries"), list)
                 and len(requirements["system_libraries"]) <= 32
                 and all(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_.+-]{1,100}", name)
                         for name in requirements["system_libraries"])
                 and requirements.get("engine_sha256") == manifest.get("llama_expected_sha256")
                 and requirements.get("python_sha256") == manifest.get("python_expected_sha256"))
        if not check("declared_requirements", valid, "Explicit pinned CPU and runtime requirements are required for this profile."):
            return report
        report["cpu"]["required"] = features
        report["abi"]["required_system_libraries"] = requirements.get("system_libraries", [])
        present = _cpu_features()
        report["cpu"]["missing"] = sorted(set(features) - present)
        if not check("cpu_features", not report["cpu"]["missing"], "Every visible processor must support the package CPU baseline."):
            return report
        if data_dir is not None:
            destination = Path(data_dir)
            while not destination.exists() and destination.parent != destination:
                destination = destination.parent
            if not check("state_directory", destination.is_dir() and os.access(destination, os.W_OK | os.X_OK),
                         "The state directory or its existing parent must be writable; startup verifies actual creation."):
                return report
        report["engine_compatible"] = True
        if verify_executables or probe_binary:
            # Hash before any binary execution. The read-only status path avoids
            # repeatedly hashing tens of megabytes or spawning a child process.
            matched = (_sha256(executable) == manifest["llama_expected_sha256"]
                       and _sha256(python) == manifest["python_expected_sha256"])
            report["integrity"] = {"executable_digests_checked": True, "executable_digests_match": matched}
            if not check("executable_hashes", matched,
                         "Bundled executable bytes must match the profile before the ABI probe."):
                report["engine_compatible"] = False
                return report
        if probe_binary:
            report["abi"].update(_version_probe(executable, root))
            report["engine_compatible"] = report["abi"]["compatible"]
            if not check("runtime_abi", report["engine_compatible"],
                         "The bounded engine version probe checks loader, shared-library and CPU startup; no model is loaded."):
                return report
        report["status"] = "pass"
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, RuntimeError):
        # A late read/hash failure must revoke any earlier static compatibility
        # result. Callers must never interpret partial evidence as launch-ready.
        report["status"] = "blocked"
        report["engine_compatible"] = False
        check("input_read", False, "Required compatibility metadata or native files are missing, invalid, or unreadable.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--probe-binary", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--startup", action="store_true", help=argparse.SUPPRESS)
    args, unknown = parser.parse_known_args()
    if unknown and not args.startup:
        parser.error("unknown arguments")
    state = args.data_dir or Path(os.environ.get("MERLIN_DATA_DIR", str(args.root / "data")))
    report = check_linux_host(args.root, data_dir=state, probe_binary=args.probe_binary)
    if not args.quiet:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    elif report["status"] == "blocked":
        failed = [item["id"] for item in report["checks"] if item["status"] == "blocked"]
        print("Merlin Linux compatibility check: " + ", ".join(failed) + ". Run sh START.sh --check for details.", file=sys.stderr)
    raise SystemExit(1 if report["status"] == "blocked" else 0)


if __name__ == "__main__":
    main()
