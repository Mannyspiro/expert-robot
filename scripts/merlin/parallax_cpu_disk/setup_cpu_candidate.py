#!/usr/bin/env python3
"""Create the pinned Linux x86_64 CPU environment from already acquired files.

This installer is offline. It never downloads packages or runs model inference.
All original runtime/model/wheel payloads are hashed before executing new code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import stat
import subprocess
import sys
import tarfile


LOCKS = {
    "checkpoint-lock.json": "bc21d1390c2c68001aa4c1ad2e2a72441b4a82125bdc0d2ffde8f98ef801deb5",
    "wheel-lock.json": "a3ff9c700b1bde73972b5b9f9cad0e6d62e541291fc6e14f748a79c21ea83412",
    "runtime-lock.json": "7b9fd39db58b1dc86ed9b7e1513adbef769d0216ee6ccbaa221bb4454ec8e917",
}
MAX_RUNTIME_FILES = 12000
MAX_RUNTIME_BYTES = 2 * 1024**3


def digest_stream(stream) -> str:
    result = hashlib.sha256()
    for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
        result.update(block)
    return result.hexdigest()


def stamp(info) -> tuple:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def open_regular(path: Path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise ValueError("locked payload is not a regular file")
    return os.fdopen(fd, "rb")


def verify_file(path: Path, entry: dict) -> dict:
    with open_regular(path) as source:
        initial = os.fstat(source.fileno())
        if initial.st_size != entry["bytes"] or digest_stream(source) != entry["sha256"]:
            raise ValueError("locked payload size or SHA-256 mismatch")
        if stamp(initial) != stamp(os.fstat(source.fileno())):
            raise ValueError("locked payload changed while being verified")
    return {"path": entry["path"], "bytes": entry["bytes"], "sha256": entry["sha256"]}


def read_locks(root: Path) -> dict:
    result = {}
    for filename, expected in LOCKS.items():
        raw = (root / filename).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("input lock differs from the audited candidate")
        lock = json.loads(raw)
        if lock["schema"] != "merlin-public-payload-lock-v1" or not 1 <= len(lock["files"]) <= 80:
            raise ValueError("invalid payload lock")
        result[filename] = lock
    return result


def safe_extract_runtime(archive: Path, destination: Path, entry: dict) -> dict:
    """Validate archive paths first, then extract files before contained symlinks."""
    records, excluded = [], []
    with open_regular(archive) as raw:
        before = os.fstat(raw.fileno())
        if before.st_size != entry["bytes"] or digest_stream(raw) != entry["sha256"]:
            raise ValueError("runtime archive integrity failure")
        raw.seek(0)
        with tarfile.open(fileobj=raw, mode="r:gz") as source:
            members = source.getmembers()
            if len(members) > MAX_RUNTIME_FILES:
                raise ValueError("runtime archive has too many members")
            names, symlinks, total = set(), set(), 0
            for member in members:
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts or len(name.parts) < 2 or name.parts[0] != "python":
                    raise ValueError("runtime archive path escapes python root")
                if str(name) in names or not (member.isfile() or member.issym() or member.isdir()):
                    raise ValueError("duplicate or unsupported runtime member")
                names.add(str(name))
                if member.isfile():
                    total += member.size
                    if member.size < 0 or total > MAX_RUNTIME_BYTES:
                        raise ValueError("runtime exceeds bounded uncompressed size")
                if member.issym():
                    symlinks.add(str(name))
                    target = PurePosixPath(member.linkname)
                    parts = list(name.parent.parts)
                    if target.is_absolute():
                        raise ValueError("absolute runtime symlink")
                    for part in target.parts:
                        if part == "..":
                            if len(parts) <= 1:
                                raise ValueError("runtime symlink escapes python root")
                            parts.pop()
                        elif part != ".":
                            parts.append(part)
                    if not parts or parts[0] != "python":
                        raise ValueError("runtime symlink escapes python root")
            for member in members:
                if any(str(parent) in symlinks for parent in PurePosixPath(member.name).parents):
                    raise ValueError("archive member descends through a symlink")
            destination.mkdir(mode=0o700)
            for member in members:
                name = PurePosixPath(member.name)
                if "__pycache__" in name.parts:
                    if member.isdir():
                        continue
                    if not member.isfile() or not member.name.endswith(".pyc"):
                        raise ValueError("unexpected runtime bytecode-cache member")
                    with source.extractfile(member) as data:
                        excluded.append({"path": member.name, "bytes": member.size, "sha256": digest_stream(data)})
                    continue
                path = destination.joinpath(*name.parts)
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True, mode=0o755)
                    continue
                if member.issym():
                    continue
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                digest, count = hashlib.sha256(), 0
                with source.extractfile(member) as data, path.open("xb") as output:
                    for block in iter(lambda: data.read(1024 * 1024), b""):
                        count += len(block)
                        if count > member.size:
                            raise ValueError("runtime member exceeds declared size")
                        output.write(block)
                        digest.update(block)
                if count != member.size:
                    raise ValueError("truncated runtime member")
                path.chmod(0o755 if member.mode & 0o111 else 0o644)
                records.append({"path": member.name, "bytes": count, "sha256": digest.hexdigest(), "executable": bool(member.mode & 0o111)})
            for member in members:
                if not member.issym():
                    continue
                path = destination.joinpath(*PurePosixPath(member.name).parts)
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                path.symlink_to(member.linkname)
                records.append({"path": member.name, "symlink_target": member.linkname})
            for member in members:
                if member.issym():
                    target = (destination / member.name).resolve(strict=True)
                    if (destination / "python").resolve() not in target.parents:
                        raise ValueError("runtime symlink resolves outside python root")
        if stamp(before) != stamp(os.fstat(raw.fileno())):
            raise ValueError("runtime archive changed during extraction")
    return {"retained_members": len(records), "records": records, "excluded_bytecode": excluded,
            "source_and_notices_preserved": True, "archive_sha256": entry["sha256"]}


def write_json(path: Path, value) -> None:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    with path.open("x") as output:
        output.write(raw)


def clean_environment(destination: Path) -> dict:
    for child in ("home", "tmp", "hf-home"):
        (destination / child).mkdir(mode=0o700)
    return {"PATH": "/usr/bin:/bin", "HOME": str(destination / "home"), "TMPDIR": str(destination / "tmp"),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
            "PIP_CONFIG_FILE": "/dev/null", "PIP_DISABLE_PIP_VERSION_CHECK": "1", "HF_HOME": str(destination / "hf-home"),
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
            "HF_HUB_DISABLE_XET": "1", "TOKENIZERS_PARALLELISM": "false", "CUDA_VISIBLE_DEVICES": "",
            "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"}


def run_checked(argv: list[str], environment: dict, log: Path, timeout: int = 180) -> str:
    with log.open("x") as output:
        result = subprocess.run(argv, env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError("offline setup command failed; inspect " + log.name)
    return log.read_text()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--runtime-archive", type=Path, help="Optional existing exact archive; still requires the fixed size/hash")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise ValueError("candidate supports Linux x86_64 only")
    root = args.payload_root.resolve(strict=True)
    locks = read_locks(root)
    runtime = locks["runtime-lock.json"]["files"][0]
    archive = args.runtime_archive or root / runtime["path"]
    verified = []
    for filename, lock in locks.items():
        for entry in lock["files"]:
            path = archive if filename == "runtime-lock.json" else root / entry["path"]
            verified.append(verify_file(path, entry))
    if args.verify_only:
        print(json.dumps({"success": True, "verified_payloads": len(verified), "bytes": sum(x["bytes"] for x in verified)}))
        return 0
    if args.destination is None:
        parser.error("--destination is required unless --verify-only is selected")
    destination = args.destination.absolute()
    destination.mkdir(mode=0o700, parents=False)  # Never overwrite another installation.
    report = {"schema": "merlin-parallax-offline-setup-v1", "success": False, "stage": "extract_runtime",
              "payload_root": str(root), "locks": LOCKS, "verified_payloads": verified, "model_inference_run": False}
    try:
        inventory = safe_extract_runtime(archive, destination / "runtime", runtime)
        write_json(destination / "runtime-inventory.json", inventory)
        report["runtime_retained_members"] = inventory["retained_members"]
        report["runtime_excluded_bytecode_files"] = len(inventory["excluded_bytecode"])
        environment = clean_environment(destination)
        interpreter = destination / "runtime/python/bin/python3"
        report["stage"] = "runtime_smoke"
        smoke = "import sys,ssl,sqlite3,hashlib,http.server,json,zlib; assert sys.version_info[:3]==(3,11,18); print(json.dumps({'version':sys.version,'abi':sys.implementation.cache_tag,'ssl':ssl.OPENSSL_VERSION}))"
        report["runtime"] = json.loads(run_checked([str(interpreter), "-I", "-B", "-S", "-c", smoke], environment, destination / "runtime-smoke.log"))
        report["stage"] = "create_venv"
        run_checked([str(interpreter), "-I", "-B", "-m", "venv", "--copies", str(destination / "venv")], environment, destination / "venv-create.log")
        python = str(destination / "venv/bin/python")
        wheels = locks["wheel-lock.json"]["files"]
        requirements = "".join(x["name"] + "==" + x["version"] + " --hash=sha256:" + x["sha256"] + "\n" for x in wheels)
        (destination / "requirements.lock").write_text(requirements)
        report["stage"] = "offline_wheel_install"
        run_checked([python, "-I", "-B", "-m", "pip", "install", "--no-index", "--no-cache-dir", "--no-compile", "--only-binary=:all:", "--require-hashes", "--find-links", str(root / "wheelhouse"), "-r", str(destination / "requirements.lock")], environment, destination / "offline-install.log", 300)
        run_checked([python, "-I", "-B", "-m", "pip", "check"], environment, destination / "pip-check.log")
        report["stage"] = "cpu_import_smoke"
        smoke = "import torch,transformers,accelerate,tokenizers,json; torch.set_num_threads(2); assert torch.__version__=='2.9.1+cpu'; assert not torch.cuda.is_available(); assert transformers.__version__=='5.6.2'; assert accelerate.__version__=='1.16.0'; assert tokenizers.__version__=='0.22.2'; print(json.dumps({'torch':torch.__version__,'transformers':transformers.__version__,'accelerate':accelerate.__version__,'tokenizers':tokenizers.__version__,'threads':torch.get_num_threads()}))"
        report["imports"] = json.loads(run_checked([python, "-I", "-B", "-c", smoke], environment, destination / "cpu-import-smoke.log"))
        if any((destination / "runtime").rglob("__pycache__")):
            raise ValueError("setup wrote caches into the verified base runtime")
        report["python"] = python
        report["checkpoint"] = str(root / "checkpoint")
        report["stage"], report["success"] = "complete", True
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)[:500]}
    finally:
        report["logs"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in destination.glob("*.log")}
        write_json(destination / "setup-receipt.json", report)
        print(json.dumps({"success": report["success"], "stage": report["stage"], "receipt": str(destination / "setup-receipt.json")}))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
