#!/usr/bin/env python3
"""Acquire immutable public model/wheel files, checking every complete payload.

No code is imported from acquired files. A lock specifies exact HTTPS URLs,
byte lengths and SHA-256 hashes. Failed partial files are retained as evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import time
import urllib.parse
import urllib.request
import uuid


def validate_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    permitted = host in {
        "huggingface.co", "files.pythonhosted.org", "download.pytorch.org",
        "download-r2.pytorch.org", "github.com", "release-assets.githubusercontent.com",
        "objects.githubusercontent.com",
    } or host.endswith(".hf.co")
    if parsed.scheme != "https" or not permitted or parsed.username or parsed.password:
        raise ValueError("download URL outside the public source allowlist")


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def digest_file(path: Path, expected_size: int) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size != expected_size:
        raise ValueError("existing payload is not a regular file of the locked size")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def acquire(entry: dict, root: Path, opener) -> dict:
    relative = PurePosixPath(entry["path"])
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("unsafe locked path")
    size, wanted = entry["bytes"], entry["sha256"]
    if not isinstance(size, int) or not 0 < size <= 2_000_000_000:
        raise ValueError("payload size outside the 2 GB acquisition bound")
    if not re.fullmatch(r"[0-9a-f]{64}", wanted):
        raise ValueError("invalid locked SHA-256")
    validate_url(entry["url"])
    target = root.joinpath(*relative.parts)
    if root.resolve() not in target.parent.resolve().parents and target.parent.resolve() != root.resolve():
        raise ValueError("locked path escaped the destination")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.exists() or target.is_symlink():
        actual = digest_file(target, size)
        if actual != wanted:
            raise ValueError("existing payload hash mismatch")
        return {"path": str(relative), "bytes": size, "sha256": actual, "cached": True}
    partial = target.with_name(target.name + ".partial-" + uuid.uuid4().hex)
    started = time.monotonic()
    digest, count, next_notice = hashlib.sha256(), 0, 128 * 1024 * 1024
    request = urllib.request.Request(entry["url"], headers={"User-Agent": "Merlin-pinned-candidate/1", "Accept-Encoding": "identity"})
    with opener.open(request, timeout=30) as response, partial.open("xb") as output:
        validate_url(response.geturl())
        declared = response.headers.get("Content-Length")
        if response.status != 200 or (declared is not None and int(declared) != size):
            raise ValueError("unexpected payload status or declared size")
        while True:
            if time.monotonic() - started > 1800:
                raise TimeoutError("payload exceeded 30-minute acquisition deadline")
            block = response.read(min(4 * 1024 * 1024, size - count + 1))
            if not block:
                break
            count += len(block)
            if count > size:
                raise ValueError("payload exceeded locked size")
            digest.update(block)
            output.write(block)
            if count >= next_notice:
                print(json.dumps({"file": str(relative), "received_bytes": count}), flush=True)
                next_notice += 128 * 1024 * 1024
        output.flush()
        os.fsync(output.fileno())
    actual = digest.hexdigest()
    if count != size or actual != wanted:
        raise ValueError("complete payload size or SHA-256 mismatch")
    partial.chmod(0o444)
    os.link(partial, target)
    partial.unlink()
    return {"path": str(relative), "bytes": count, "sha256": actual, "cached": False, "download_seconds": round(time.monotonic() - started, 3)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    raw = args.lock.read_bytes()
    lock = json.loads(raw)
    if lock.get("schema") != "merlin-public-payload-lock-v1" or len(lock["files"]) > 80:
        raise ValueError("unsupported or unbounded lock")
    args.root.mkdir(mode=0o700, parents=True, exist_ok=True)
    result = {"schema": "merlin-acquisition-receipt-v1", "lock_sha256": hashlib.sha256(raw).hexdigest(), "files": [], "success": False}
    opener = urllib.request.build_opener(HTTPSRedirect())
    try:
        for entry in lock["files"]:
            row = acquire(entry, args.root, opener)
            result["files"].append(row)
            print(json.dumps(row), flush=True)
        result["success"] = True
        return 0
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        print(json.dumps({"success": False, "error_type": type(exc).__name__}), flush=True)
        return 1
    finally:
        with args.receipt.open("x") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
