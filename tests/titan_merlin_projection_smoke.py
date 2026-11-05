#!/usr/bin/env python3
"""Smoke-test the read-only Merlin projection without promoting evidence."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "projection.json"
    subprocess.run(
        [sys.executable, "scripts/export_titan_merlin_projection.py", "--output", str(out)],
        check=True, timeout=10, capture_output=True, text=True,
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["projection"] == "merlin-titan-research-read-only"
    assert data["record_count"] == len(data["records"])
    assert data["records"]
    assert all(record["promotion_authority"] is False for record in data["records"])
    assert all(record["qualification_status"] == "research_only" for record in data["records"])
    assert any(record["test_result"] == "blocked" for record in data["records"])
    assert any(record["cace_verification_status"] == "pass" for record in data["records"])
print("Titan Merlin projection smoke test passed; no promotion authority.")
