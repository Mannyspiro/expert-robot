#!/usr/bin/env python3
"""Assemble and reread-verify a complete offline CPU profile ZIP from fixed inputs.

The kit contains the original runtime, 39 wheels and ten checkpoint files.
It contains no installed environment, user prompt/history, or inferred weights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import uuid
import zipfile

import setup_cpu_candidate as setup


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return setup.digest_stream(stream)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profile = Path(__file__).resolve().parent
    source = Path(git(profile, "rev-parse", "--show-toplevel"))
    if git(source, "rev-parse", "HEAD") != args.source_commit:
        raise ValueError("source HEAD differs from explicitly supplied commit")
    source_tree = git(source, "rev-parse", args.source_commit + "^{tree}")
    if git(source, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("tracked source must be clean before kit assembly")
    relative = profile.relative_to(source)
    tracked = git(source, "ls-files", "-z", "--", str(relative)).split("\0")
    tracked = [name for name in tracked if name]
    if not 1 <= len(tracked) <= 256:
        raise ValueError("unbounded profile source closure")
    files, source_bytes = [], 0
    for name in tracked:
        path = source / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or path.resolve().is_relative_to(profile) is False:
            raise ValueError("profile source must contain only regular contained files")
        source_bytes += info.st_size
        files.append((path, "profile/" + str(path.relative_to(profile)),
                      {"path": name, "bytes": info.st_size, "sha256": digest(path)}))
    if source_bytes > 16 * 1024**2:
        raise ValueError("profile source closure exceeds 16 MiB")
    base = args.payload_root.resolve(strict=True)
    locks = setup.read_locks(base)
    for name in setup.LOCKS:
        if digest(profile / name) != setup.LOCKS[name]:
            raise ValueError("source lock differs from audited setup constants")
        path = base / name
        files.append((path, "payloads/" + name,
                      {"path": name, "bytes": path.stat().st_size, "sha256": digest(path)}))
    for lock in locks.values():
        for entry in lock["files"]:
            path = base / entry["path"]
            if not path.resolve().is_relative_to(base):
                raise ValueError("payload escaped its root")
            setup.verify_file(path, entry)
            files.append((path, "payloads/" + entry["path"], entry))
    if sum(len(lock["files"]) for lock in locks.values()) != 50:
        raise ValueError("offline kit requires all 50 original locked payloads")
    output = args.output.absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError("kit output must be new")
    partial = output.with_name(output.name + ".partial-" + uuid.uuid4().hex)
    records = []
    with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path, target, entry in files:
            name = "Merlin_Parallax_CPU/" + target
            check, count = hashlib.sha256(), 0
            with setup.open_regular(path) as incoming, archive.open(name, "w", force_zip64=True) as outgoing:
                before = os.fstat(incoming.fileno())
                for block in iter(lambda: incoming.read(4 * 1024 * 1024), b""):
                    count += len(block)
                    if count > entry["bytes"]:
                        raise ValueError("input grew while writing offline kit")
                    check.update(block)
                    outgoing.write(block)
                if (count != entry["bytes"] or check.hexdigest() != entry["sha256"]
                        or setup.stamp(before) != setup.stamp(os.fstat(incoming.fileno()))):
                    raise ValueError("kit input changed or failed complete-payload verification")
            records.append({"path": name, "bytes": count, "sha256": check.hexdigest()})
        manifest = {"schema": "merlin-parallax-offline-kit/1", "source_commit": args.source_commit,
                    "source_tree": source_tree, "locks": setup.LOCKS,
                    "locked_payloads": 50, "files": records,
                    "bootstrap": "Python3.10+ stdlib on Linux x86_64; setup then uses bundled CPython3.11.18",
                    "scope": "Experimental bounded CPU disk-weight profile; KV/activations remain in RAM."}
        raw = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
        if len(raw) > 256 * 1024:
            raise ValueError("kit manifest exceeds bound")
        archive.writestr("Merlin_Parallax_CPU/manifest.json", raw)
    with zipfile.ZipFile(partial) as archive:
        if len(archive.infolist()) != len(records) + 1:
            raise ValueError("unexpected ZIP member count")
        for entry in records:
            with archive.open(entry["path"]) as stream:
                if archive.getinfo(entry["path"]).file_size != entry["bytes"] or setup.digest_stream(stream) != entry["sha256"]:
                    raise ValueError("written ZIP member failed complete reread verification")
        if archive.read("Merlin_Parallax_CPU/manifest.json") != raw:
            raise ValueError("written manifest differs")
    kit_hash, kit_bytes = digest(partial), partial.stat().st_size
    if (git(source, "rev-parse", "HEAD") != args.source_commit
            or git(source, "status", "--porcelain", "--untracked-files=no")):
        raise ValueError("source HEAD or tracked files changed before kit publication")
    os.link(partial, output)
    partial.unlink()
    receipt = {"schema": "merlin-parallax-offline-kit-receipt/1", "success": True,
               "source_commit": args.source_commit, "source_tree": manifest["source_tree"],
               "zip_sha256": kit_hash, "zip_bytes": kit_bytes, "members": len(records) + 1,
               "manifest_sha256": hashlib.sha256(raw).hexdigest(), "locked_payloads": 50,
               "all_members_reread_hashed": True, "assembler_sha256": digest(Path(__file__))}
    setup.write_json(output.with_suffix(output.suffix + ".receipt.json"), receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
