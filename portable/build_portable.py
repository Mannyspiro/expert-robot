#!/usr/bin/env python3
"""Build an allowlisted, deterministic Merlin Studio ZIP without user state.

Reproducibility is for identical input bytes, Python/zlib, and (when requested)
the same native compiler/toolchain. No dependencies or model weights are fetched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import struct
import subprocess
import tempfile
import zipfile

REPO = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = "Merlin_Studio"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
APP_FILES = (
    "engine.py", "model.py", "public_web.py", "server.py", "storage.py", "tools.py", "worker.py", "security_review.py",
    "web/index.html", "START.sh", "START.bat", "START.command", "README.md", "MODEL_SETUP.md",
    "models/README.md", "bin/README.md", "tests/test_studio.py", "tests/test_security_review.py",
)
CORE_MODULES = (
    "merlin/__init__.py", "merlin/artifact_ref.py", "merlin/project_registry.py",
    "orchestrator.py", "experimental_self_healing.py", "experimental_fault_advisory.py",
    "runtime_supervisor.py",
)
CPP_FILES = (
    "include/expert_robot/protocol.hpp", "include/expert_robot/runtime.hpp",
    "src/runtime.cpp", "src/main.cpp",
)
EXECUTABLES = {"START.sh", "START.command", "VERIFY.py", "bin/expert_robot_runtime"}


def source_bytes(relative: str) -> bytes:
    path = REPO / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or non-regular source: " + relative)
    path.resolve().relative_to(REPO.resolve())
    return path.read_bytes()


def collect_sources() -> tuple[dict[str, bytes], dict[str, str]]:
    payload: dict[str, bytes] = {}
    origins: dict[str, str] = {}
    mappings = [(name, "portable/merlin_studio/" + name) for name in APP_FILES]
    mappings += [("core/python/" + name, "python/" + name) for name in CORE_MODULES]
    mappings += [("core/cpp/" + name, "cpp/" + name) for name in CPP_FILES]
    mappings += [("VERIFY.py", "scripts/verify_portable.py")]
    for destination, origin in mappings:
        payload[destination] = source_bytes(origin)
        origins[destination] = origin
    # Explicit paths are intentional: globbing this directory would pick up state,
    # models, environments, credentials, user files, or old build products.
    return payload, origins


def native_protocol(payload: dict[str, bytes]) -> tuple[bytes, dict]:
    if platform.system() != "Linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        raise ValueError("--include-native supports a Linux x86_64 build host only; use the source-only ZIP elsewhere")
    compiler = shutil.which("g++")
    if not compiler:
        raise ValueError("--include-native requires g++; the source-only package does not")
    flags = ["-std=c++20", "-O2", "-DNDEBUG", "-fno-ident", "-Wl,--build-id=none"]
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C"}
    version = subprocess.run([compiler, "--version"], capture_output=True, text=True,
                             check=True, timeout=15, env=environment).stdout.splitlines()[0]
    with tempfile.TemporaryDirectory(prefix="merlin-native-") as folder:
        root = Path(folder)
        for name in CPP_FILES:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload["core/cpp/" + name])
        output = root / "expert_robot_runtime"
        command = [compiler, *flags, "-ffile-prefix-map=" + str(root) + "=.",
                   "-I", "include", "src/runtime.cpp", "src/main.cpp", "-o", str(output)]
        result = subprocess.run(command, cwd=root, env=environment, capture_output=True,
                                text=True, timeout=120)
        if result.returncode:
            raise RuntimeError("Native protocol compilation failed: " + result.stderr[-4000:])
        binary = output.read_bytes()
        if binary[:5] != b"\x7fELF\x02" or binary[5] != 1 or struct.unpack("<H", binary[18:20])[0] != 62:
            raise ValueError("Compiler output is not a little-endian Linux x86_64 ELF executable")
        probes = [{"id": "package-health", "role": "health", "task": "check"},
                  {"id": "package-scope", "role": "controller", "task": "check"}]
        checked = subprocess.run([str(output)], input="".join(json.dumps(p) + "\n" for p in probes),
                                 capture_output=True, text=True, timeout=5, check=True, env=environment)
        replies = [json.loads(line) for line in checked.stdout.splitlines()]
        if (len(replies) != 2 or replies[0].get("id") != probes[0]["id"]
                or replies[0].get("ok") is not True
                or replies[0].get("result") != "runtime protocol healthy"
                or replies[1].get("id") != probes[1]["id"]
                or replies[1].get("ok") is not False
                or "does not own model state" not in replies[1].get("error", "")):
            raise ValueError("Compiled core failed its health and model-ownership reference checks")
    return binary, {"included": True, "platform": "linux-x86_64", "scope": "jsonl_protocol_health_only",
                    "compiler": version, "compiler_flags": [*flags, "-ffile-prefix-map=<build>=."],
                    "build_libc": list(platform.libc_ver()), "reference_checks": 2,
                    "runtime_requirement": "compatible Linux x86_64 system libraries; not a universal binary"}


def build(output: Path, include_native: bool = False) -> dict:
    payload, origins = collect_sources()
    native = {"included": False, "scope": "protocol_source_only", "platform": None}
    if include_native:
        payload["bin/expert_robot_runtime"], native = native_protocol(payload)
        origins["bin/expert_robot_runtime"] = "compiled from included core/cpp protocol sources"
    records = []
    for name in sorted(payload):
        p = PurePosixPath(name)
        if p.is_absolute() or ".." in p.parts or "\\" in name:
            raise ValueError("Unsafe archive path: " + name)
        records.append({"path": name, "bytes": len(payload[name]),
                        "sha256": hashlib.sha256(payload[name]).hexdigest(),
                        "mode": "0755" if name in EXECUTABLES else "0644", "source": origins[name]})
    manifest = {"schema": "merlin-studio-portable/1", "version": "0.2.0", "archive_root": ARCHIVE_ROOT,
                "python_requirement": ">=3.10", "native_protocol": native,
                "contains_model_weights": False, "contains_python_runtime": False,
                "contains_inference_engine": False, "contains_user_state": False,
                "zip_timestamp": "1980-01-01T00:00:00", "files": records,
                "integrity_scope": "File hashes detect changed bytes; this manifest is not a signature or capability qualification."}
    payload["PACKAGE_MANIFEST.json"] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    output = Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".merlin-package-", suffix=".zip", dir=output.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(payload):
                entry = zipfile.ZipInfo(ARCHIVE_ROOT + "/" + name, date_time=ZIP_TIME)
                entry.create_system = 3
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = (stat.S_IFREG | (0o755 if name in EXECUTABLES else 0o644)) << 16
                entry.flag_bits |= 0x800
                archive.writestr(entry, payload[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return {"output": str(output), "sha256": digest, "bytes": output.stat().st_size,
            "files": len(payload), "native_protocol": native,
            "state_included": False, "model_weights_included": False, "python_runtime_included": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="ZIP file to create")
    parser.add_argument("--include-native", action="store_true", help="Compile and include the Linux x86_64 protocol-health core")
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output, args.include_native), sort_keys=True, indent=2))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, "Package build failed: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
