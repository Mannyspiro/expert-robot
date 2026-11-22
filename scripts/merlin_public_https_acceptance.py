#!/usr/bin/env python3
"""Two live public, primary-source HTTPS captures with exact-byte receipts.

This is NOT rendered Chromium, autonomous model research or source-truth proof.
A failed source stays a failed source; no fixture may replace a live response.
"""
from __future__ import annotations
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable"))
from merlin_studio.public_web import PublicWebError, fetch_public

SOURCES = (
    ("iana-reserved", "https://www.iana.org/domains/reserved"),
    ("rfc2606", "https://www.rfc-editor.org/rfc/rfc2606.html"),
)
TOKENS = ("example.com", "example.net", "example.org")
MAX_BYTES = 600000


def acquire(directory: Path, fetch=fetch_public):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    result = {
        "schema": "merlin-real-public-primary-sources/1",
        "status": "blocked",
        "question": "Do the two original public documents explicitly name all three example domains?",
        "source_class": "live_primary_source_http_bytes",
        "sources_predeclared": [{"id": name, "requested_url": url} for name, url in SOURCES],
        "expected_strings": list(TOKENS),
        "records": records,
        "model_calls": 0,
        "browser_render_calls": 0,
        "external_model_spend_usd": 0,
        "production_qualified": False,
        "promotion_authority": False,
    }
    try:
        for index, (name, url) in enumerate(SOURCES, 1):
            item = fetch(url, max_bytes=MAX_BYTES, timeout=25, max_redirects=4)
            raw = item["body"]
            assert item["url"] == url and isinstance(raw, bytes)
            assert item["status"] == 200 and 0 < len(raw) <= MAX_BYTES
            assert item["network_bytes"] >= len(raw)
            digest = hashlib.sha256(raw).hexdigest()
            assert digest == item["sha256"]
            text = item["text"]
            assert isinstance(text, str) and 0 < len(text) < 1_000_000
            name_on_disk = "source-" + str(index) + ".bin"
            target = directory / name_on_disk
            with target.open("xb") as stream:
                stream.write(raw)
            seen = {token: token in text.lower() for token in TOKENS}
            records.append({
                "source_id": name, "requested_url": url,
                "final_url": item["final_url"], "status": item["status"],
                "content_type": item["content_type"], "body_file": name_on_disk,
                "raw_sha256": digest, "body_bytes": len(raw),
                "total_network_bytes": item["network_bytes"], "redirects": item["redirects"],
                "literal_token_presence": seen,
                "capture_time_utc": datetime.now(timezone.utc).isoformat(),
            })
        result["status"] = ("passed"
                            if len(records) == 2 and
                            all(all(row["literal_token_presence"].values()) for row in records)
                            else "reference_disagrees")
        result["bytes_rechecked"] = all(
            hashlib.sha256((directory / row["body_file"]).read_bytes()).hexdigest() == row["raw_sha256"]
            for row in records)
        if not result["bytes_rechecked"]:
            result["status"] = "blocked"
    except Exception as exc:
        result["status"] = "blocked"
        result["error_type"] = type(exc).__name__
        result["error_reason"] = str(exc)[:280]
    (directory / "report.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "sources": len(records),
                      "browser_render_calls": 0, "model_calls": 0,
                      "production_qualified": False}, sort_keys=True))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = acquire(args.output)
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
