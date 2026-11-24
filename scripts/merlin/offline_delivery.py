#!/usr/bin/env python3
"""Split/reassemble one verified offline ZIP without changing its bytes.

384 MiB raw parts leave room for ordinary GitHub artifact ZIP wrappers under
400 MiB. This is transport integrity, not model or production qualification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

PART_BYTES = 384 * 1024**2
ARTIFACT_BYTES = 400 * 1024**2
BLOCK_BYTES = 1024**2
MANIFEST = "offline-delivery-manifest.json"
SCHEMA = "merlin-offline-split-delivery/1"
EVIDENCE = frozenset({"source-pins.txt", "llama-ui-build-options.txt", "runtime-cache-exclusions.json",
    "llama-dynamic-dependencies.txt", "offline-zip-verification.json", "extracted-profile-verification.json",
    "ZIP_SHA256SUMS.txt", "native-smoke.json", "native-studio-server.log", "QUALIFICATION_SCOPE.txt",
    "studio-ui-live-trace.json"})


def require(value, message):
    if not value:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate manifest field")
        result[key] = value
    return result


def sha_ok(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def regular(path, limit):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and 0 <= info.st_size <= limit, "non-regular or oversized delivery file")
    return info


def record(path, limit):
    before = regular(path, limit)
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as source:
        while block := source.read(BLOCK_BYTES):
            count += len(block)
            require(count <= limit, "delivery file grew beyond limit")
            digest.update(block)
    after = path.lstat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            and count == before.st_size, "delivery file changed while hashing")
    return {"name": path.name, "bytes": count, "sha256": digest.hexdigest()}


def read_json(path, limit=65536):
    regular(path, limit)
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def evidence_records(directory):
    require(directory.is_dir() and not directory.is_symlink(), "regular evidence directory required")
    names = {entry.name for entry in directory.iterdir()}
    require(names in (set(EVIDENCE), set(EVIDENCE) | {MANIFEST}), "unknown or missing evidence file")
    rows = [record(directory / name, BLOCK_BYTES) for name in sorted(EVIDENCE)]
    require(sum(row["bytes"] for row in rows) <= 4 * BLOCK_BYTES, "evidence total limit")
    return rows


def split(archive, parts_dir, evidence_dir, source_commit, source_tree, *, part_bytes=PART_BYTES):
    archive, parts_dir, evidence_dir = map(Path, (archive, parts_dir, evidence_dir))
    require(all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{40}", v)
                for v in (source_commit, source_tree)), "invalid source identity")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,170}\.zip", archive.name), "invalid archive name")
    size = regular(archive, 3 * part_bytes).st_size
    require(2 * part_bytes < size <= 3 * part_bytes, "this profile requires exactly three bounded parts")
    require(not parts_dir.exists() and not parts_dir.is_symlink(), "parts directory must be new")
    manifest_path = evidence_dir / MANIFEST
    require(not manifest_path.exists() and not manifest_path.is_symlink(), "manifest already exists")
    evidence = evidence_records(evidence_dir)
    native = read_json(evidence_dir / "native-smoke.json", 16385)
    live = read_json(evidence_dir / "studio-ui-live-trace.json", 65537)
    require(native.get("result") == "pass" and live.get("result") == "pass"
            and live.get("source_commit") == source_commit and live.get("source_tree") == source_tree,
            "native acceptance and actual stream must pass before splitting")
    checksum = (evidence_dir / "ZIP_SHA256SUMS.txt").read_text().split()
    require(len(checksum) == 2 and sha_ok(checksum[0]) and Path(checksum[1]).name == archive.name,
            "missing original verified ZIP digest")
    parts_dir.mkdir(mode=0o700)
    published_manifest = False
    try:
        parts = []
        full_hash = hashlib.sha256()
        with archive.open("rb") as source:
            for index in range(1, 4):
                target = parts_dir / (archive.name + f".part-{index:03d}")
                digest, count = hashlib.sha256(), 0
                with target.open("xb") as output:
                    while count < part_bytes:
                        block = source.read(min(BLOCK_BYTES, part_bytes - count))
                        if not block:
                            break
                        output.write(block)
                        digest.update(block)
                        full_hash.update(block)
                        count += len(block)
                parts.append({"name": target.name, "bytes": count, "sha256": digest.hexdigest()})
            require(not source.read(1) and sum(row["bytes"] for row in parts) == size,
                    "original ZIP size changed during splitting")
        require(full_hash.hexdigest() == checksum[0], "original verified ZIP changed during splitting")
        manifest = {"schema": SCHEMA, "source_commit": source_commit, "source_tree": source_tree,
                    "archive": {"name": archive.name, "bytes": size, "sha256": full_hash.hexdigest()},
                    "part_bytes_limit": part_bytes, "artifact_bytes_limit": ARTIFACT_BYTES,
                    "parts": parts, "evidence": evidence,
                    "scope": "Transport integrity only; retain the full offline-profile and native acceptance evidence."}
        raw = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
        require(len(raw) <= 65536, "manifest size limit")
        with manifest_path.open("xb") as output:
            published_manifest = True
            output.write(raw)
        return manifest
    except BaseException:
        shutil.rmtree(parts_dir)
        if published_manifest:
            manifest_path.unlink(missing_ok=True)
        raise


def assemble(manifest_path, parts_dir, output, *, part_bytes=PART_BYTES):
    manifest_path, parts_dir, output = map(Path, (manifest_path, parts_dir, output))
    value = read_json(manifest_path)
    require(value.get("schema") == SCHEMA and value.get("part_bytes_limit") == part_bytes
            and value.get("artifact_bytes_limit") == ARTIFACT_BYTES, "unsupported delivery manifest")
    require(all(isinstance(value.get(key), str) and re.fullmatch(r"[0-9a-f]{40}", value[key])
                for key in ("source_commit", "source_tree")), "invalid manifest source identity")
    archive = value.get("archive", {})
    require(isinstance(archive, dict) and isinstance(archive.get("name"), str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,170}\.zip", archive["name"])
            and type(archive.get("bytes")) is int and 2 * part_bytes < archive["bytes"] <= 3 * part_bytes
            and sha_ok(archive.get("sha256")), "invalid archive record")
    parts = value.get("parts")
    require(isinstance(parts, list) and len(parts) == 3, "exactly three parts required")
    for index, row in enumerate(parts, 1):
        require(isinstance(row, dict) and set(row) == {"name", "bytes", "sha256"}
                and row.get("name") == archive["name"] + f".part-{index:03d}"
                and type(row.get("bytes")) is int and 0 < row["bytes"] <= part_bytes
                and (index == 3 or row["bytes"] == part_bytes) and sha_ok(row.get("sha256")),
                "invalid part identity, size or digest")
    require(sum(row["bytes"] for row in parts) == archive["bytes"], "part total differs from archive")
    require(evidence_records(manifest_path.parent) == value.get("evidence"), "delivery evidence changed")
    require(parts_dir.is_dir() and not parts_dir.is_symlink(), "regular parts directory required")
    require({entry.name for entry in parts_dir.iterdir()} == {row["name"] for row in parts},
            "missing or unknown delivery part")
    require(not output.exists() and not output.is_symlink(), "output must be new")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".merlin-reassembly-", dir=output.parent)
    temporary = Path(temporary)
    try:
        full_hash = hashlib.sha256()
        with os.fdopen(descriptor, "wb") as destination:
            for row in parts:
                source_path = parts_dir / row["name"]
                require(regular(source_path, part_bytes).st_size == row["bytes"], "part size differs")
                digest, count = hashlib.sha256(), 0
                with source_path.open("rb") as source:
                    while block := source.read(BLOCK_BYTES):
                        count += len(block)
                        require(count <= row["bytes"], "part grew during reassembly")
                        digest.update(block)
                        full_hash.update(block)
                        destination.write(block)
                require(count == row["bytes"] and digest.hexdigest() == row["sha256"], "part digest differs")
        require(full_hash.hexdigest() == archive["sha256"], "full ZIP digest differs")
        os.link(temporary, output)  # Atomic no-overwrite publication on the same filesystem.
    finally:
        temporary.unlink(missing_ok=True)
    return {"verified": True, "bytes": archive["bytes"], "sha256": archive["sha256"],
            "output": str(output), "application_executed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("split")
    for name in ("archive", "parts-dir", "evidence-dir", "source-commit", "source-tree"):
        create.add_argument("--" + name, required=True)
    join = commands.add_parser("assemble")
    for name in ("manifest", "parts-dir", "output"):
        join.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if args.command == "split":
        result = split(args.archive, args.parts_dir, args.evidence_dir, args.source_commit, args.source_tree)
    else:
        result = assemble(args.manifest, args.parts_dir, args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
