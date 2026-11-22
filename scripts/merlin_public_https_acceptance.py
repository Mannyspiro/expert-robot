#!/usr/bin/env python3
"""One bounded, anonymous live public HTTPS source-capture acceptance run.

This is optional NETWORK acceptance, separate from Merlin's offline CI.
It does not render JavaScript, execute source code, run AI, download weights,
accept account credentials, or authorize promotion or deployment. The target is
a fixed public Python source tag, not a moving branch or user-supplied URL.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable" / "merlin_studio"))
from public_web import PublicWebError, PublicWebFetcher

URL = "https://raw.githubusercontent.com/python/cpython/v3.12.1/Lib/fractions.py"
LIMIT = 192 * 1024


def source_commit():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, timeout=10, check=False)
    source = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"[0-9a-f]{40}", source):
        raise RuntimeError("an exact checked-out GitHub source SHA is required")
    if os.environ.get("MERLIN_EXPECTED_SHA", source) != source:
        raise RuntimeError("source does not match the CI reviewed SHA")
    return source


def atomic_write(path: Path, body: bytes):
    fd, temp = tempfile.mkstemp(prefix="._merlin-source-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def record(output: Path, result: dict, *, commit: str) -> dict:
    raw = result["body"]
    if (result["status"] != 200 or result["final_url"] != URL
            or result["retrieval_kind"] != "https_http"
            or not isinstance(raw, bytes)
            or not 200 <= len(raw) <= LIMIT
            or b"class Fraction" not in raw
            or result["sha256"] != hashlib.sha256(raw).hexdigest()
            or result["network_bytes"] < len(raw)
            or len(result["redirects"]) != 0):
        raise ValueError("live source content, TLS retrieval metadata or byte identity differed")
    output.mkdir(parents=True, exist_ok=True)
    atomic_write(output / "public-source-raw.py.txt", raw)
    receipt = {
        "schema": "merlin-public-https-source-acceptance/1",
        "source_repository": "Mannyspiro/expert-robot",
        "source_commit": commit,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": URL,
        "final_url": result["final_url"],
        "status": result["status"],
        "retrieval_kind": result["retrieval_kind"],
        "content_type": result["content_type"],
        "raw_path": "public-source-raw.py.txt",
        "raw_bytes": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "network_bytes": result["network_bytes"],
        "redirect_count": len(result["redirects"]),
        "source_observed": True,
        "domain_ownership_or_scientific_truth_verified": False,
        "browser_rendering_performed": False,
        "model_inference_performed": False,
        "private_context_included": False,
        "external_spend_usd": 0,
        "promotion_authority": False,
    }
    atomic_write(output / "receipt.json",
                 (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode())
    return receipt


def live(output: Path):
    commit = source_commit()
    output.mkdir(parents=True, exist_ok=True)
    try:
        response = PublicWebFetcher().fetch(URL, max_bytes=LIMIT,
                                            timeout=20, max_redirects=0)
        receipt = record(output, response, commit=commit)
    except Exception as exc:
        failure = {
            "schema": "merlin-public-https-source-failure/1",
            "source_commit": commit,
            "source_url": URL,
            "error_type": type(exc).__name__,
            "error_code": exc.code if isinstance(exc, PublicWebError) else "invalid_result",
            "http_status": exc.status if isinstance(exc, PublicWebError) else None,
            "source_observed": False,
            "independent_verification": False,
            "side_effects": "bounded anonymous HTTPS read only",
        }
        atomic_write(output / "failure.json",
                     (json.dumps(failure, indent=2, sort_keys=True) + "\n").encode())
        raise
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = live(args.output.resolve())
    except Exception as exc:
        print("public source acceptance BLOCKED: "
              + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"status": "source_observed",
                      "source_commit": receipt["source_commit"],
                      "raw_bytes": receipt["raw_bytes"],
                      "raw_sha256": receipt["raw_sha256"],
                      "scientific_truth_verified": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
